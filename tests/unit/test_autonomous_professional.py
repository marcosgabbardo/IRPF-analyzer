"""Tests for autonomous professional analyzer."""

from decimal import Decimal

from irpf_analyzer.core.analyzers.autonomous_professional import (
    AutonomousProfessionalAnalyzer,
    TaxRegime,
    analyze_autonomous_professional,
)
from irpf_analyzer.core.models import (
    Declaration,
    TipoDeclaracao,
)
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.deductions import Deducao
from irpf_analyzer.core.models.enums import TipoDeducao, TipoRendimento
from irpf_analyzer.core.models.income import Rendimento


def create_declaration(
    cpf: str = "52998224725",
    rendimentos_tributaveis: Decimal = Decimal("100000"),
    rendimentos: list[Rendimento] | None = None,
    deducoes: list[Deducao] | None = None,
) -> Declaration:
    """Helper to create a test declaration."""
    return Declaration(
        contribuinte=Contribuinte(
            cpf=cpf,
            nome="Test User",
        ),
        ano_exercicio=2025,
        ano_calendario=2024,
        tipo_declaracao=TipoDeclaracao.COMPLETA,
        total_rendimentos_tributaveis=rendimentos_tributaveis,
        rendimentos=rendimentos or [],
        deducoes=deducoes or [],
    )


def create_autonomous_income(value: Decimal) -> Rendimento:
    """Create autonomous income rendimento."""
    return Rendimento(
        tipo=TipoRendimento.TRABALHO_NAO_ASSALARIADO,
        valor_anual=value,
    )


def create_livro_caixa_deduction(value: Decimal, descricao: str = "") -> Deducao:
    """Create livro-caixa deduction."""
    return Deducao(
        tipo=TipoDeducao.LIVRO_CAIXA,
        valor=value,
        descricao=descricao,
    )


class TestDeductibleCategories:
    """Tests for deductible expense categories."""

    def test_categories_defined(self):
        """Test that categories are properly defined."""
        categories = AutonomousProfessionalAnalyzer.DEDUCTIBLE_CATEGORIES
        assert len(categories) >= 5

    def test_categories_have_examples(self):
        """Test that all categories have examples."""
        for category in AutonomousProfessionalAnalyzer.DEDUCTIBLE_CATEGORIES:
            assert len(category.examples) >= 1

    def test_categories_have_valid_ratios(self):
        """Test that category ratios are reasonable."""
        total_ratio = Decimal("0")
        for category in AutonomousProfessionalAnalyzer.DEDUCTIBLE_CATEGORIES:
            assert Decimal("0") < category.typical_ratio <= Decimal("0.20")
            total_ratio += category.typical_ratio

        # Total should be reasonable (not more than 80%)
        assert total_ratio <= Decimal("0.80")


class TestTaxRegimeEnum:
    """Tests for TaxRegime enum."""

    def test_all_regimes_defined(self):
        """Test that all regimes are defined."""
        assert TaxRegime.AUTONOMO_PF.value == "autonomo_pf"
        assert TaxRegime.SIMPLES_NACIONAL.value == "simples_nacional"
        assert TaxRegime.LUCRO_PRESUMIDO.value == "lucro_presumido"


class TestNoAutonomousIncome:
    """Tests when there's no autonomous income."""

    def test_no_suggestions_without_autonomous_income(self):
        """Test that no suggestions are generated without autonomous income."""
        decl = create_declaration(
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                    valor_anual=Decimal("100000"),
                ),
            ],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        assert len(suggestions) == 0
        assert len(warnings) == 0


class TestLivroCaixaOptimization:
    """Tests for livro-caixa optimization."""

    def test_no_livro_caixa_suggests_using_it(self):
        """Test suggestion to use livro-caixa when not using it."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("120000"),
            rendimentos=[create_autonomous_income(Decimal("120000"))],
            deducoes=[],  # No livro-caixa
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        livro_caixa_suggestions = [
            s for s in suggestions
            if "livro-caixa" in s.titulo.lower() or "livro-caixa" in s.descricao.lower()
        ]
        assert len(livro_caixa_suggestions) >= 1
        assert livro_caixa_suggestions[0].economia_potencial > 0

    def test_low_livro_caixa_ratio_suggests_review(self):
        """Test suggestion to review when livro-caixa ratio is low."""
        autonomous_income = Decimal("150000")
        livro_caixa = Decimal("10000")  # Only 6.7%

        decl = create_declaration(
            rendimentos_tributaveis=Decimal("140000"),
            rendimentos=[create_autonomous_income(autonomous_income)],
            deducoes=[create_livro_caixa_deduction(livro_caixa, "Aluguel consultório")],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        review_suggestions = [
            s for s in suggestions
            if "revise" in s.descricao.lower() or "livro-caixa" in s.titulo.lower()
        ]
        assert len(review_suggestions) >= 1

    def test_adequate_livro_caixa_no_warning(self):
        """Test no warning when livro-caixa is adequate."""
        autonomous_income = Decimal("100000")
        livro_caixa = Decimal("30000")  # 30%

        decl = create_declaration(
            rendimentos_tributaveis=Decimal("70000"),
            rendimentos=[create_autonomous_income(autonomous_income)],
            deducoes=[create_livro_caixa_deduction(livro_caixa, "Diversas despesas")],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should not warn about livro-caixa ratio
        ratio_warnings = [
            w for w in warnings
            if "livro-caixa representa" in w.mensagem.lower()
        ]
        assert len(ratio_warnings) == 0

    def test_high_livro_caixa_ratio_warning(self):
        """Test warning when livro-caixa ratio is suspiciously high."""
        autonomous_income = Decimal("100000")
        livro_caixa = Decimal("85000")  # 85%

        decl = create_declaration(
            rendimentos_tributaveis=Decimal("15000"),
            rendimentos=[create_autonomous_income(autonomous_income)],
            deducoes=[create_livro_caixa_deduction(livro_caixa, "Muitas despesas")],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        high_ratio_warnings = [
            w for w in warnings
            if "livro-caixa representa" in w.mensagem.lower()
        ]
        assert len(high_ratio_warnings) >= 1


class TestDeductibleExpensesSuggestions:
    """Tests for missing deductible expenses suggestions."""

    def test_suggests_missing_categories(self):
        """Test suggestion of missing deductible categories."""
        autonomous_income = Decimal("120000")
        livro_caixa = Decimal("15000")

        decl = create_declaration(
            rendimentos_tributaveis=Decimal("105000"),
            rendimentos=[create_autonomous_income(autonomous_income)],
            deducoes=[
                create_livro_caixa_deduction(livro_caixa, "Aluguel consultório"),
            ],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        missing_suggestions = [
            s for s in suggestions
            if "não identificadas" in s.descricao.lower() or "categorias" in s.descricao.lower()
        ]
        assert len(missing_suggestions) >= 1

    def test_no_missing_categories_when_comprehensive(self):
        """Test no missing categories suggestion when comprehensive."""
        autonomous_income = Decimal("120000")

        # Create deductions covering most categories
        deducoes = [
            create_livro_caixa_deduction(Decimal("15000"), "Aluguel consultório"),
            create_livro_caixa_deduction(Decimal("5000"), "Material escritório"),
            create_livro_caixa_deduction(Decimal("3000"), "Telefone Internet"),
            create_livro_caixa_deduction(Decimal("5000"), "Combustível deslocamento"),
            create_livro_caixa_deduction(Decimal("8000"), "Contador secretária"),
            create_livro_caixa_deduction(Decimal("2000"), "Cursos congressos"),
            create_livro_caixa_deduction(Decimal("2000"), "Computador manutenção"),
        ]

        decl = create_declaration(
            rendimentos_tributaveis=Decimal("80000"),
            rendimentos=[create_autonomous_income(autonomous_income)],
            deducoes=deducoes,
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should have fewer missing category suggestions
        missing_suggestions = [
            s for s in suggestions
            if "não identificadas" in s.titulo.lower()
        ]
        assert len(missing_suggestions) <= 1


class TestTaxRegimeComparison:
    """Tests for tax regime comparison."""

    def test_low_income_no_regime_comparison(self):
        """Test no regime comparison for low income."""
        autonomous_income = Decimal("40000")  # Below threshold

        decl = create_declaration(
            rendimentos_tributaveis=autonomous_income,
            rendimentos=[create_autonomous_income(autonomous_income)],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        regime_suggestions = [
            s for s in suggestions
            if "regime" in s.titulo.lower() or "simples" in s.titulo.lower()
        ]
        # Should not suggest regime change for low income
        regime_suggestions_recommend = [
            s for s in regime_suggestions
            if "considere" in s.titulo.lower()
        ]
        assert len(regime_suggestions_recommend) == 0

    def test_medium_income_suggests_simples(self):
        """Test regime comparison suggests Simples for medium income."""
        autonomous_income = Decimal("120000")

        decl = create_declaration(
            rendimentos_tributaveis=autonomous_income,
            rendimentos=[create_autonomous_income(autonomous_income)],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should have regime comparison
        regime_suggestions = [
            s for s in suggestions
            if "regime" in s.titulo.lower() or "comparativo" in s.titulo.lower()
        ]
        assert len(regime_suggestions) >= 1

    def test_high_income_regime_comparison(self):
        """Test regime comparison for high income."""
        autonomous_income = Decimal("500000")

        decl = create_declaration(
            rendimentos_tributaveis=autonomous_income,
            rendimentos=[create_autonomous_income(autonomous_income)],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should have detailed regime comparison
        comparativo_suggestions = [
            s for s in suggestions
            if "comparativo" in s.titulo.lower()
        ]
        assert len(comparativo_suggestions) >= 1

    def test_regime_calculation_autonomo_pf(self):
        """Test autonomous PF tax calculation."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("120000"),
            rendimentos=[create_autonomous_income(Decimal("120000"))],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        result = analyzer._calculate_autonomo_pf()

        assert result.regime == TaxRegime.AUTONOMO_PF
        assert result.gross_income == Decimal("120000")
        assert result.estimated_tax > 0
        assert result.effective_rate > 0
        assert result.effective_rate < 1

    def test_regime_calculation_simples_nacional(self):
        """Test Simples Nacional tax calculation."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("120000"),
            rendimentos=[create_autonomous_income(Decimal("120000"))],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        result = analyzer._calculate_simples_nacional()

        assert result.regime == TaxRegime.SIMPLES_NACIONAL
        assert result.gross_income == Decimal("120000")
        assert result.estimated_tax > 0
        # Simples should be around 6% for this bracket
        assert Decimal("0.05") < result.effective_rate < Decimal("0.15")

    def test_regime_calculation_lucro_presumido(self):
        """Test Lucro Presumido tax calculation."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("200000"),
            rendimentos=[create_autonomous_income(Decimal("200000"))],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        result = analyzer._calculate_lucro_presumido()

        assert result.regime == TaxRegime.LUCRO_PRESUMIDO
        assert result.gross_income == Decimal("200000")
        assert result.estimated_tax > 0
        # LP should be around 13-18% for services
        assert Decimal("0.10") < result.effective_rate < Decimal("0.25")

    def test_mei_mention_for_low_income(self):
        """Test MEI is mentioned for income below limit."""
        autonomous_income = Decimal("70000")  # Below MEI limit of 81k

        decl = create_declaration(
            rendimentos_tributaveis=autonomous_income,
            rendimentos=[create_autonomous_income(autonomous_income)],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        result = analyzer._calculate_simples_nacional()

        assert "MEI" in result.notes


class TestCalculateAllRegimes:
    """Tests for calculating all applicable regimes."""

    def test_all_regimes_calculated(self):
        """Test that all regimes are calculated."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("200000"),
            rendimentos=[create_autonomous_income(Decimal("200000"))],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        regimes = analyzer._calculate_all_regimes()

        regime_types = {r.regime for r in regimes}
        assert TaxRegime.AUTONOMO_PF in regime_types
        assert TaxRegime.SIMPLES_NACIONAL in regime_types
        assert TaxRegime.LUCRO_PRESUMIDO in regime_types

    def test_high_income_excludes_simples(self):
        """Test that high income excludes Simples Nacional."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("5000000"),  # Above Simples limit
            rendimentos=[create_autonomous_income(Decimal("5000000"))],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        regimes = analyzer._calculate_all_regimes()

        regime_types = {r.regime for r in regimes}
        assert TaxRegime.SIMPLES_NACIONAL not in regime_types


class TestConvenienceFunction:
    """Tests for analyze_autonomous_professional convenience function."""

    def test_returns_tuple(self):
        """Test that convenience function returns correct types."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("100000"),
            rendimentos=[create_autonomous_income(Decimal("100000"))],
        )

        result = analyze_autonomous_professional(decl)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], list)

    def test_matches_class_results(self):
        """Test that convenience function matches class results."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("100000"),
            rendimentos=[create_autonomous_income(Decimal("100000"))],
        )

        # Use class
        analyzer = AutonomousProfessionalAnalyzer(decl)
        class_result = analyzer.analyze()

        # Use convenience function
        func_result = analyze_autonomous_professional(decl)

        assert len(class_result[0]) == len(func_result[0])
        assert len(class_result[1]) == len(func_result[1])


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_autonomous_income(self):
        """Test handling of zero autonomous income."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("100000"),
            rendimentos=[],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        assert isinstance(suggestions, list)
        assert isinstance(warnings, list)

    def test_very_high_autonomous_income(self):
        """Test handling of very high autonomous income."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("10000000"),
            rendimentos=[create_autonomous_income(Decimal("10000000"))],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should still provide comparison
        comparativo = [s for s in suggestions if "comparativo" in s.titulo.lower()]
        assert len(comparativo) >= 1

    def test_mixed_income_sources(self):
        """Test with both salary and autonomous income."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("200000"),
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                    valor_anual=Decimal("100000"),
                ),
                create_autonomous_income(Decimal("100000")),
            ],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should analyze autonomous portion
        assert analyzer._renda_autonoma == Decimal("100000")


class TestSimplesTaxBrackets:
    """Tests for Simples Nacional tax brackets."""

    def test_first_bracket(self):
        """Test first Simples bracket (up to 180k)."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("150000"),
            rendimentos=[create_autonomous_income(Decimal("150000"))],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        result = analyzer._calculate_simples_nacional()

        # First bracket is 6%
        expected_tax = Decimal("150000") * Decimal("0.06")
        assert abs(result.estimated_tax - expected_tax) < Decimal("1")

    def test_second_bracket(self):
        """Test second Simples bracket (180k-360k)."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("300000"),
            rendimentos=[create_autonomous_income(Decimal("300000"))],
        )

        analyzer = AutonomousProfessionalAnalyzer(decl)
        result = analyzer._calculate_simples_nacional()

        # Second bracket calculation
        expected_tax = Decimal("300000") * Decimal("0.112") - Decimal("9360")
        assert abs(result.estimated_tax - expected_tax) < Decimal("1")


class TestImportFromModule:
    """Tests for module imports."""

    def test_import_from_analyzers_init(self):
        """Test that analyzer can be imported from analyzers package."""
        from irpf_analyzer.core.analyzers import (
            AutonomousProfessionalAnalyzer,
            analyze_autonomous_professional,
        )

        assert AutonomousProfessionalAnalyzer is not None
        assert analyze_autonomous_professional is not None
