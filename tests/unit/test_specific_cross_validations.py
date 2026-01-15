"""Tests for specific cross-validation analyzer."""

from datetime import date
from decimal import Decimal

from irpf_analyzer.core.analyzers.specific_cross_validations import (
    SpecificCrossValidationAnalyzer,
    analyze_specific_cross_validations,
)
from irpf_analyzer.core.models import (
    BemDireito,
    Declaration,
    GrupoBem,
    TipoDeclaracao,
)
from irpf_analyzer.core.models.analysis import InconsistencyType
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.deductions import Deducao
from irpf_analyzer.core.models.dependents import Dependente
from irpf_analyzer.core.models.enums import TipoDeducao, TipoDependente


def create_declaration(
    cpf: str = "52998224725",
    birth_date: date | None = None,
    rendimentos_tributaveis: Decimal = Decimal("100000"),
    deducoes: list[Deducao] | None = None,
    bens_direitos: list[BemDireito] | None = None,
    dependentes: list[Dependente] | None = None,
) -> Declaration:
    """Helper to create a test declaration."""
    return Declaration(
        contribuinte=Contribuinte(
            cpf=cpf,
            nome="Test User",
            data_nascimento=birth_date,
        ),
        ano_exercicio=2025,
        ano_calendario=2024,
        tipo_declaracao=TipoDeclaracao.COMPLETA,
        total_rendimentos_tributaveis=rendimentos_tributaveis,
        deducoes=deducoes or [],
        bens_direitos=bens_direitos or [],
        dependentes=dependentes or [],
    )


class TestAgeBasedMedicalThresholds:
    """Tests for medical expense thresholds."""

    def test_thresholds_defined_for_all_ages(self):
        """Test that thresholds cover all adult ages."""
        analyzer = SpecificCrossValidationAnalyzer
        ages_covered = set()
        for t in analyzer.MEDICAL_THRESHOLDS:
            for age in range(t.min_age, t.max_age + 1):
                ages_covered.add(age)

        # All ages from 18 to 120 should be covered
        for age in range(18, 121):
            assert age in ages_covered, f"Age {age} not covered"

    def test_thresholds_have_valid_ratios(self):
        """Test that thresholds have sensible ratio progression."""
        for t in SpecificCrossValidationAnalyzer.MEDICAL_THRESHOLDS:
            assert t.expected_ratio < t.high_ratio < t.critical_ratio
            assert t.expected_ratio > 0
            assert t.critical_ratio < 1  # Should be less than 100%

    def test_older_age_higher_thresholds(self):
        """Test that older age groups have higher thresholds."""
        thresholds = SpecificCrossValidationAnalyzer.MEDICAL_THRESHOLDS
        for i in range(1, len(thresholds)):
            assert thresholds[i].expected_ratio >= thresholds[i - 1].expected_ratio


class TestEducationLevels:
    """Tests for education level definitions."""

    def test_levels_cover_all_school_ages(self):
        """Test that education levels cover typical school ages."""
        levels = SpecificCrossValidationAnalyzer.EDUCATION_LEVELS
        ages_covered = set()
        for level in levels:
            for age in range(level.min_age, level.max_age + 1):
                ages_covered.add(age)

        # Ages 0-30 should be covered (nursery through university)
        for age in range(0, 31):
            assert age in ages_covered, f"Age {age} not covered"

    def test_levels_have_valid_costs(self):
        """Test that levels have positive costs."""
        for level in SpecificCrossValidationAnalyzer.EDUCATION_LEVELS:
            assert level.typical_annual_cost > 0


class TestMedicalExpensesVsAge:
    """Tests for medical expenses vs age validation."""

    def test_young_taxpayer_normal_expenses(self):
        """Test young taxpayer with normal medical expenses passes."""
        decl = create_declaration(
            birth_date=date(1995, 1, 15),  # ~30 years old
            rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("5000"),  # 5% of income
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(inconsistencies) == 0
        assert len(warnings) == 0

    def test_young_taxpayer_high_expenses_warning(self):
        """Test young taxpayer with high medical expenses triggers warning."""
        decl = create_declaration(
            birth_date=date(1996, 1, 15),  # ~29 years old
            rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("12000"),  # 12% of income
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(warnings) >= 1
        assert any("acima do esperado" in w.mensagem for w in warnings)

    def test_young_taxpayer_critical_expenses_inconsistency(self):
        """Test young taxpayer with critical medical expenses triggers inconsistency."""
        decl = create_declaration(
            birth_date=date(1996, 1, 15),  # ~29 years old
            rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("25000"),  # 25% of income
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(inconsistencies) >= 1
        assert any(i.tipo == InconsistencyType.DESPESAS_MEDICAS_ALTAS for i in inconsistencies)

    def test_elderly_taxpayer_high_expenses_normal(self):
        """Test elderly taxpayer with high medical expenses is normal."""
        decl = create_declaration(
            birth_date=date(1945, 1, 15),  # ~80 years old
            rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("35000"),  # 35% of income
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not trigger inconsistency for elderly
        med_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DESPESAS_MEDICAS_ALTAS
        ]
        assert len(med_inconsistencies) == 0

    def test_no_birth_date_skips_validation(self):
        """Test that missing birth date skips validation."""
        decl = create_declaration(
            birth_date=None,
            rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("50000"),
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not trigger medical age validation
        med_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DESPESAS_MEDICAS_ALTAS
        ]
        assert len(med_inconsistencies) == 0

    def test_zero_income_skips_validation(self):
        """Test that zero income skips validation."""
        decl = create_declaration(
            birth_date=date(1996, 1, 15),
            rendimentos_tributaveis=Decimal("0"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("10000"),
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        med_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DESPESAS_MEDICAS_ALTAS
        ]
        assert len(med_inconsistencies) == 0

    def test_middle_aged_taxpayer_moderate_expenses(self):
        """Test middle-aged taxpayer with moderate expenses."""
        decl = create_declaration(
            birth_date=date(1975, 6, 15),  # ~50 years old
            rendimentos_tributaveis=Decimal("150000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("15000"),  # 10% of income
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Within normal range for middle-aged
        med_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DESPESAS_MEDICAS_ALTAS
        ]
        assert len(med_inconsistencies) == 0


class TestEducationVsDependentAge:
    """Tests for education expenses vs dependent age validation."""

    def test_appropriate_education_expense(self):
        """Test appropriate education expense for dependent age."""
        decl = create_declaration(
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="12345678901",
                    nome="Child",
                    data_nascimento=date(2010, 1, 1),  # ~15 years old
                ),
            ],
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_EDUCACAO,
                    valor=Decimal("15000"),
                    beneficiario_cpf="12345678901",
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # No age-related inconsistencies
        edu_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL
        ]
        assert len(edu_inconsistencies) == 0

    def test_university_expense_for_child_inconsistency(self):
        """Test university-level expense for young child triggers inconsistency."""
        decl = create_declaration(
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="12345678901",
                    nome="Young Child",
                    data_nascimento=date(2016, 1, 1),  # ~9 years old
                ),
            ],
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_EDUCACAO,
                    valor=Decimal("35000"),  # High value typical of university
                    beneficiario_cpf="12345678901",
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(inconsistencies) >= 1
        assert any(i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL for i in inconsistencies)

    def test_high_expense_young_child_warning(self):
        """Test high education expense for young child triggers warning."""
        decl = create_declaration(
            dependentes=[
                Dependente(
                    tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
                    cpf="12345678901",
                    nome="Toddler",
                    data_nascimento=date(2022, 6, 1),  # ~3 years old
                ),
            ],
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_EDUCACAO,
                    valor=Decimal("26000"),  # High for nursery
                    beneficiario_cpf="12345678901",
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(warnings) >= 1
        assert any("elevada" in w.mensagem.lower() or "verifique" in w.mensagem.lower() for w in warnings)

    def test_education_without_dependent_warning(self):
        """Test education expense for non-dependent triggers warning."""
        decl = create_declaration(
            dependentes=[],  # No dependents
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_EDUCACAO,
                    valor=Decimal("10000"),
                    beneficiario_cpf="98765432109",  # Not a dependent
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(warnings) >= 1
        assert any("não consta como dependente" in w.mensagem for w in warnings)

    def test_titular_education_young_taxpayer_inconsistency(self):
        """Test titular education with very young taxpayer is inconsistent."""
        decl = create_declaration(
            birth_date=date(2012, 1, 15),  # ~13 years old
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_EDUCACAO,
                    valor=Decimal("8000"),
                    beneficiario_cpf=None,  # Titular
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(inconsistencies) >= 1
        assert any(i.tipo == InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL for i in inconsistencies)

    def test_elderly_dependent_education_warning(self):
        """Test education expense for elderly dependent triggers informative warning."""
        decl = create_declaration(
            dependentes=[
                Dependente(
                    tipo=TipoDependente.PAIS_AVOS_BISAVOS,
                    cpf="12345678901",
                    nome="Grandparent",
                    data_nascimento=date(1950, 1, 1),  # ~75 years old
                ),
            ],
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_EDUCACAO,
                    valor=Decimal("5000"),
                    beneficiario_cpf="12345678901",
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should trigger informative warning about unusual case
        assert len(warnings) >= 1


class TestRealEstateAppreciation:
    """Tests for real estate appreciation validation."""

    def test_normal_appreciation_passes(self):
        """Test that normal appreciation passes validation."""
        decl = create_declaration(
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento Centro",
                    situacao_anterior=Decimal("500000"),
                    situacao_atual=Decimal("530000"),  # 6% appreciation
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        appreciation_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.IMOVEL_SUBAVALIADO
        ]
        assert len(appreciation_inconsistencies) == 0

    def test_high_appreciation_warning(self):
        """Test that high appreciation triggers warning."""
        decl = create_declaration(
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento Centro",
                    situacao_anterior=Decimal("500000"),
                    situacao_atual=Decimal("560000"),  # 12% appreciation
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(warnings) >= 1
        assert any("valorização" in w.mensagem.lower() for w in warnings)

    def test_critical_appreciation_inconsistency(self):
        """Test that critical appreciation triggers inconsistency."""
        decl = create_declaration(
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento Centro sem benfeitorias declaradas",
                    situacao_anterior=Decimal("500000"),
                    situacao_atual=Decimal("650000"),  # 30% appreciation
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert len(inconsistencies) >= 1
        assert any(i.tipo == InconsistencyType.IMOVEL_SUBAVALIADO for i in inconsistencies)

    def test_depreciation_no_issue(self):
        """Test that depreciation (lower value) causes no issue."""
        decl = create_declaration(
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento Centro",
                    situacao_anterior=Decimal("500000"),
                    situacao_atual=Decimal("480000"),  # Depreciation
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        appreciation_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.IMOVEL_SUBAVALIADO
        ]
        assert len(appreciation_inconsistencies) == 0

    def test_small_property_skipped(self):
        """Test that small value properties are skipped."""
        decl = create_declaration(
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Terreno rural pequeno",
                    situacao_anterior=Decimal("50000"),  # Below threshold
                    situacao_atual=Decimal("80000"),  # 60% appreciation
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        appreciation_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.IMOVEL_SUBAVALIADO
        ]
        assert len(appreciation_inconsistencies) == 0

    def test_non_real_estate_skipped(self):
        """Test that non-real estate assets are skipped."""
        decl = create_declaration(
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.VEICULOS,
                    codigo="21",
                    discriminacao="Carro",
                    situacao_anterior=Decimal("200000"),
                    situacao_atual=Decimal("300000"),  # 50% appreciation
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Vehicle appreciation doesn't trigger real estate check
        appreciation_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.IMOVEL_SUBAVALIADO
        ]
        assert len(appreciation_inconsistencies) == 0


class TestSpouseConsistency:
    """Tests for spouse declaration cross-validation."""

    def test_no_spouse_no_validation(self):
        """Test that no spouse declaration skips validation."""
        decl = create_declaration()

        analyzer = SpecificCrossValidationAnalyzer(decl, spouse_declaration=None)
        inconsistencies, warnings = analyzer.analyze()

        # No spouse-related issues
        duplicate_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_DUPLICADO
        ]
        assert len(duplicate_inconsistencies) == 0

    def test_duplicate_dependent_inconsistency(self):
        """Test that duplicate dependent triggers inconsistency."""
        child = Dependente(
            tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
            cpf="12345678901",
            nome="Shared Child",
            data_nascimento=date(2015, 1, 1),
        )

        decl1 = create_declaration(
            cpf="52998224725",
            dependentes=[child],
        )

        decl2 = create_declaration(
            cpf="11122233344",
            dependentes=[child],  # Same child
        )

        analyzer = SpecificCrossValidationAnalyzer(decl1, spouse_declaration=decl2)
        inconsistencies, warnings = analyzer.analyze()

        assert len(inconsistencies) >= 1
        assert any(i.tipo == InconsistencyType.DEPENDENTE_DUPLICADO for i in inconsistencies)

    def test_different_dependents_no_issue(self):
        """Test that different dependents don't trigger issues."""
        child1 = Dependente(
            tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
            cpf="12345678901",
            nome="Child 1",
            data_nascimento=date(2015, 1, 1),
        )

        child2 = Dependente(
            tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
            cpf="98765432109",
            nome="Child 2",
            data_nascimento=date(2017, 1, 1),
        )

        decl1 = create_declaration(
            cpf="52998224725",
            dependentes=[child1],
        )

        decl2 = create_declaration(
            cpf="11122233344",
            dependentes=[child2],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl1, spouse_declaration=decl2)
        inconsistencies, warnings = analyzer.analyze()

        duplicate_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DEPENDENTE_DUPLICADO
        ]
        assert len(duplicate_inconsistencies) == 0

    def test_common_medical_providers_warning(self):
        """Test that common medical providers trigger warning."""
        decl1 = create_declaration(
            cpf="52998224725",
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("5000"),
                    cnpj_prestador="12345678000190",
                ),
            ],
        )

        decl2 = create_declaration(
            cpf="11122233344",
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("3000"),
                    cnpj_prestador="12345678000190",  # Same provider
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl1, spouse_declaration=decl2)
        inconsistencies, warnings = analyzer.analyze()

        assert len(warnings) >= 1
        assert any("prestadores" in w.mensagem.lower() for w in warnings)

    def test_shared_property_different_values_warning(self):
        """Test that shared property with different values triggers warning."""
        property1 = BemDireito(
            grupo=GrupoBem.IMOVEIS,
            codigo="01",
            discriminacao="Apartamento Centro conjugal",
            situacao_anterior=Decimal("500000"),
            situacao_atual=Decimal("500000"),
        )

        property2 = BemDireito(
            grupo=GrupoBem.IMOVEIS,
            codigo="01",
            discriminacao="Apartamento Centro conjugal",
            situacao_anterior=Decimal("500000"),
            situacao_atual=Decimal("600000"),  # Different value
        )

        decl1 = create_declaration(
            cpf="52998224725",
            bens_direitos=[property1],
        )

        decl2 = create_declaration(
            cpf="11122233344",
            bens_direitos=[property2],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl1, spouse_declaration=decl2)
        inconsistencies, warnings = analyzer.analyze()

        assert len(warnings) >= 1
        assert any("valores diferentes" in w.mensagem for w in warnings)


class TestConvenienceFunction:
    """Tests for the analyze_specific_cross_validations convenience function."""

    def test_convenience_function_returns_tuple(self):
        """Test that convenience function returns correct types."""
        decl = create_declaration()
        result = analyze_specific_cross_validations(decl)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], list)

    def test_convenience_function_with_spouse(self):
        """Test convenience function with spouse declaration."""
        decl1 = create_declaration(cpf="52998224725")
        decl2 = create_declaration(cpf="11122233344")

        result = analyze_specific_cross_validations(decl1, spouse_declaration=decl2)

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_convenience_function_matches_class(self):
        """Test that convenience function matches class results."""
        decl = create_declaration(
            birth_date=date(1996, 1, 15),
            rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("25000"),
                ),
            ],
        )

        # Use class
        analyzer = SpecificCrossValidationAnalyzer(decl)
        class_result = analyzer.analyze()

        # Use convenience function
        func_result = analyze_specific_cross_validations(decl)

        assert len(class_result[0]) == len(func_result[0])
        assert len(class_result[1]) == len(func_result[1])


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_declaration(self):
        """Test analyzer handles empty declaration."""
        decl = create_declaration()
        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        assert isinstance(inconsistencies, list)
        assert isinstance(warnings, list)

    def test_multiple_issues(self):
        """Test analyzer handles multiple issues."""
        child = Dependente(
            tipo=TipoDependente.FILHO_ENTEADO_ATE_21,
            cpf="12345678901",
            nome="Child",
            data_nascimento=date(2022, 1, 1),  # ~3 years old
        )

        decl = create_declaration(
            birth_date=date(1996, 1, 15),  # ~29 years old
            rendimentos_tributaveis=Decimal("100000"),
            dependentes=[child],
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("25000"),  # Critical for young taxpayer
                ),
                Deducao(
                    tipo=TipoDeducao.DESPESAS_EDUCACAO,
                    valor=Decimal("35000"),  # High for young child
                    beneficiario_cpf="12345678901",
                ),
            ],
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartment high appreciation",
                    situacao_anterior=Decimal("500000"),
                    situacao_atual=Decimal("700000"),  # 40% appreciation
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should have multiple issues
        assert len(inconsistencies) >= 2  # Medical + real estate

    def test_boundary_age_values(self):
        """Test boundary age values for thresholds."""
        # Test exact boundary at age 30/31
        # In 2026, someone born in 1996 is 30, born in 1995 is 31
        for birth_year, expected_threshold_min in [(1996, 18), (1994, 31)]:
            decl = create_declaration(
                birth_date=date(birth_year, 1, 15),
                rendimentos_tributaveis=Decimal("100000"),
            )
            analyzer = SpecificCrossValidationAnalyzer(decl)
            threshold = analyzer._get_medical_threshold(analyzer._taxpayer_age)
            assert threshold is not None
            assert threshold.min_age == expected_threshold_min

    def test_exact_threshold_ratio(self):
        """Test that exact threshold ratio triggers correctly."""
        # Create declaration at exactly high_ratio boundary
        decl = create_declaration(
            birth_date=date(1996, 1, 15),  # ~29 years old (18-30 bracket)
            rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("10000"),  # Exactly 10% = high_ratio for 18-30
                ),
            ],
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # At exactly high_ratio, should trigger warning (>= check)
        assert len(warnings) >= 1

    def test_zero_medical_expenses_no_validation(self):
        """Test that zero medical expenses skips validation."""
        decl = create_declaration(
            birth_date=date(1996, 1, 15),
            rendimentos_tributaveis=Decimal("100000"),
            deducoes=[],  # No medical expenses
        )

        analyzer = SpecificCrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        med_inconsistencies = [
            i for i in inconsistencies
            if i.tipo == InconsistencyType.DESPESAS_MEDICAS_ALTAS
        ]
        assert len(med_inconsistencies) == 0


class TestImportFromModule:
    """Tests for module imports."""

    def test_import_from_analyzers_init(self):
        """Test that analyzer can be imported from analyzers package."""
        from irpf_analyzer.core.analyzers import (
            SpecificCrossValidationAnalyzer,
            analyze_specific_cross_validations,
        )

        assert SpecificCrossValidationAnalyzer is not None
        assert analyze_specific_cross_validations is not None
