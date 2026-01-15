"""Tests for dependent fraud analyzer."""

from datetime import date
from decimal import Decimal

import pytest

from irpf_analyzer.core.analyzers.dependent_fraud import (
    DependentFraudAnalyzer,
    analyze_dependent_fraud,
)
from irpf_analyzer.core.models import (
    Declaration,
    Dependente,
    Deducao,
    TipoDeclaracao,
    TipoDeducao,
    RiskLevel,
)
from irpf_analyzer.core.models.analysis import InconsistencyType
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.enums import TipoDependente


class TestCPFPatterns:
    """Tests for CPF pattern detection in dependents."""

    def test_detects_missing_cpf(self):
        """Test detection of dependent with empty CPF.

        Note: The model requires a string, so we test with empty string.
        The analyzer should catch this as missing/invalid CPF.
        """
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="",  # Empty CPF
                    nome="Filho Sem CPF",
                )
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Empty CPF should trigger invalid CPF detection
        cpf_issues = [i for i in inconsistencies if i.tipo == InconsistencyType.CPF_INVALIDO]
        assert len(cpf_issues) > 0

    def test_detects_invalid_cpf(self):
        """Test detection of invalid CPF in dependent."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11111111111",  # Invalid CPF
                    nome="Filho Teste",
                )
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        cpf_issues = [i for i in inconsistencies if i.tipo == InconsistencyType.CPF_INVALIDO]
        assert len(cpf_issues) > 0
        assert cpf_issues[0].risco == RiskLevel.CRITICAL

    def test_valid_cpf_no_issues(self):
        """Test that valid CPF doesn't trigger issues."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11144477735",  # Valid CPF
                    nome="Filho Teste",
                    data_nascimento=date(2015, 1, 1),
                )
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        cpf_issues = [i for i in inconsistencies if i.tipo == InconsistencyType.CPF_INVALIDO]
        assert len(cpf_issues) == 0


class TestAgeTypeConsistency:
    """Tests for age/type consistency validation."""

    def test_detects_overage_child(self):
        """Test detection of child dependent over 21 years old."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11144477735",
                    nome="Filho Velho",
                    data_nascimento=date(2000, 1, 1),  # ~25 years old
                )
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        age_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL
        ]
        assert len(age_issues) > 0
        assert age_issues[0].risco == RiskLevel.HIGH

    def test_detects_overage_university_student(self):
        """Test detection of university student over 24 years old."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_UNIVERSITARIO,
                    cpf="11144477735",
                    nome="Universitario Velho",
                    data_nascimento=date(1998, 1, 1),  # ~27 years old
                )
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        age_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL
        ]
        assert len(age_issues) > 0

    def test_detects_young_university_student(self):
        """Test warning for very young university student."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_UNIVERSITARIO,
                    cpf="11144477735",
                    nome="Genio Precoce",
                    data_nascimento=date(2012, 1, 1),  # ~13 years old
                )
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        young_warnings = [w for w in warnings if "Idade baixa" in w.mensagem]
        assert len(young_warnings) > 0

    def test_incapacitated_no_age_limit(self):
        """Test that incapacitated dependent has no age limit."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_INCAPAZ,
                    cpf="11144477735",
                    nome="Filho Incapaz",
                    data_nascimento=date(1980, 1, 1),  # ~45 years old - OK for incapaz
                )
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        age_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL
        ]
        assert len(age_issues) == 0


class TestDuplicateDependents:
    """Tests for duplicate dependent detection."""

    def test_detects_duplicate_cpf(self):
        """Test detection of same CPF used for multiple dependents."""
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
                    data_nascimento=date(2015, 1, 1),
                ),
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11144477735",  # Same CPF
                    nome="Filho 2",
                    data_nascimento=date(2015, 1, 1),
                ),
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        dup_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_DUPLICADO
        ]
        assert len(dup_issues) > 0
        assert dup_issues[0].risco == RiskLevel.CRITICAL


class TestEducationExpenses:
    """Tests for education expense attribution."""

    def test_detects_education_over_limit(self):
        """Test detection of education expenses over limit."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11144477735",
                    nome="Filho",
                    data_nascimento=date(2015, 1, 1),
                ),
            ],
            deducoes=[
                Deducao(tipo=TipoDeducao.DESPESAS_EDUCACAO, valor=Decimal("50000")),
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        edu_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DESPESAS_EDUCACAO_LIMITE
        ]
        assert len(edu_issues) > 0

    def test_detects_education_without_school_age_dependents(self):
        """Test warning for education expenses without school-age dependents."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.PAIS_AVOS_BISAVOS,
                    cpf="11144477735",
                    nome="Pai",
                    data_nascimento=date(1960, 1, 1),  # 65 years old
                ),
            ],
            deducoes=[
                Deducao(tipo=TipoDeducao.DESPESAS_EDUCACAO, valor=Decimal("15000")),
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        edu_warnings = [w for w in warnings if "idade escolar" in w.mensagem]
        assert len(edu_warnings) > 0


class TestOrphanExpenses:
    """Tests for dependent-related expenses without dependents."""

    def test_detects_education_over_limit_no_dependents(self):
        """Test detection of education exceeding individual limit without dependents."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[],  # No dependents
            deducoes=[
                Deducao(tipo=TipoDeducao.DESPESAS_EDUCACAO, valor=Decimal("10000")),
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Education > R$ 3.561,50 (2024 limit) without dependents
        edu_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEDUCAO_SEM_COMPROVANTE
        ]
        assert len(edu_issues) > 0


class TestDependentCount:
    """Tests for dependent count anomalies."""

    def test_warns_many_dependents(self):
        """Test warning for many dependents."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf=f"1114447773{i}",
                    nome=f"Filho {i}",
                    data_nascimento=date(2015, 1, 1),
                )
                for i in range(6)
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        count_warnings = [w for w in warnings if "elevado de dependentes" in w.mensagem]
        assert len(count_warnings) > 0


class TestSpouseIncome:
    """Tests for spouse income validation."""

    def test_warns_spouse_as_dependent(self):
        """Test informative warning when spouse is dependent."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.CONJUGE,
                    cpf="11144477735",
                    nome="Esposa",
                ),
            ],
        )

        analyzer = DependentFraudAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        spouse_warnings = [w for w in warnings if "Cônjuge" in w.mensagem]
        assert len(spouse_warnings) > 0
        assert spouse_warnings[0].informativo is True


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_analyze_dependent_fraud_returns_tuple(self):
        """Test that analyze_dependent_fraud returns correct tuple."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        result = analyze_dependent_fraud(decl)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)  # inconsistencies
        assert isinstance(result[1], list)  # warnings
