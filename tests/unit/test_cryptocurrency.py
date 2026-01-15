"""Tests for cryptocurrency analyzer (IN RFB 1888/2019)."""

from decimal import Decimal

import pytest

from irpf_analyzer.core.analyzers.cryptocurrency import (
    CryptocurrencyAnalyzer,
    analyze_cryptocurrency,
)
from irpf_analyzer.core.models import (
    BemDireito,
    Declaration,
    GrupoBem,
    RiskLevel,
    TipoDeclaracao,
)
from irpf_analyzer.core.models.analysis import InconsistencyType
from irpf_analyzer.core.models.declaration import Alienacao, Contribuinte


class TestCapitalGainsThreshold:
    """Tests for IN 1888/2019 capital gains threshold (R$ 35k/mês)."""

    def test_detects_gains_above_35k_monthly(self):
        """Capital gains > R$ 35k/mês should trigger inconsistency."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin (BTC) - 1.5 unidades",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("100000"),
                    lucro_prejuizo=Decimal("500000"),  # ~42k/month average
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should detect gains above threshold
        gain_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.GANHO_CAPITAL_CRIPTO_ACIMA_LIMITE
        ]
        assert len(gain_issues) == 1
        assert gain_issues[0].risco == RiskLevel.HIGH
        assert "IN RFB 1888/2019" in gain_issues[0].descricao
        assert "35" in gain_issues[0].descricao  # Mentions the threshold

    def test_no_issue_for_gains_below_threshold(self):
        """Capital gains < R$ 35k/mês should not trigger issue."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin (BTC)",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("60000"),
                    lucro_prejuizo=Decimal("200000"),  # ~17k/month - below threshold
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        gain_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.GANHO_CAPITAL_CRIPTO_ACIMA_LIMITE
        ]
        assert len(gain_issues) == 0

    def test_aggregates_multiple_crypto_gains(self):
        """Should aggregate gains from multiple cryptocurrencies."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin (BTC)",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("100000"),
                    lucro_prejuizo=Decimal("250000"),  # ~21k/month
                ),
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="02",
                    discriminacao="Ethereum (ETH)",
                    situacao_anterior=Decimal("30000"),
                    situacao_atual=Decimal("60000"),
                    lucro_prejuizo=Decimal("300000"),  # ~25k/month
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Combined: ~46k/month - should trigger
        gain_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.GANHO_CAPITAL_CRIPTO_ACIMA_LIMITE
        ]
        assert len(gain_issues) == 1

    def test_includes_alienations_in_gains(self):
        """Should include capital gains from alienations."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin (BTC)",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("100000"),
                    lucro_prejuizo=Decimal("100000"),  # ~8k/month
                ),
            ],
            alienacoes=[
                Alienacao(
                    nome_bem="Bitcoin vendido",
                    valor_alienacao=Decimal("500000"),
                    custo_aquisicao=Decimal("100000"),
                    ganho_capital=Decimal("400000"),  # ~33k/month
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Combined: ~41k/month - should trigger
        gain_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.GANHO_CAPITAL_CRIPTO_ACIMA_LIMITE
        ]
        assert len(gain_issues) == 1

    def test_ignores_losses(self):
        """Should not count losses (negative lucro_prejuizo) in gains."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin (BTC)",
                    situacao_anterior=Decimal("100000"),
                    situacao_atual=Decimal("50000"),
                    lucro_prejuizo=Decimal("-50000"),  # Loss
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        gain_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.GANHO_CAPITAL_CRIPTO_ACIMA_LIMITE
        ]
        assert len(gain_issues) == 0


class TestIN1888Reporting:
    """Tests for IN 1888/2019 reporting requirements."""

    def test_warns_about_reporting_obligation(self):
        """Should warn when crypto holdings > R$ 5k."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin (BTC)",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should have informative warning about IN 1888/2019
        in1888_warnings = [
            w for w in warnings
            if "IN RFB 1888/2019" in w.mensagem
        ]
        assert len(in1888_warnings) > 0
        assert in1888_warnings[0].informativo is True

    def test_no_warning_for_small_holdings(self):
        """Holdings < R$ 5k should not trigger obligation warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin (BTC)",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("3000"),  # Below R$ 5k
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        in1888_warnings = [
            w for w in warnings
            if "IN RFB 1888/2019" in w.mensagem
        ]
        assert len(in1888_warnings) == 0

    def test_counts_multiple_cryptos(self):
        """Should count number of cryptoassets in warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin (BTC)",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("3000"),
                ),
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="02",
                    discriminacao="Ethereum (ETH)",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("4000"),
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Total is R$ 7k - should warn
        in1888_warnings = [
            w for w in warnings
            if "IN RFB 1888/2019" in w.mensagem
        ]
        assert len(in1888_warnings) > 0
        assert "2 ativo(s)" in in1888_warnings[0].mensagem


class TestExchangeValidation:
    """Tests for exchange CNPJ validation."""

    def test_detects_invalid_exchange_cnpj(self):
        """Invalid exchange CNPJ should trigger inconsistency."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin na Binance",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                    cnpj_instituicao="11111111111111",  # Invalid CNPJ
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        cnpj_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.EXCHANGE_CNPJ_INVALIDO
        ]
        assert len(cnpj_issues) == 1
        assert cnpj_issues[0].risco == RiskLevel.MEDIUM

    def test_accepts_known_exchanges(self):
        """Known exchanges should not trigger warnings about CNPJ."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin no Mercado Bitcoin",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                    cnpj_instituicao="18189547000142",  # Mercado Bitcoin
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not have invalid CNPJ issues
        cnpj_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.EXCHANGE_CNPJ_INVALIDO
        ]
        assert len(cnpj_issues) == 0

        # Should not have unknown exchange warnings
        unknown_warnings = [
            w for w in warnings
            if "não reconhecido" in w.mensagem
        ]
        assert len(unknown_warnings) == 0

    def test_warns_about_unknown_exchange(self):
        """Valid but unknown CNPJ should trigger informative warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin em exchange desconhecida",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                    cnpj_instituicao="11222333000181",  # Valid but unknown
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not have invalid CNPJ issues (it's valid)
        cnpj_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.EXCHANGE_CNPJ_INVALIDO
        ]
        assert len(cnpj_issues) == 0

        # Should have unknown exchange warning
        unknown_warnings = [
            w for w in warnings
            if "não reconhecido" in w.mensagem
        ]
        assert len(unknown_warnings) == 1
        assert unknown_warnings[0].informativo is True

    def test_warns_about_self_custody(self):
        """Crypto without exchange CNPJ should warn about self-custody docs."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin em cold wallet",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                    # No cnpj_instituicao - self custody
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        custody_warnings = [
            w for w in warnings
            if "self-custody" in w.mensagem.lower()
        ]
        assert len(custody_warnings) == 1


class TestRoundValues:
    """Tests for round value detection in crypto holdings."""

    def test_detects_multiple_round_values(self):
        """Multiple round values should trigger warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),  # Round
                ),
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="02",
                    discriminacao="Ethereum",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("5000"),  # Round
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        round_warnings = [
            w for w in warnings
            if "redondos" in w.mensagem.lower()
        ]
        assert len(round_warnings) == 1

    def test_no_warning_for_non_round_values(self):
        """Non-round values should not trigger round value warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10234.56"),  # Not round
                ),
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="02",
                    discriminacao="Ethereum",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("5678.90"),  # Not round
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        round_warnings = [
            w for w in warnings
            if "redondos" in w.mensagem.lower()
        ]
        assert len(round_warnings) == 0


class TestAppreciationAlerts:
    """Tests for atypical appreciation detection."""

    def test_detects_extreme_appreciation(self):
        """Appreciation > 200% should trigger warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Altcoin especulativa",
                    situacao_anterior=Decimal("10000"),  # Above min threshold
                    situacao_atual=Decimal("50000"),  # 400% increase
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        appreciation_warnings = [
            w for w in warnings
            if "valorização atípica" in w.mensagem.lower()
        ]
        assert len(appreciation_warnings) == 1
        assert appreciation_warnings[0].risco == RiskLevel.MEDIUM

    def test_detects_extreme_depreciation(self):
        """Depreciation > 80% should trigger warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="02",
                    discriminacao="Token que colapsou",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("5000"),  # 90% loss
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        depreciation_warnings = [
            w for w in warnings
            if "desvalorização atípica" in w.mensagem.lower()
        ]
        assert len(depreciation_warnings) == 1

    def test_normal_variation_no_warning(self):
        """Normal variation (-80% to +200%) should not trigger warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin",
                    situacao_anterior=Decimal("10000"),
                    situacao_atual=Decimal("15000"),  # 50% increase - normal
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        variation_warnings = [
            w for w in warnings
            if "atípica" in w.mensagem.lower()
        ]
        assert len(variation_warnings) == 0

    def test_skips_small_previous_values(self):
        """Should skip variation analysis for small previous values."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Novo investimento",
                    situacao_anterior=Decimal("100"),  # Below min threshold
                    situacao_atual=Decimal("10000"),  # Would be 9900% increase
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not trigger because previous value too small
        variation_warnings = [
            w for w in warnings
            if "atípica" in w.mensagem.lower()
        ]
        assert len(variation_warnings) == 0


class TestPortfolioDiversity:
    """Tests for portfolio concentration detection."""

    def test_detects_high_concentration(self):
        """Single asset > 80% should trigger warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("90000"),  # 90% of portfolio
                ),
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="02",
                    discriminacao="Ethereum",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),  # 10% of portfolio
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        concentration_warnings = [
            w for w in warnings
            if "concentração" in w.mensagem.lower()
        ]
        assert len(concentration_warnings) == 1
        assert concentration_warnings[0].informativo is True

    def test_no_warning_for_diversified_portfolio(self):
        """Diversified portfolio should not trigger warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("40000"),  # 40%
                ),
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="02",
                    discriminacao="Ethereum",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("30000"),  # 30%
                ),
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="03",
                    discriminacao="Stablecoins",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("30000"),  # 30%
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        concentration_warnings = [
            w for w in warnings
            if "concentração" in w.mensagem.lower()
        ]
        assert len(concentration_warnings) == 0

    def test_skips_single_asset_portfolio(self):
        """Single asset portfolio should not trigger concentration warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="Bitcoin",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("100000"),
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        concentration_warnings = [
            w for w in warnings
            if "concentração" in w.mensagem.lower()
        ]
        assert len(concentration_warnings) == 0


class TestNoCryptocurrencies:
    """Tests for declarations without cryptocurrencies."""

    def test_no_issues_without_crypto(self):
        """Declaration without crypto should have no crypto issues."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="01",
                    discriminacao="CDB Banco XYZ",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("55000"),
                ),
            ],
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(inconsistencies) == 0
        assert len(warnings) == 0

    def test_empty_declaration(self):
        """Empty declaration should have no issues."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        analyzer = CryptocurrencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(inconsistencies) == 0
        assert len(warnings) == 0


class TestConvenienceFunction:
    """Tests for analyze_cryptocurrency convenience function."""

    def test_analyze_cryptocurrency_returns_tuple(self):
        """analyze_cryptocurrency should return tuple of lists."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        result = analyze_cryptocurrency(decl)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)  # inconsistencies
        assert isinstance(result[1], list)  # warnings
