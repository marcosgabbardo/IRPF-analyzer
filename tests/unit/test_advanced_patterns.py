"""Tests for advanced pattern detector."""

from datetime import date
from decimal import Decimal

from irpf_analyzer.core.analyzers.advanced_patterns import (
    AdvancedPatternDetector,
    analyze_advanced_patterns,
)
from irpf_analyzer.core.models import (
    BemDireito,
    Declaration,
    Deducao,
    GrupoBem,
    RiskLevel,
    TipoDeclaracao,
    TipoDeducao,
)
from irpf_analyzer.core.models.alienation import Alienacao
from irpf_analyzer.core.models.analysis import InconsistencyType
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.enums import TipoRendimento
from irpf_analyzer.core.models.income import Rendimento


class TestSmurfingDetection:
    """Tests for smurfing (transaction splitting) detection."""

    def test_detects_smurfing_in_alienations(self):
        """Test detection of multiple alienations just below R$ 30k threshold."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            alienacoes=[
                Alienacao(
                    nome_bem="Criptoativo Bitcoin 1",
                    tipo_bem="CRIPTO",
                    valor_alienacao=Decimal("28000"),  # Just below R$ 30k
                    ganho_capital=Decimal("5000"),
                ),
                Alienacao(
                    nome_bem="Criptoativo Bitcoin 2",
                    tipo_bem="CRIPTO",
                    valor_alienacao=Decimal("27500"),  # Just below R$ 30k
                    ganho_capital=Decimal("4500"),
                ),
                Alienacao(
                    nome_bem="Criptoativo Bitcoin 3",
                    tipo_bem="CRIPTO",
                    valor_alienacao=Decimal("29000"),  # Just below R$ 30k
                    ganho_capital=Decimal("6000"),
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        smurfing_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.SMURFING_DETECTADO
        ]
        assert len(smurfing_issues) > 0
        assert smurfing_issues[0].risco == RiskLevel.HIGH
        assert "fracionamento" in smurfing_issues[0].descricao.lower()

    def test_no_smurfing_for_varied_values(self):
        """Test that varied alienation values don't trigger smurfing."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            alienacoes=[
                Alienacao(
                    nome_bem="Ativo 1",
                    tipo_bem="OUTROS",
                    valor_alienacao=Decimal("15000"),
                    ganho_capital=Decimal("2000"),
                ),
                Alienacao(
                    nome_bem="Ativo 2",
                    tipo_bem="OUTROS",
                    valor_alienacao=Decimal("45000"),  # Above threshold
                    ganho_capital=Decimal("8000"),
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        smurfing_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.SMURFING_DETECTADO
        ]
        assert len(smurfing_issues) == 0

    def test_detects_smurfing_in_acquisitions(self):
        """Test detection of multiple acquisitions near threshold."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("50000"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.OUTROS_BENS,
                    codigo="99",
                    discriminacao="Bem A",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("28000"),  # Near threshold
                ),
                BemDireito(
                    grupo=GrupoBem.OUTROS_BENS,
                    codigo="99",
                    discriminacao="Bem B",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("27000"),  # Near threshold
                ),
                BemDireito(
                    grupo=GrupoBem.OUTROS_BENS,
                    codigo="99",
                    discriminacao="Bem C",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("29500"),  # Near threshold
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        smurfing_warnings = [
            w for w in warnings
            if "fracionamento" in w.mensagem.lower() or "próximos ao limite" in w.mensagem.lower()
        ]
        assert len(smurfing_warnings) > 0


class TestRoundTripDetection:
    """Tests for round-trip (wash sale) detection."""

    def test_detects_round_trip_same_company(self):
        """Test detection of sell and rebuy of same company shares."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            alienacoes=[
                Alienacao(
                    nome_bem="QUOTAS EMPRESA ABC LTDA",
                    tipo_bem="QUOTAS",
                    cnpj="11222333000181",
                    valor_alienacao=Decimal("100000"),
                    ganho_capital=Decimal("-10000"),  # Loss
                    data_alienacao=date(2024, 6, 15),
                ),
            ],
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.PARTICIPACOES_SOCIETARIAS,
                    codigo="31",
                    discriminacao="QUOTAS EMPRESA ABC LTDA - CNPJ 11222333000181",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("80000"),  # Rebought
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        round_trip_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.ROUND_TRIP_SUSPEITO
        ]
        assert len(round_trip_issues) > 0
        assert "vai-e-volta" in round_trip_issues[0].descricao.lower()

    def test_no_round_trip_for_different_assets(self):
        """Test that different assets don't trigger round-trip."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            alienacoes=[
                Alienacao(
                    nome_bem="QUOTAS EMPRESA XYZ",
                    tipo_bem="QUOTAS",
                    cnpj="11111111000111",
                    valor_alienacao=Decimal("50000"),
                    ganho_capital=Decimal("5000"),
                ),
            ],
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.PARTICIPACOES_SOCIETARIAS,
                    codigo="31",
                    discriminacao="QUOTAS EMPRESA DIFERENTE",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("60000"),
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        round_trip_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.ROUND_TRIP_SUSPEITO
        ]
        assert len(round_trip_issues) == 0

    def test_detects_multiple_round_trips(self):
        """Test detection of multiple round-trip operations."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            alienacoes=[
                Alienacao(
                    nome_bem="EMPRESA ALFA",
                    tipo_bem="QUOTAS",
                    cnpj="11111111000111",
                    valor_alienacao=Decimal("50000"),
                    ganho_capital=Decimal("-5000"),
                ),
                Alienacao(
                    nome_bem="EMPRESA BETA",
                    tipo_bem="QUOTAS",
                    cnpj="22222222000122",
                    valor_alienacao=Decimal("60000"),
                    ganho_capital=Decimal("-8000"),
                ),
                Alienacao(
                    nome_bem="EMPRESA GAMMA",
                    tipo_bem="QUOTAS",
                    cnpj="33333333000133",
                    valor_alienacao=Decimal("70000"),
                    ganho_capital=Decimal("-10000"),
                ),
                Alienacao(
                    nome_bem="EMPRESA DELTA",
                    tipo_bem="QUOTAS",
                    cnpj="44444444000144",
                    valor_alienacao=Decimal("80000"),
                    ganho_capital=Decimal("-12000"),
                ),
            ],
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.PARTICIPACOES_SOCIETARIAS,
                    codigo="31",
                    discriminacao="EMPRESA ALFA CNPJ 11111111000111",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("45000"),
                ),
                BemDireito(
                    grupo=GrupoBem.PARTICIPACOES_SOCIETARIAS,
                    codigo="31",
                    discriminacao="EMPRESA BETA CNPJ 22222222000122",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("55000"),
                ),
                BemDireito(
                    grupo=GrupoBem.PARTICIPACOES_SOCIETARIAS,
                    codigo="31",
                    discriminacao="EMPRESA GAMMA CNPJ 33333333000133",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("65000"),
                ),
                BemDireito(
                    grupo=GrupoBem.PARTICIPACOES_SOCIETARIAS,
                    codigo="31",
                    discriminacao="EMPRESA DELTA CNPJ 44444444000144",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("75000"),
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        round_trip_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.ROUND_TRIP_SUSPEITO
        ]
        # Should detect multiple round-trips (max 3 detailed + warning for more)
        assert len(round_trip_issues) >= 3

        # Should have warning about total count
        round_trip_warnings = [
            w for w in warnings
            if "vai-e-volta" in w.mensagem.lower()
        ]
        assert len(round_trip_warnings) > 0


class TestPhantomDeductionsDetection:
    """Tests for phantom deductions (fake providers) detection."""

    def test_detects_invalid_cnpj_provider(self):
        """Test detection of deductions with invalid CNPJ providers."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("5000"),
                    cnpj_prestador="11111111111111",  # Invalid CNPJ
                    nome_prestador="Clinica Fantasma",
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        phantom_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEDUCAO_PRESTADOR_FANTASMA
        ]
        assert len(phantom_issues) > 0
        assert phantom_issues[0].risco == RiskLevel.HIGH
        assert "inválido" in phantom_issues[0].descricao.lower()

    def test_detects_invalid_cpf_provider(self):
        """Test detection of deductions with invalid CPF providers."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("3000"),
                    cpf_prestador="12345678901",  # Invalid CPF
                    nome_prestador="Dr. Fantasma",
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        phantom_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEDUCAO_PRESTADOR_FANTASMA
        ]
        assert len(phantom_issues) > 0
        assert "CPF" in phantom_issues[0].descricao

    def test_no_phantom_for_valid_providers(self):
        """Test that valid provider IDs don't trigger phantom detection."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("2000"),
                    cnpj_prestador="11222333000181",  # Valid CNPJ
                    nome_prestador="Clinica Real",
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("1500"),
                    cpf_prestador="11144477735",  # Valid CPF
                    nome_prestador="Dr. Real",
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        phantom_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEDUCAO_PRESTADOR_FANTASMA
        ]
        assert len(phantom_issues) == 0

    def test_detects_deductions_without_provider_id(self):
        """Test detection of medical expenses without provider identification."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("1000"),
                    nome_prestador="Prestador 1",
                    # No CPF/CNPJ
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("1500"),
                    nome_prestador="Prestador 2",
                    # No CPF/CNPJ
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("2000"),
                    nome_prestador="Prestador 3",
                    # No CPF/CNPJ
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        no_id_warnings = [
            w for w in warnings
            if "sem identificação" in w.mensagem.lower()
        ]
        assert len(no_id_warnings) > 0

    def test_detects_multiple_invalid_providers(self):
        """Test detection of multiple invalid provider IDs with summary."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("1000"),
                    cnpj_prestador="11111111111111",  # Invalid
                    nome_prestador="Clinica 1",
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("1500"),
                    cnpj_prestador="22222222222222",  # Invalid
                    nome_prestador="Clinica 2",
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("2000"),
                    cnpj_prestador="33333333333333",  # Invalid
                    nome_prestador="Clinica 3",
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("2500"),
                    cnpj_prestador="44444444444444",  # Invalid
                    nome_prestador="Clinica 4",
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("3000"),
                    cnpj_prestador="55555555555555",  # Invalid
                    nome_prestador="Clinica 5",
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("3500"),
                    cnpj_prestador="66666666666666",  # Invalid
                    nome_prestador="Clinica 6",
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        phantom_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEDUCAO_PRESTADOR_FANTASMA
        ]
        # Should have max 5 detailed issues
        assert len(phantom_issues) == 5

        # Should have warning about total
        total_warnings = [
            w for w in warnings
            if "prestadores inválidos" in w.mensagem.lower()
        ]
        assert len(total_warnings) > 0


class TestCashFlowTimingAnalysis:
    """Tests for cash flow timing analysis."""

    def test_detects_suspicious_loss_gain_compensation(self):
        """Test detection of losses matching gains (tax manipulation)."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            alienacoes=[
                Alienacao(
                    nome_bem="Ativo com Lucro",
                    tipo_bem="QUOTAS",
                    valor_alienacao=Decimal("100000"),
                    ganho_capital=Decimal("50000"),  # R$ 50k gain
                ),
                Alienacao(
                    nome_bem="Ativo com Prejuizo",
                    tipo_bem="QUOTAS",
                    valor_alienacao=Decimal("80000"),
                    ganho_capital=Decimal("-48000"),  # R$ 48k loss (close to gain)
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        timing_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.TIMING_FLUXO_CAIXA_SUSPEITO
        ]
        assert len(timing_issues) > 0
        assert "compensação" in timing_issues[0].descricao.lower()

    def test_detects_large_acquisitions_vs_income(self):
        """Test detection of large acquisitions relative to income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("80000"),
            total_rendimentos_isentos=Decimal("10000"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="11",
                    discriminacao="Apartamento novo",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("100000"),
                ),
                BemDireito(
                    grupo=GrupoBem.VEICULOS,
                    codigo="21",
                    discriminacao="Carro novo",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("80000"),
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        acquisition_warnings = [
            w for w in warnings
            if "aquisições" in w.mensagem.lower() and "alto valor" in w.mensagem.lower()
        ]
        assert len(acquisition_warnings) > 0

    def test_detects_patrimony_income_mismatch(self):
        """Test detection of patrimony growth not explained by income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("60000"),
            total_rendimentos_isentos=Decimal("10000"),
            total_deducoes=Decimal("20000"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.OUTROS_BENS,
                    codigo="99",
                    discriminacao="Bem existente",
                    situacao_anterior=Decimal("100000"),
                    situacao_atual=Decimal("250000"),  # R$ 150k increase
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        timing_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.TIMING_FLUXO_CAIXA_SUSPEITO
        ]
        # Should detect mismatch (R$ 150k growth vs R$ 50k available income)
        assert len(timing_issues) > 0
        assert "variação patrimonial" in timing_issues[0].descricao.lower()

    def test_no_issues_for_balanced_declaration(self):
        """Test that balanced declaration doesn't trigger timing issues."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("150000"),
            total_rendimentos_isentos=Decimal("20000"),
            total_deducoes=Decimal("30000"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.OUTROS_BENS,
                    codigo="99",
                    discriminacao="Bem",
                    situacao_anterior=Decimal("100000"),
                    situacao_atual=Decimal("150000"),  # R$ 50k increase
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        # Patrimony increase (50k) is less than available income (140k)
        # Should not trigger timing mismatch
        timing_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.TIMING_FLUXO_CAIXA_SUSPEITO
            and "variação patrimonial" in i.descricao.lower()
        ]
        assert len(timing_issues) == 0

    def test_detects_high_bonus_proportion(self):
        """Test detection of high proportion of bonus/extra income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                    valor_anual=Decimal("60000"),
                    descricao="SALARIO NORMAL",
                ),
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                    valor_anual=Decimal("40000"),
                    descricao="13o SALARIO E PLR BONUS",
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        bonus_warnings = [
            w for w in warnings
            if "bônus" in w.mensagem.lower() or "extras" in w.mensagem.lower()
        ]
        assert len(bonus_warnings) > 0
        assert bonus_warnings[0].informativo is True


class TestProviderPatterns:
    """Tests for provider pattern detection."""

    def test_detects_provider_with_multiple_service_types(self):
        """Test detection of provider offering many different service types."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("1000"),
                    cnpj_prestador="11222333000181",
                    nome_prestador="Empresa Multi",
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_EDUCACAO,
                    valor=Decimal("2000"),
                    cnpj_prestador="11222333000181",
                    nome_prestador="Empresa Multi",
                ),
                Deducao(
                    tipo=TipoDeducao.PREVIDENCIA_PRIVADA,
                    valor=Decimal("3000"),
                    cnpj_prestador="11222333000181",
                    nome_prestador="Empresa Multi",
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        multi_warnings = [
            w for w in warnings
            if "tipos diferentes" in w.mensagem.lower()
        ]
        assert len(multi_warnings) > 0


class TestAnalyzeAdvancedPatternsFunction:
    """Tests for convenience function."""

    def test_analyze_advanced_patterns_returns_tuple(self):
        """Test that analyze_advanced_patterns returns correct tuple."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        result = analyze_advanced_patterns(decl)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)  # inconsistencies
        assert isinstance(result[1], list)  # warnings

    def test_analyze_empty_declaration(self):
        """Test analysis of minimal declaration."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        # Empty declaration should have no issues
        assert isinstance(inconsistencies, list)
        assert isinstance(warnings, list)


class TestKeyNormalization:
    """Tests for asset key normalization helper methods."""

    def test_normalize_with_cnpj(self):
        """Test key normalization with CNPJ."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )
        detector = AdvancedPatternDetector(decl)

        key = detector._normalize_asset_key("Test Asset", "01", "11222333000181")
        assert key.startswith("CNPJ:")

    def test_normalize_with_name(self):
        """Test key normalization with name only."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )
        detector = AdvancedPatternDetector(decl)

        key = detector._normalize_asset_key("QUOTAS DA EMPRESA XYZ", "31", "")
        assert key.startswith("NOME:")
        assert "QUOTAS" in key

    def test_keys_match_same_cnpj(self):
        """Test that keys with same CNPJ base match."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )
        detector = AdvancedPatternDetector(decl)

        key1 = "CNPJ:11222333"
        key2 = "CNPJ:11222333"
        assert detector._keys_match(key1, key2) is True

    def test_keys_match_different_cnpj(self):
        """Test that keys with different CNPJ don't match."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )
        detector = AdvancedPatternDetector(decl)

        key1 = "CNPJ:11222333"
        key2 = "CNPJ:44555666"
        assert detector._keys_match(key1, key2) is False


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_value_deductions_ignored(self):
        """Test that zero-value deductions are ignored."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("0"),
                    cnpj_prestador="11111111111111",  # Invalid, but value is 0
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        phantom_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEDUCAO_PRESTADOR_FANTASMA
        ]
        assert len(phantom_issues) == 0

    def test_zero_value_alienations_ignored(self):
        """Test that zero-value alienations are ignored."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            alienacoes=[
                Alienacao(
                    nome_bem="Test",
                    tipo_bem="OUTROS",
                    valor_alienacao=Decimal("0"),
                    ganho_capital=Decimal("0"),
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        smurfing_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.SMURFING_DETECTADO
        ]
        assert len(smurfing_issues) == 0

    def test_small_acquisitions_not_flagged(self):
        """Test that small acquisitions don't trigger warnings."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("50000"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.OUTROS_BENS,
                    codigo="99",
                    discriminacao="Pequeno bem",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("5000"),  # Small value
                ),
            ],
        )

        detector = AdvancedPatternDetector(decl)
        inconsistencies, warnings = detector.analyze()

        # Small acquisitions shouldn't trigger timing warnings
        timing_warnings = [
            w for w in warnings
            if "aquisições" in w.mensagem.lower() and "alto valor" in w.mensagem.lower()
        ]
        assert len(timing_warnings) == 0
