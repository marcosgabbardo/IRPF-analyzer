"""Tests for investment optimization analyzer."""

from decimal import Decimal

from irpf_analyzer.core.analyzers.investment_optimization import (
    InvestmentOptimizationAnalyzer,
    analyze_investment_optimization,
)
from irpf_analyzer.core.models import (
    BemDireito,
    Declaration,
    GrupoBem,
    TipoDeclaracao,
)
from irpf_analyzer.core.models.alienation import Alienacao
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.enums import TipoRendimento
from irpf_analyzer.core.models.income import Rendimento


class TestTaxEfficientAllocation:
    """Tests for tax-efficient allocation suggestions."""

    def test_suggests_lci_lca_over_cdb(self):
        """Test that analyzer suggests LCI/LCA when user has high CDB holdings."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",  # CDB
                    discriminacao="CDB BANCO XYZ 120% CDI",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("55000"),
                ),
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",  # CDB
                    discriminacao="CDB BANCO ABC 115% CDI",
                    situacao_anterior=Decimal("40000"),
                    situacao_atual=Decimal("44000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should suggest LCI/LCA
        lci_suggestions = [
            s for s in suggestions
            if "LCI" in s.titulo or "LCA" in s.titulo
        ]
        assert len(lci_suggestions) > 0
        assert lci_suggestions[0].economia_potencial > 0

    def test_suggests_diversification_when_high_taxed_ratio(self):
        """Test that analyzer suggests diversification when taxed investments are high."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",  # CDB - taxed
                    discriminacao="CDB BANCO A",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("100000"),
                ),
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="42",  # RDB - taxed
                    discriminacao="RDB BANCO B",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("80000"),
                ),
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="45",  # LCI - exempt
                    discriminacao="LCI BANCO C",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("20000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should suggest diversification to exempt investments
        diversify_suggestions = [
            s for s in suggestions
            if "diversificar" in s.titulo.lower() or "isentos" in s.titulo.lower()
        ]
        assert len(diversify_suggestions) > 0

    def test_no_suggestion_for_mostly_exempt_portfolio(self):
        """Test that no reallocation suggestion when portfolio is mostly exempt."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="45",  # LCI - exempt
                    discriminacao="LCI BANCO A",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("100000"),
                ),
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="46",  # LCA - exempt
                    discriminacao="LCA BANCO B",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("80000"),
                ),
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",  # CDB - taxed (small amount)
                    discriminacao="CDB BANCO C",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("20000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should NOT suggest diversification (already mostly exempt)
        diversify_suggestions = [
            s for s in suggestions
            if "diversificar" in s.titulo.lower()
        ]
        assert len(diversify_suggestions) == 0


class TestFIIOpportunities:
    """Tests for FII (Real Estate Fund) opportunities."""

    def test_suggests_fii_when_none_in_portfolio(self):
        """Test that analyzer suggests FIIs when user has no FII holdings."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",  # CDB
                    discriminacao="CDB BANCO A",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("100000"),
                ),
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="45",  # LCI
                    discriminacao="LCI BANCO B",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("100000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should suggest FIIs
        fii_suggestions = [
            s for s in suggestions
            if "FII" in s.titulo or "Imobiliário" in s.titulo
        ]
        assert len(fii_suggestions) > 0

    def test_detects_fii_without_dividends(self):
        """Test that analyzer warns when FII holder has no dividend income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.FUNDOS,
                    codigo="73",  # FII
                    discriminacao="FII XPTO11 - FUNDO IMOBILIARIO XYZ",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("50000"),
                ),
            ],
            rendimentos=[],  # No dividend income declared
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should warn about missing FII dividends
        dividend_warnings = [
            w for w in warnings
            if "FII" in w.mensagem and "dividendos" in w.mensagem.lower()
        ]
        assert len(dividend_warnings) > 0

    def test_no_fii_suggestion_when_already_has_fii(self):
        """Test that analyzer doesn't suggest FIIs when user already has them."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.FUNDOS,
                    codigo="73",  # FII
                    discriminacao="FII XPTO11",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("50000"),
                ),
            ],
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.LUCROS_DIVIDENDOS,
                    valor_anual=Decimal("4000"),
                    descricao="DIVIDENDOS FII XPTO11",
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should NOT suggest FIIs (already has them with dividends)
        fii_suggestions = [
            s for s in suggestions
            if "Considere Fundos Imobiliários" in s.titulo
        ]
        assert len(fii_suggestions) == 0


class TestLossCompensation:
    """Tests for capital loss compensation opportunities."""

    def test_detects_accumulated_losses(self):
        """Test detection of accumulated losses from alienations."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            alienacoes=[
                Alienacao(
                    nome_bem="ACAO XYZ",
                    tipo_bem="ACOES",
                    valor_alienacao=Decimal("30000"),
                    ganho_capital=Decimal("-5000"),  # Loss
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should suggest loss compensation
        loss_suggestions = [
            s for s in suggestions
            if "Prejuízo" in s.titulo or "prejuízo" in s.descricao.lower()
        ]
        assert len(loss_suggestions) > 0
        assert loss_suggestions[0].economia_potencial > 0

    def test_detects_partial_compensation_opportunity(self):
        """Test detection when losses exceed gains of same type."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            alienacoes=[
                Alienacao(
                    nome_bem="ACAO ABC",
                    tipo_bem="ACOES",
                    valor_alienacao=Decimal("50000"),
                    ganho_capital=Decimal("10000"),  # Gain
                ),
                Alienacao(
                    nome_bem="ACAO XYZ",
                    tipo_bem="ACOES",
                    valor_alienacao=Decimal("30000"),
                    ganho_capital=Decimal("-20000"),  # Loss (greater than gain)
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should suggest carrying forward the remaining loss
        loss_suggestions = [
            s for s in suggestions
            if "Prejuízo acumulado" in s.titulo
        ]
        assert len(loss_suggestions) > 0

    def test_detects_foreign_stock_losses(self):
        """Test detection of losses in foreign stocks via lucro_prejuizo field."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="12",  # Foreign application
                    discriminacao="ACOES APPLE VIA AVENUE",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("40000"),
                    lucro_prejuizo=Decimal("-5000"),  # Loss declared
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should detect foreign stock loss
        foreign_loss_items = [
            s for s in suggestions
            if "estrangeiras" in s.descricao.lower()
        ] + [
            w for w in warnings
            if "estrangeiras" in w.mensagem.lower()
        ]
        assert len(foreign_loss_items) > 0

    def test_no_loss_suggestion_for_small_amounts(self):
        """Test that small losses don't trigger suggestions."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            alienacoes=[
                Alienacao(
                    nome_bem="ACAO XYZ",
                    tipo_bem="ACOES",
                    valor_alienacao=Decimal("5000"),
                    ganho_capital=Decimal("-500"),  # Small loss
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should NOT suggest for small losses
        loss_suggestions = [
            s for s in suggestions
            if "Prejuízo acumulado" in s.titulo
        ]
        assert len(loss_suggestions) == 0


class TestPortfolioConcentration:
    """Tests for portfolio concentration analysis."""

    def test_detects_high_concentration_in_taxed(self):
        """Test detection of high concentration in taxed investments."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",  # CDB
                    discriminacao="CDB BANCO A",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("200000"),
                ),
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="45",  # LCI
                    discriminacao="LCI BANCO B",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should warn about concentration
        concentration_warnings = [
            w for w in warnings
            if "concentração" in w.mensagem.lower()
        ]
        assert len(concentration_warnings) > 0

    def test_detects_high_concentration_in_crypto(self):
        """Test detection of high concentration in crypto assets."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",  # Crypto
                    discriminacao="BITCOIN",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("180000"),
                ),
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="45",  # LCI
                    discriminacao="LCI BANCO B",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("20000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should warn about crypto concentration
        crypto_warnings = [
            w for w in warnings
            if "Cripto" in w.mensagem
        ]
        assert len(crypto_warnings) > 0

    def test_no_concentration_warning_for_diversified(self):
        """Test that diversified portfolios don't trigger concentration warnings."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",  # CDB
                    discriminacao="CDB BANCO A",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("50000"),
                ),
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="45",  # LCI
                    discriminacao="LCI BANCO B",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("50000"),
                ),
                BemDireito(
                    grupo=GrupoBem.FUNDOS,
                    codigo="73",  # FII
                    discriminacao="FII XPTO11",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("50000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should NOT warn about concentration (diversified)
        concentration_warnings = [
            w for w in warnings
            if "concentração" in w.mensagem.lower()
        ]
        assert len(concentration_warnings) == 0


class TestInvestmentClassification:
    """Tests for investment classification logic."""

    def test_classifies_lci_as_exempt(self):
        """Test that LCI is classified as tax-exempt."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="45",  # LCI
                    discriminacao="LCI BANCO A",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        investments = analyzer.investments_classified

        assert len(investments) == 1
        assert investments[0].tax_type == "ISENTO"
        assert investments[0].tax_rate == Decimal("0")

    def test_classifies_cdb_as_exclusive(self):
        """Test that CDB is classified as exclusive taxation."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",  # CDB
                    discriminacao="CDB BANCO A",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        investments = analyzer.investments_classified

        assert len(investments) == 1
        assert investments[0].tax_type == "EXCLUSIVO"
        assert investments[0].tax_rate > Decimal("0")

    def test_classifies_fii_correctly(self):
        """Test that FII is correctly identified and classified."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.FUNDOS,
                    codigo="73",  # FII
                    discriminacao="FII XPTO11",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        investments = analyzer.investments_classified

        assert len(investments) == 1
        assert investments[0].is_fii is True
        assert investments[0].tax_type == "ISENTO"

    def test_classifies_crypto_correctly(self):
        """Test that crypto assets are correctly identified."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.CRIPTOATIVOS,
                    codigo="01",
                    discriminacao="BITCOIN",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        investments = analyzer.investments_classified

        assert len(investments) == 1
        assert investments[0].is_crypto is True
        assert investments[0].tax_rate == Decimal("0.15")  # 15% on capital gains

    def test_classifies_poupanca_as_exempt(self):
        """Test that savings account (poupança) is classified as exempt."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.POUPANCA,
                    codigo="01",
                    discriminacao="POUPANCA BANCO A",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        investments = analyzer.investments_classified

        assert len(investments) == 1
        assert investments[0].tax_type == "ISENTO"


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_analyze_investment_optimization_returns_tuple(self):
        """Test that the convenience function returns correct tuple."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        result = analyze_investment_optimization(decl)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)  # suggestions
        assert isinstance(result[1], list)  # warnings

    def test_analyze_empty_declaration(self):
        """Test analysis of declaration with no investments."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Empty declaration should have no issues
        assert isinstance(suggestions, list)
        assert isinstance(warnings, list)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_ignores_zero_value_assets(self):
        """Test that zero-value assets are ignored."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",
                    discriminacao="CDB RESGATADO",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("0"),  # Zero value (redeemed)
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        investments = analyzer.investments_classified

        # Zero-value asset should be ignored
        assert len(investments) == 0

    def test_handles_small_portfolio(self):
        """Test that small portfolios don't trigger suggestions."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",  # CDB
                    discriminacao="CDB PEQUENO",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("5000"),  # Small amount
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Small portfolio shouldn't trigger diversification suggestions
        diversify_suggestions = [
            s for s in suggestions
            if "diversificar" in s.titulo.lower()
        ]
        assert len(diversify_suggestions) == 0

    def test_recognizes_fii_from_description(self):
        """Test that FII is recognized from description when code is not 73."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.FUNDOS,
                    codigo="07",  # Generic fund code
                    discriminacao="FII HGLG11 - FUNDO IMOBILIARIO CSHG LOGISTICA",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("50000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)
        investments = analyzer.investments_classified

        assert len(investments) == 1
        assert investments[0].is_fii is True

    def test_caches_investment_classification(self):
        """Test that investment classification is cached."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",
                    discriminacao="CDB",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                ),
            ],
        )

        analyzer = InvestmentOptimizationAnalyzer(decl)

        # Access twice - should return same cached object
        first = analyzer.investments_classified
        second = analyzer.investments_classified

        assert first is second  # Same object (cached)
