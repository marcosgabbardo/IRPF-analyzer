"""Tests for pattern analyzer."""

from decimal import Decimal

import pytest

from irpf_analyzer.core.analyzers.patterns import PatternAnalyzer, analyze_patterns
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
from irpf_analyzer.core.models.analysis import InconsistencyType
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.enums import TipoDependente, TipoRendimento
from irpf_analyzer.core.models.income import Rendimento, FontePagadora


class TestRoundValues:
    """Tests for round value detection."""

    def test_detects_round_values_in_deductions(self):
        """Test detection of suspiciously round deduction values."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("1000")),
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("2000")),
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("5000")),
                Deducao(tipo=TipoDeducao.DESPESAS_EDUCACAO, valor=Decimal("3000")),
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # All 4 values are round, should trigger warning
        round_warnings = [w for w in warnings if "redondos" in w.mensagem.lower()]
        assert len(round_warnings) > 0

    def test_no_warning_for_non_round_values(self):
        """Test that non-round values don't trigger warnings."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("1234.56")),
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("7891.23")),
                Deducao(tipo=TipoDeducao.DESPESAS_EDUCACAO, valor=Decimal("3456.78")),
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        round_warnings = [w for w in warnings if "redondos" in w.mensagem.lower()]
        assert len(round_warnings) == 0


class TestVehicleDepreciation:
    """Tests for vehicle depreciation detection."""

    def test_detects_low_depreciation(self):
        """Test detection of vehicles with below-expected depreciation."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.VEICULOS,
                    codigo="21",  # 21 = Vehicle code (not 01)
                    discriminacao="Automóvel Honda Civic",
                    situacao_anterior=Decimal("100000"),
                    situacao_atual=Decimal("99000"),  # Only 1% depreciation
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        dep_warnings = [w for w in warnings if "depreciação" in w.mensagem.lower()]
        assert len(dep_warnings) > 0
        assert "abaixo" in dep_warnings[0].mensagem.lower()

    def test_detects_high_depreciation(self):
        """Test detection of vehicles with above-expected depreciation."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.VEICULOS,
                    codigo="21",  # 21 = Vehicle code (not 01)
                    discriminacao="Carro Usado",
                    situacao_anterior=Decimal("100000"),
                    situacao_atual=Decimal("50000"),  # 50% depreciation
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        dep_warnings = [w for w in warnings if "depreciação" in w.mensagem.lower()]
        assert len(dep_warnings) > 0
        assert "acima" in dep_warnings[0].mensagem.lower()

    def test_normal_depreciation_no_warning(self):
        """Test that normal depreciation doesn't trigger warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.VEICULOS,
                    codigo="21",  # 21 = Vehicle code (not 01)
                    discriminacao="Veículo XYZ",
                    situacao_anterior=Decimal("100000"),
                    situacao_atual=Decimal("90000"),  # 10% depreciation - normal
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        dep_warnings = [w for w in warnings if "depreciação" in w.mensagem.lower()]
        assert len(dep_warnings) == 0


class TestCPFCNPJValidation:
    """Tests for CPF/CNPJ validation in declarations."""

    def test_detects_invalid_taxpayer_cpf(self):
        """Test detection of invalid taxpayer CPF."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="11111111111", nome="Test"),  # Invalid CPF
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        cpf_issues = [i for i in inconsistencies if i.tipo == InconsistencyType.CPF_INVALIDO]
        assert len(cpf_issues) > 0
        assert cpf_issues[0].risco == RiskLevel.CRITICAL

    def test_detects_invalid_dependent_cpf(self):
        """Test detection of invalid dependent CPF."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),  # Valid CPF
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="12345678901",  # Invalid CPF
                    nome="Filho Test",
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        cpf_issues = [i for i in inconsistencies if i.tipo == InconsistencyType.CPF_INVALIDO]
        assert len(cpf_issues) > 0
        assert "dependente" in cpf_issues[0].descricao.lower()

    def test_detects_invalid_payment_source_cnpj(self):
        """Test detection of invalid payment source CNPJ."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                    fonte_pagadora=FontePagadora(
                        cnpj_cpf="11111111111111",  # Invalid CNPJ
                        nome="Empresa XYZ",
                    ),
                    valor_anual=Decimal("100000"),
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        cnpj_issues = [i for i in inconsistencies if i.tipo == InconsistencyType.CNPJ_INVALIDO]
        assert len(cnpj_issues) > 0

    def test_valid_cpf_cnpj_no_issues(self):
        """Test that valid CPF/CNPJ don't trigger issues."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),  # Valid CPF
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11144477735",  # Valid CPF
                    nome="Filho Test",
                )
            ],
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                    fonte_pagadora=FontePagadora(
                        cnpj_cpf="11222333000181",  # Valid CNPJ
                        nome="Empresa XYZ",
                    ),
                    valor_anual=Decimal("100000"),
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        cpf_cnpj_issues = [
            i for i in inconsistencies
            if i.tipo in (InconsistencyType.CPF_INVALIDO, InconsistencyType.CNPJ_INVALIDO)
        ]
        assert len(cpf_cnpj_issues) == 0


class TestMedicalExpensePatterns:
    """Tests for medical expense pattern detection."""

    def test_detects_concentrated_medical_expenses(self):
        """Test detection of medical expenses concentrated in one provider."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("8000"),
                    cnpj_prestador="11222333000181",
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("1000"),
                    cnpj_prestador="22333444000199",
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("1000"),
                    cnpj_prestador="33444555000188",
                ),
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # 80% in one provider should trigger warning
        conc_warnings = [w for w in warnings if "concentradas" in w.mensagem.lower()]
        assert len(conc_warnings) > 0

    def test_detects_identical_medical_expenses(self):
        """Test detection of multiple identical medical expense values."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("500")),
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("500")),
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("500")),
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # 3 identical values should trigger warning
        identical_warnings = [w for w in warnings if "idêntico" in w.mensagem.lower()]
        assert len(identical_warnings) > 0


class TestPropertyWithoutRental:
    """Tests for property without rental income detection."""

    def test_detects_multiple_properties_no_rental(self):
        """Test detection of multiple properties without rental income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="11",  # 11 = Apartamento (real estate code)
                    discriminacao="Apartamento 1",
                    situacao_anterior=Decimal("300000"),
                    situacao_atual=Decimal("300000"),
                ),
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="12",  # 12 = Casa (real estate code)
                    discriminacao="Casa 1",
                    situacao_anterior=Decimal("400000"),
                    situacao_atual=Decimal("400000"),
                ),
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Multiple properties without rental income should trigger informative warning
        rental_warnings = [w for w in warnings if "aluguel" in w.mensagem.lower()]
        assert len(rental_warnings) > 0
        assert rental_warnings[0].informativo is True


class TestPurchasesWithoutBacking:
    """Tests for purchase without backing detection."""

    def test_detects_large_purchase_without_resources(self):
        """Test detection of large asset acquisition vs income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("80000"),
            total_rendimentos_isentos=Decimal("0"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.VEICULOS,
                    codigo="01",
                    discriminacao="Carro novo",
                    situacao_anterior=Decimal("0"),  # New purchase
                    situacao_atual=Decimal("100000"),  # 125% of income
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Large purchase should trigger informative warning
        purchase_warnings = [w for w in warnings if "aquisição" in w.mensagem.lower()]
        assert len(purchase_warnings) > 0


class TestDividendsVsParticipation:
    """Tests for dividends vs equity participation detection."""

    def test_detects_high_dividends_vs_participation(self):
        """Test detection of high dividends relative to equity participation."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.PARTICIPACOES_SOCIETARIAS,
                    codigo="31",
                    discriminacao="Quotas Empresa X",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("50000"),
                )
            ],
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.LUCROS_DIVIDENDOS,
                    valor_anual=Decimal("30000"),  # 60% of participation
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # 60% dividends vs participation should trigger warning
        div_warnings = [w for w in warnings if "dividendos" in w.mensagem.lower()]
        assert len(div_warnings) > 0


class TestStatisticalPatterns:
    """Tests for statistical pattern detection."""

    def test_detects_deduction_outliers(self):
        """Test detection of outlier values in deductions."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("1000")),
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("1200")),
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("800")),
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("1100")),
                Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=Decimal("50000")),  # Outlier
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        outlier_warnings = [w for w in warnings if "outlier" in w.mensagem.lower()]
        assert len(outlier_warnings) > 0


class TestHighValueMedicalExpensePF:
    """Tests for high-value medical expense with individual providers (PF)."""

    def test_detects_high_medical_expense_with_cpf(self):
        """Test detection of high-value medical expense paid to individual (CPF)."""
        from datetime import date

        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("7500"),  # > R$ 5000 threshold
                    cpf_prestador="11144477735",  # Valid CPF
                    nome_prestador="Dr. Fulano",
                ),
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # High value PF expense should trigger warning
        pf_warnings = [w for w in warnings if "pessoa física" in w.mensagem.lower()]
        assert len(pf_warnings) > 0
        # Check value is mentioned (format may vary by locale)
        assert "7,500" in pf_warnings[0].mensagem or "7.500" in pf_warnings[0].mensagem or "7500" in pf_warnings[0].mensagem

    def test_no_warning_for_low_value_pf_expense(self):
        """Test that low-value PF expenses don't trigger warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("3000"),  # Below R$ 5000 threshold
                    cpf_prestador="11144477735",
                    nome_prestador="Dr. Fulano",
                ),
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        pf_warnings = [w for w in warnings if "pessoa física" in w.mensagem.lower()]
        assert len(pf_warnings) == 0

    def test_no_warning_for_cnpj_provider(self):
        """Test that high-value expenses with CNPJ don't trigger this warning."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("10000"),  # High value
                    cnpj_prestador="11222333000181",  # CNPJ, not CPF
                    nome_prestador="Clínica ABC",
                ),
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        pf_warnings = [w for w in warnings if "pessoa física" in w.mensagem.lower()]
        assert len(pf_warnings) == 0


class TestDependentAgeValidation:
    """Tests for dependent age validation."""

    def test_detects_overage_child_dependent(self):
        """Test detection of child dependent over 21 years old."""
        from datetime import date

        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11144477735",
                    nome="João Silva",
                    data_nascimento=date(2000, 1, 1),  # ~25 years old (over 21)
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        age_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL
        ]
        assert len(age_issues) > 0
        assert age_issues[0].risco == RiskLevel.HIGH
        assert "21" in age_issues[0].descricao

    def test_detects_overage_university_dependent(self):
        """Test detection of university dependent over 24 years old."""
        from datetime import date

        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_UNIVERSITARIO,
                    cpf="11144477735",
                    nome="Maria Silva",
                    data_nascimento=date(1998, 1, 1),  # ~28 years old (over 24)
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        age_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL
        ]
        assert len(age_issues) > 0
        assert "24" in age_issues[0].descricao or "universitário" in age_issues[0].descricao.lower()

    def test_no_issue_for_valid_age_child(self):
        """Test that valid age child dependent doesn't trigger issue."""
        from datetime import date

        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11144477735",
                    nome="Pedro Silva",
                    data_nascimento=date(2010, 1, 1),  # ~15 years old (valid)
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        age_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL
        ]
        assert len(age_issues) == 0

    def test_no_age_limit_for_incapacitated_dependent(self):
        """Test that incapacitated dependent has no age limit."""
        from datetime import date

        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_INCAPAZ,
                    cpf="11144477735",
                    nome="Carlos Silva",
                    data_nascimento=date(1980, 1, 1),  # ~45 years old (valid for incapaz)
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        age_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL
        ]
        assert len(age_issues) == 0

    def test_no_validation_without_birth_date(self):
        """Test that no validation occurs when birth date is missing."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="11144477735",
                    nome="Ana Silva",
                    # No birth date provided
                )
            ],
        )

        analyzer = PatternAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        age_issues = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL
        ]
        assert len(age_issues) == 0


class TestAnalyzePatternsFunction:
    """Tests for convenience function."""

    def test_analyze_patterns_returns_tuple(self):
        """Test that analyze_patterns returns correct tuple."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        result = analyze_patterns(decl)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)  # inconsistencies
        assert isinstance(result[1], list)  # warnings
