"""Tests for expatriate and tax residency analyzer."""

from decimal import Decimal

from irpf_analyzer.core.analyzers.expatriate import (
    ExpatriateAnalyzer,
    TaxTreatyCountry,
    analyze_expatriate,
)
from irpf_analyzer.core.models import (
    BemDireito,
    Declaration,
    GrupoBem,
    TipoDeclaracao,
)
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.enums import TipoRendimento
from irpf_analyzer.core.models.income import Rendimento
from irpf_analyzer.core.models.patrimony import Localizacao


def create_declaration(
    cpf: str = "52998224725",
    rendimentos_tributaveis: Decimal = Decimal("100000"),
    rendimentos: list[Rendimento] | None = None,
    bens_direitos: list[BemDireito] | None = None,
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
        bens_direitos=bens_direitos or [],
    )


def create_foreign_income(value: Decimal) -> Rendimento:
    """Create foreign income rendimento."""
    return Rendimento(
        tipo=TipoRendimento.RENDIMENTOS_EXTERIOR,
        valor_anual=value,
    )


def create_foreign_asset(
    value: Decimal,
    country_code: str = "249",  # USA
    discriminacao: str = "Investimento no exterior",
    situacao_anterior: Decimal | None = None,
    grupo: GrupoBem = GrupoBem.APLICACOES_FINANCEIRAS,
) -> BemDireito:
    """Create foreign asset."""
    return BemDireito(
        grupo=grupo,
        codigo="01",
        discriminacao=discriminacao,
        situacao_anterior=situacao_anterior or value * Decimal("0.8"),
        situacao_atual=value,
        localizacao=Localizacao(pais=country_code),
    )


def create_brazilian_asset(
    value: Decimal,
    discriminacao: str = "Imóvel no Brasil",
    situacao_anterior: Decimal | None = None,
    grupo: GrupoBem = GrupoBem.IMOVEIS,
) -> BemDireito:
    """Create Brazilian asset."""
    return BemDireito(
        grupo=grupo,
        codigo="01",
        discriminacao=discriminacao,
        situacao_anterior=situacao_anterior or value * Decimal("0.8"),
        situacao_atual=value,
        localizacao=Localizacao(pais="105"),  # Brazil
    )


class TestTaxTreatyCountries:
    """Tests for tax treaty country enum."""

    def test_major_countries_included(self):
        """Test that major trading partners are included."""
        assert TaxTreatyCountry.USA.value == "US"
        assert TaxTreatyCountry.UK.value == "GB"
        assert TaxTreatyCountry.GERMANY.value == "DE"
        assert TaxTreatyCountry.PORTUGAL.value == "PT"
        assert TaxTreatyCountry.JAPAN.value == "JP"

    def test_treaty_count(self):
        """Test that reasonable number of treaties exist."""
        assert len(TaxTreatyCountry) >= 30


class TestNoForeignAssets:
    """Tests when there are no foreign assets or income."""

    def test_no_analysis_without_foreign_elements(self):
        """Test that minimal analysis occurs without foreign elements."""
        decl = create_declaration(
            bens_direitos=[
                create_brazilian_asset(Decimal("500000")),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should not have DCBE or foreign tax credit suggestions
        dcbe_warnings = [w for w in warnings if "DCBE" in w.mensagem]
        assert len(dcbe_warnings) == 0


class TestDCBERequirement:
    """Tests for DCBE (foreign capital declaration) requirement."""

    def test_dcbe_required_high_foreign_assets(self):
        """Test DCBE warning for high value foreign assets."""
        # Create assets worth > USD 1M (at 5.50 rate = R$ 5.5M)
        decl = create_declaration(
            bens_direitos=[
                create_foreign_asset(
                    Decimal("6000000"),  # R$ 6M ~ USD 1.09M
                    discriminacao="Conta investimentos USA",
                ),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        dcbe_warnings = [w for w in warnings if "DCBE" in w.mensagem]
        assert len(dcbe_warnings) >= 1
        assert "obrigatória" in dcbe_warnings[0].mensagem.lower()

    def test_dcbe_approaching_threshold_warning(self):
        """Test warning when approaching DCBE threshold."""
        # Create assets worth ~80% of threshold (R$ 4.4M ~ USD 800k)
        decl = create_declaration(
            bens_direitos=[
                create_foreign_asset(
                    Decimal("4500000"),
                    discriminacao="Conta investimentos USA",
                ),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        dcbe_warnings = [w for w in warnings if "DCBE" in w.mensagem]
        assert len(dcbe_warnings) >= 1

    def test_no_dcbe_low_foreign_assets(self):
        """Test no DCBE warning for low value foreign assets."""
        decl = create_declaration(
            bens_direitos=[
                create_foreign_asset(
                    Decimal("100000"),  # R$ 100k ~ USD 18k
                    discriminacao="Conta poupança exterior",
                ),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        dcbe_warnings = [
            w for w in warnings
            if "DCBE" in w.mensagem and "obrigatória" in w.mensagem.lower()
        ]
        assert len(dcbe_warnings) == 0


class TestForeignTaxCredit:
    """Tests for foreign tax credit calculation."""

    def test_foreign_tax_credit_with_paid_tax(self):
        """Test foreign tax credit calculation when tax was paid."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("200000"),
            rendimentos=[
                create_foreign_income(Decimal("50000")),
            ],
        )

        analyzer = ExpatriateAnalyzer(
            decl,
            foreign_tax_paid=Decimal("10000"),
        )
        suggestions, warnings = analyzer.analyze()

        credit_suggestions = [
            s for s in suggestions
            if "crédito" in s.titulo.lower() or "imposto pago" in s.titulo.lower()
        ]
        assert len(credit_suggestions) >= 1
        assert credit_suggestions[0].economia_potencial > 0

    def test_foreign_tax_credit_suggest_checking(self):
        """Test suggestion to check for foreign tax when not declared."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("150000"),
            rendimentos=[
                create_foreign_income(Decimal("30000")),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl, foreign_tax_paid=Decimal("0"))
        suggestions, warnings = analyzer.analyze()

        check_suggestions = [
            s for s in suggestions
            if "verifique" in s.titulo.lower() or "exterior" in s.descricao.lower()
        ]
        assert len(check_suggestions) >= 1

    def test_foreign_tax_credit_limited_to_brazilian_tax(self):
        """Test that credit is limited to Brazilian tax on foreign income."""
        foreign_income = Decimal("50000")
        foreign_tax_paid = Decimal("20000")  # More than Brazilian tax

        decl = create_declaration(
            rendimentos_tributaveis=Decimal("200000"),
            rendimentos=[
                create_foreign_income(foreign_income),
            ],
        )

        analyzer = ExpatriateAnalyzer(
            decl,
            foreign_tax_paid=foreign_tax_paid,
        )

        # Use the direct calculation method
        credit = analyzer.calculate_foreign_tax_credit(
            country="USA",
            foreign_income=foreign_income,
            foreign_tax_paid=foreign_tax_paid,
        )

        assert credit.credit_allowed <= credit.brazilian_tax_on_income
        assert credit.excess_credit > 0

    def test_no_foreign_income_no_credit_analysis(self):
        """Test no credit analysis when no foreign income."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("100000"),
            rendimentos=[],  # No foreign income
        )

        analyzer = ExpatriateAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        credit_suggestions = [
            s for s in suggestions
            if "crédito" in s.titulo.lower()
        ]
        assert len(credit_suggestions) == 0


class TestExitTax:
    """Tests for exit tax (imposto de saída) analysis."""

    def test_exit_tax_calculated_when_leaving(self):
        """Test exit tax is calculated when leaving Brazil."""
        decl = create_declaration(
            bens_direitos=[
                create_brazilian_asset(
                    Decimal("1000000"),
                    situacao_anterior=Decimal("500000"),  # 100% gain
                ),
                create_foreign_asset(
                    Decimal("500000"),
                    situacao_anterior=Decimal("300000"),  # 66% gain
                ),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl, is_leaving_brazil=True)
        suggestions, warnings = analyzer.analyze()

        exit_warnings = [
            w for w in warnings
            if "imposto de saída" in w.mensagem.lower() or "saída" in w.mensagem.lower()
        ]
        assert len(exit_warnings) >= 1
        assert exit_warnings[0].valor_impacto > 0

    def test_exit_tax_not_calculated_when_staying(self):
        """Test exit tax not calculated when not leaving."""
        decl = create_declaration(
            bens_direitos=[
                create_brazilian_asset(
                    Decimal("1000000"),
                    situacao_anterior=Decimal("500000"),
                ),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl, is_leaving_brazil=False)
        suggestions, warnings = analyzer.analyze()

        exit_warnings = [
            w for w in warnings
            if "imposto de saída" in w.mensagem.lower()
        ]
        assert len(exit_warnings) == 0

    def test_exit_tax_planning_suggestions(self):
        """Test exit tax planning suggestions are provided."""
        decl = create_declaration(
            bens_direitos=[
                create_brazilian_asset(
                    Decimal("2000000"),
                    situacao_anterior=Decimal("1000000"),
                ),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl, is_leaving_brazil=True)
        suggestions, warnings = analyzer.analyze()

        planning_suggestions = [
            s for s in suggestions
            if "planejamento" in s.titulo.lower() or "saída" in s.titulo.lower()
        ]
        assert len(planning_suggestions) >= 1

    def test_exit_tax_no_gain_no_tax(self):
        """Test no exit tax when no gains."""
        decl = create_declaration(
            bens_direitos=[
                create_brazilian_asset(
                    Decimal("500000"),
                    situacao_anterior=Decimal("600000"),  # Loss
                ),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl, is_leaving_brazil=True)
        exit_calculations = analyzer.calculate_exit_tax()

        # No calculations should have tax (all losses)
        assert all(calc.capital_gain <= 0 or calc.exit_tax == 0 for calc in exit_calculations)


class TestExitTaxCalculation:
    """Tests for detailed exit tax calculation."""

    def test_calculate_exit_tax_method(self):
        """Test the calculate_exit_tax method."""
        decl = create_declaration(
            bens_direitos=[
                create_brazilian_asset(
                    Decimal("1000000"),
                    situacao_anterior=Decimal("500000"),
                    grupo=GrupoBem.IMOVEIS,
                ),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl, is_leaving_brazil=True)
        calculations = analyzer.calculate_exit_tax()

        assert len(calculations) >= 1
        calc = calculations[0]
        assert calc.capital_gain == Decimal("500000")
        assert calc.exit_tax == Decimal("75000")  # 15% of 500k

    def test_exit_tax_rates_by_asset_type(self):
        """Test exit tax rates vary by asset type."""
        analyzer = ExpatriateAnalyzer
        assert analyzer.EXIT_TAX_RATES[GrupoBem.IMOVEIS] == Decimal("0.15")
        assert analyzer.EXIT_TAX_RATES[GrupoBem.PARTICIPACOES_SOCIETARIAS] == Decimal("0.15")


class TestForeignTaxCreditCalculation:
    """Tests for detailed foreign tax credit calculation."""

    def test_calculate_foreign_tax_credit_method(self):
        """Test the calculate_foreign_tax_credit method."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("200000"),
        )

        analyzer = ExpatriateAnalyzer(decl)
        credit = analyzer.calculate_foreign_tax_credit(
            country="USA",
            foreign_income=Decimal("50000"),
            foreign_tax_paid=Decimal("10000"),
        )

        assert credit.country == "USA"
        assert credit.foreign_income == Decimal("50000")
        assert credit.foreign_tax_paid == Decimal("10000")
        assert credit.credit_allowed > 0
        assert credit.credit_allowed <= credit.brazilian_tax_on_income

    def test_full_credit_when_foreign_tax_lower(self):
        """Test full credit when foreign tax is lower than Brazilian."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("200000"),
        )

        analyzer = ExpatriateAnalyzer(decl)
        credit = analyzer.calculate_foreign_tax_credit(
            country="Germany",
            foreign_income=Decimal("100000"),
            foreign_tax_paid=Decimal("5000"),  # Low foreign tax
        )

        assert credit.credit_allowed == credit.foreign_tax_paid
        assert credit.excess_credit == Decimal("0")


class TestTaxTreatyGuidance:
    """Tests for tax treaty guidance."""

    def test_treaty_guidance_with_foreign_income(self):
        """Test treaty guidance is provided with significant foreign income."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("200000"),
            rendimentos=[
                create_foreign_income(Decimal("50000")),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        treaty_suggestions = [
            s for s in suggestions
            if "tratado" in s.titulo.lower() or "bitributação" in s.descricao.lower()
        ]
        assert len(treaty_suggestions) >= 1

    def test_no_treaty_guidance_low_foreign_income(self):
        """Test no treaty guidance for low foreign income."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("100000"),
            rendimentos=[
                create_foreign_income(Decimal("5000")),  # Low amount
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        treaty_suggestions = [
            s for s in suggestions
            if "tratado" in s.titulo.lower()
        ]
        assert len(treaty_suggestions) == 0


class TestForeignAssetDetection:
    """Tests for foreign asset detection."""

    def test_detect_foreign_by_country_code(self):
        """Test detection of foreign assets by country code."""
        decl = create_declaration(
            bens_direitos=[
                create_foreign_asset(
                    Decimal("100000"),
                    country_code="249",  # USA
                    discriminacao="Conta bancária",
                ),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        assert len(analyzer._foreign_assets) == 1

    def test_detect_foreign_by_description(self):
        """Test detection of foreign assets by description."""
        decl = create_declaration(
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="01",
                    discriminacao="Interactive Brokers - conta USD",
                    situacao_anterior=Decimal("50000"),
                    situacao_atual=Decimal("60000"),
                    # No location set
                ),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        # Should detect as foreign based on description
        assert len(analyzer._foreign_assets) >= 1

    def test_brazilian_asset_not_detected_as_foreign(self):
        """Test Brazilian assets are not detected as foreign."""
        decl = create_declaration(
            bens_direitos=[
                create_brazilian_asset(Decimal("500000")),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        assert len(analyzer._foreign_assets) == 0


class TestConvenienceFunction:
    """Tests for analyze_expatriate convenience function."""

    def test_returns_tuple(self):
        """Test that convenience function returns correct types."""
        decl = create_declaration()
        result = analyze_expatriate(decl)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], list)

    def test_with_parameters(self):
        """Test convenience function with all parameters."""
        decl = create_declaration(
            bens_direitos=[
                create_brazilian_asset(
                    Decimal("1000000"),
                    situacao_anterior=Decimal("500000"),
                ),
            ],
        )

        suggestions, warnings = analyze_expatriate(
            decl,
            is_leaving_brazil=True,
            foreign_tax_paid=Decimal("5000"),
        )

        # Should have exit tax warnings when leaving
        exit_warnings = [
            w for w in warnings
            if "saída" in w.mensagem.lower()
        ]
        assert len(exit_warnings) >= 1

    def test_matches_class_results(self):
        """Test that convenience function matches class results."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("150000"),
            rendimentos=[
                create_foreign_income(Decimal("30000")),
            ],
        )

        # Use class
        analyzer = ExpatriateAnalyzer(decl)
        class_result = analyzer.analyze()

        # Use convenience function
        func_result = analyze_expatriate(decl)

        assert len(class_result[0]) == len(func_result[0])
        assert len(class_result[1]) == len(func_result[1])


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_declaration(self):
        """Test analyzer handles empty declaration."""
        decl = create_declaration()
        analyzer = ExpatriateAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        assert isinstance(suggestions, list)
        assert isinstance(warnings, list)

    def test_very_high_foreign_assets(self):
        """Test handling of very high value foreign assets."""
        decl = create_declaration(
            bens_direitos=[
                create_foreign_asset(Decimal("50000000")),  # R$ 50M
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should definitely warn about DCBE
        dcbe_warnings = [w for w in warnings if "DCBE" in w.mensagem]
        assert len(dcbe_warnings) >= 1

    def test_multiple_foreign_income_sources(self):
        """Test handling of multiple foreign income sources."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("300000"),
            rendimentos=[
                create_foreign_income(Decimal("50000")),
                create_foreign_income(Decimal("30000")),
                create_foreign_income(Decimal("20000")),
            ],
        )

        analyzer = ExpatriateAnalyzer(decl)
        assert analyzer._foreign_income == Decimal("100000")


class TestImportFromModule:
    """Tests for module imports."""

    def test_import_from_analyzers_init(self):
        """Test that analyzer can be imported from analyzers package."""
        from irpf_analyzer.core.analyzers import (
            ExpatriateAnalyzer,
            analyze_expatriate,
        )

        assert ExpatriateAnalyzer is not None
        assert analyze_expatriate is not None
