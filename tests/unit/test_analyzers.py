"""Tests for risk analyzers."""

from decimal import Decimal
from pathlib import Path

import pytest

from irpf_analyzer.core.analyzers import (
    ConsistencyAnalyzer,
    DeductionAnalyzer,
    RiskAnalyzer,
    analyze_declaration,
)
from irpf_analyzer.core.models import (
    Declaration,
    BemDireito,
    Deducao,
    Dependente,
    TipoDeclaracao,
    TipoDeducao,
    GrupoBem,
    RiskLevel,
)
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.enums import TipoDependente


class TestConsistencyAnalyzer:
    """Tests for ConsistencyAnalyzer."""

    def test_no_inconsistencies_when_balanced(self):
        """Test that balanced declaration has no inconsistencies."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="01",
                    discriminacao="Poupança",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("60000"),  # 10k increase, reasonable with 100k income
                )
            ],
        )

        analyzer = ConsistencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # With 100k income and 10k patrimony increase, should be fine
        assert len([i for i in inconsistencies if i.tipo.value == "patrimonio_vs_renda"]) == 0

    def test_detects_patrimony_vs_income_issue(self):
        """Test detection of large patrimony increase vs low income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("50000"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento",
                    situacao_anterior=Decimal("200000"),
                    situacao_atual=Decimal("500000"),  # 300k increase with 50k income
                )
            ],
        )

        analyzer = ConsistencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should detect patrimony vs income issue
        patrimony_issues = [i for i in inconsistencies if i.tipo.value == "patrimonio_vs_renda"]
        assert len(patrimony_issues) > 0

    def test_detects_patrimony_without_income(self):
        """Test detection of patrimony declared without income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("0"),
            total_rendimentos_isentos=Decimal("0"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Casa",
                    situacao_anterior=Decimal("500000"),
                    situacao_atual=Decimal("500000"),
                )
            ],
        )

        analyzer = ConsistencyAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should detect zero income with high patrimony
        zero_issues = [i for i in inconsistencies if i.tipo.value == "valor_zerado_suspeito"]
        assert len(zero_issues) > 0


class TestDeductionAnalyzer:
    """Tests for DeductionAnalyzer."""

    def test_no_issues_with_normal_deductions(self):
        """Test that normal deductions don't trigger warnings."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("5000"),  # 5% of income, normal
                    cnpj_prestador="11222333000181",
                    nome_prestador="Hospital XYZ",
                )
            ],
        )

        analyzer = DeductionAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # 5% medical expenses is normal
        medical_issues = [i for i in inconsistencies if i.tipo.value == "despesas_medicas_altas"]
        assert len(medical_issues) == 0

    def test_detects_high_medical_expenses(self):
        """Test detection of suspiciously high medical expenses."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("35000"),  # 35% of income, very high
                    cnpj_prestador="11222333000181",
                    nome_prestador="Hospital",
                )
            ],
        )

        analyzer = DeductionAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        medical_issues = [i for i in inconsistencies if i.tipo.value == "despesas_medicas_altas"]
        assert len(medical_issues) > 0
        assert medical_issues[0].risco == RiskLevel.HIGH

    def test_detects_duplicate_dependents(self):
        """Test detection of duplicate dependent CPFs."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11144477735",
                    nome="Filho 1",
                ),
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11144477735",  # Same CPF!
                    nome="Filho 2",
                ),
            ],
        )

        analyzer = DeductionAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        duplicate_issues = [i for i in inconsistencies if i.tipo.value == "dependente_duplicado"]
        assert len(duplicate_issues) > 0
        assert duplicate_issues[0].risco == RiskLevel.CRITICAL


class TestRiskAnalyzer:
    """Tests for RiskAnalyzer."""

    def test_low_risk_score(self):
        """Test that clean declaration gets low risk score."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.DEPOSITOS_VISTA,
                    codigo="01",
                    discriminacao="Conta corrente",
                    situacao_anterior=Decimal("10000"),
                    situacao_atual=Decimal("15000"),
                )
            ],
        )

        result = analyze_declaration(decl)

        assert result.risk_score.score <= 20
        assert result.risk_score.level == RiskLevel.LOW

    def test_high_risk_score_with_issues(self):
        """Test that declaration with issues gets higher risk score."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("50000"),
            total_rendimentos_isentos=Decimal("0"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("30000"),  # 60% of income!
                    nome_prestador="Hospital",
                )
            ],
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Casa",
                    situacao_anterior=Decimal("100000"),
                    situacao_atual=Decimal("400000"),  # 300k increase
                )
            ],
        )

        result = analyze_declaration(decl)

        assert result.risk_score.score > 20
        assert len(result.inconsistencies) > 0

    def test_generates_suggestions(self):
        """Test that suggestions are generated."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            total_deducoes=Decimal("5000"),  # Low deductions
        )

        result = analyze_declaration(decl)

        # Should suggest simplified declaration
        assert any("simplificada" in s.titulo.lower() for s in result.suggestions)


class TestIntegrationWithRealFile:
    """Integration tests with real DEC file."""

    @pytest.fixture
    def real_dec_path(self) -> Path:
        """Path to real DEC file for testing."""
        return Path(__file__).parent.parent / "fixtures" / "83158073072-IRPF-A-2025-2024-ORIGI.DEC"

    def test_analyze_real_file(self, real_dec_path: Path):
        """Test full analysis of real DEC file."""
        if not real_dec_path.exists():
            pytest.skip("Real DEC file not available")

        from irpf_analyzer.infrastructure.parsers.dec_parser import parse_dec_file

        declaration = parse_dec_file(real_dec_path)
        result = analyze_declaration(declaration)

        # Should return valid result
        assert result is not None
        assert 0 <= result.risk_score.score <= 100
        assert result.risk_score.level in RiskLevel
