"""Tests for legislation alerts analyzer."""

from datetime import date
from decimal import Decimal

from irpf_analyzer.core.analyzers.legislation_alerts import (
    ImpactLevel,
    LegislationAlertsAnalyzer,
    LegislationCategory,
    analyze_legislation,
)
from irpf_analyzer.core.models import (
    Declaration,
    TipoDeclaracao,
)
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.enums import GrupoBem
from irpf_analyzer.core.models.patrimony import BemDireito, Localizacao


def create_declaration(
    cpf: str = "52998224725",
    rendimentos_tributaveis: Decimal = Decimal("100000"),
    rendimentos_isentos: Decimal = Decimal("0"),
    rendimentos_exclusivos: Decimal = Decimal("0"),
    imposto_devido: Decimal = Decimal("10000"),
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
        total_rendimentos_isentos=rendimentos_isentos,
        total_rendimentos_exclusivos=rendimentos_exclusivos,
        imposto_devido=imposto_devido,
        bens_direitos=bens_direitos or [],
    )


def create_crypto_asset(
    value_current: Decimal,
    value_previous: Decimal = Decimal("0"),
    cnpj: str | None = None,
    description: str = "Bitcoin BTC",
) -> BemDireito:
    """Create a cryptocurrency asset."""
    return BemDireito(
        grupo=GrupoBem.CRIPTOATIVOS,
        codigo="99",
        discriminacao=description,
        situacao_anterior=value_previous,
        situacao_atual=value_current,
        cnpj_instituicao=cnpj,
    )


def create_foreign_asset(
    value_current: Decimal,
    value_previous: Decimal = Decimal("0"),
    country_code: str = "249",  # USA
    description: str = "Ações no exterior - Interactive Brokers",
) -> BemDireito:
    """Create a foreign asset."""
    return BemDireito(
        grupo=GrupoBem.PARTICIPACOES_SOCIETARIAS,  # Closest to stocks
        codigo="31",
        discriminacao=description,
        situacao_anterior=value_previous,
        situacao_atual=value_current,
        localizacao=Localizacao(pais=country_code),
    )


class TestLegislationEnums:
    """Tests for legislation-related enums."""

    def test_legislation_categories(self):
        """Test that all legislation categories are defined."""
        assert LegislationCategory.TAX_REFORM.value == "tax_reform"
        assert LegislationCategory.DEDUCTION_LIMITS.value == "deduction_limits"
        assert LegislationCategory.CRYPTOCURRENCY.value == "cryptocurrency"
        assert LegislationCategory.INTERNATIONAL.value == "international"
        assert LegislationCategory.CAPITAL_GAINS.value == "capital_gains"

    def test_impact_levels(self):
        """Test that all impact levels are defined."""
        assert ImpactLevel.HIGH.value == "alto"
        assert ImpactLevel.MEDIUM.value == "medio"
        assert ImpactLevel.LOW.value == "baixo"
        assert ImpactLevel.INFORMATIONAL.value == "informativo"


class TestLegislationChangeDatabase:
    """Tests for the legislation change database."""

    def test_legislation_changes_not_empty(self):
        """Test that there are legislation changes defined."""
        assert len(LegislationAlertsAnalyzer.LEGISLATION_CHANGES) >= 5

    def test_all_changes_have_required_fields(self):
        """Test that all changes have required fields."""
        for change in LegislationAlertsAnalyzer.LEGISLATION_CHANGES:
            assert change.name
            assert change.description
            assert change.effective_date
            assert change.category in LegislationCategory
            assert change.impact_level in ImpactLevel
            assert change.law_reference
            assert change.details

    def test_has_2026_reform_changes(self):
        """Test that 2026 reform changes are included."""
        reform_changes = [
            c for c in LegislationAlertsAnalyzer.LEGISLATION_CHANGES
            if c.category == LegislationCategory.TAX_REFORM
        ]
        assert len(reform_changes) >= 2

    def test_has_crypto_regulations(self):
        """Test that crypto regulations are included."""
        crypto_changes = [
            c for c in LegislationAlertsAnalyzer.LEGISLATION_CHANGES
            if c.category == LegislationCategory.CRYPTOCURRENCY
        ]
        assert len(crypto_changes) >= 1

    def test_has_international_rules(self):
        """Test that international rules are included."""
        intl_changes = [
            c for c in LegislationAlertsAnalyzer.LEGISLATION_CHANGES
            if c.category == LegislationCategory.INTERNATIONAL
        ]
        assert len(intl_changes) >= 1


class TestReform2026Exemption:
    """Tests for 2026 tax reform exemption detection."""

    def test_low_income_gets_exemption_suggestion(self):
        """Test that low income taxpayers get exemption suggestion."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("50000"),
            imposto_devido=Decimal("5000"),
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should suggest they'll be exempt
        exempt_suggestions = [
            s for s in suggestions if "isento" in s.titulo.lower()
        ]
        assert len(exempt_suggestions) >= 1
        assert exempt_suggestions[0].economia_potencial == Decimal("5000")

    def test_medium_income_gets_reduction_suggestion(self):
        """Test that medium income taxpayers get reduction suggestion."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("75000"),  # Between 60k and 88.2k
            imposto_devido=Decimal("8000"),
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should suggest progressive reduction
        reduction_suggestions = [
            s for s in suggestions if "Redução" in s.titulo or "progressiva" in s.descricao.lower()
        ]
        assert len(reduction_suggestions) >= 1

    def test_high_income_no_exemption_suggestion(self):
        """Test that high income taxpayers don't get exemption suggestion."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("200000"),
            imposto_devido=Decimal("30000"),
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should NOT suggest exemption
        exempt_suggestions = [
            s for s in suggestions if "isento" in s.titulo.lower()
        ]
        assert len(exempt_suggestions) == 0


class TestIRPFM:
    """Tests for IRPFM (minimum tax for high earners) detection."""

    def test_very_high_income_gets_irpfm_warning(self):
        """Test that very high income taxpayers get IRPFM warning."""
        # Above R$ 1.2M - 10% minimum applies
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("1000000"),
            rendimentos_isentos=Decimal("500000"),  # Total = R$ 1.5M
            imposto_devido=Decimal("100000"),  # Only ~6.7% effective rate
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should warn about IRPFM
        irpfm_warnings = [
            w for w in warnings if "IRPFM" in w.mensagem
        ]
        assert len(irpfm_warnings) >= 1

    def test_high_income_gets_irpfm_alert(self):
        """Test that high income taxpayers (R$ 600k-1.2M) get alert."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("400000"),
            rendimentos_isentos=Decimal("300000"),  # Total = R$ 700k
            imposto_devido=Decimal("50000"),
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should warn about potential IRPFM
        irpfm_warnings = [
            w for w in warnings if "IRPFM" in w.mensagem
        ]
        assert len(irpfm_warnings) >= 1

    def test_normal_income_no_irpfm_warning(self):
        """Test that normal income taxpayers don't get IRPFM warning."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("200000"),
            imposto_devido=Decimal("30000"),
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should NOT warn about IRPFM
        irpfm_warnings = [
            w for w in warnings if "IRPFM" in w.mensagem
        ]
        assert len(irpfm_warnings) == 0


class TestCryptoObligations:
    """Tests for cryptocurrency obligation detection."""

    def test_crypto_without_exchange_cnpj_warning(self):
        """Test that crypto without exchange CNPJ generates warning."""
        decl = create_declaration(
            bens_direitos=[
                create_crypto_asset(
                    value_current=Decimal("50000"),
                    cnpj=None,  # No exchange CNPJ
                )
            ]
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should warn about missing CNPJ
        cnpj_warnings = [
            w for w in warnings if "CNPJ" in w.mensagem and "exchange" in w.mensagem.lower()
        ]
        assert len(cnpj_warnings) >= 1

    def test_crypto_with_exchange_cnpj_no_warning(self):
        """Test that crypto with valid exchange CNPJ doesn't generate warning."""
        decl = create_declaration(
            bens_direitos=[
                create_crypto_asset(
                    value_current=Decimal("50000"),
                    cnpj="18394228000188",  # Valid CNPJ
                )
            ]
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should NOT warn about missing CNPJ
        cnpj_warnings = [
            w for w in warnings if "CNPJ de exchange" in w.mensagem
        ]
        assert len(cnpj_warnings) == 0

    def test_high_crypto_gains_warning(self):
        """Test that high crypto gains generate monthly declaration warning."""
        # R$ 600k gain annually = R$ 50k/month > R$ 35k threshold
        decl = create_declaration(
            bens_direitos=[
                create_crypto_asset(
                    value_current=Decimal("800000"),
                    value_previous=Decimal("200000"),  # R$ 600k gain
                )
            ]
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should warn about monthly declaration obligation
        monthly_warnings = [
            w for w in warnings if "mensal" in w.mensagem.lower() and "cripto" in w.mensagem.lower()
        ]
        assert len(monthly_warnings) >= 1

    def test_crypto_detected_by_description(self):
        """Test that crypto is detected by description keywords."""
        decl = create_declaration(
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.OUTROS_BENS,
                    codigo="99",
                    discriminacao="Ethereum ETH na Binance",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("10000"),
                )
            ]
        )
        analyzer = LegislationAlertsAnalyzer(decl)

        crypto_assets = analyzer._get_crypto_assets()
        assert len(crypto_assets) == 1


class TestInternationalObligations:
    """Tests for international tax obligation detection."""

    def test_dcbe_warning_for_high_foreign_assets(self):
        """Test DCBE warning for assets > USD 1M."""
        # R$ 6M = ~USD 1.2M at 5 BRL/USD
        decl = create_declaration(
            bens_direitos=[
                create_foreign_asset(value_current=Decimal("6000000"))
            ]
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should warn about DCBE
        dcbe_warnings = [
            w for w in warnings if "DCBE" in w.mensagem
        ]
        assert len(dcbe_warnings) >= 1

    def test_no_dcbe_warning_for_low_foreign_assets(self):
        """Test no DCBE warning for assets < USD 1M."""
        # R$ 2M = ~USD 400k at 5 BRL/USD
        decl = create_declaration(
            bens_direitos=[
                create_foreign_asset(value_current=Decimal("2000000"))
            ]
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should NOT warn about DCBE
        dcbe_warnings = [
            w for w in warnings if "DCBE OBRIGATÓRIO" in w.mensagem
        ]
        assert len(dcbe_warnings) == 0

    def test_foreign_asset_detected_by_location(self):
        """Test that foreign assets are detected by location."""
        decl = create_declaration(
            bens_direitos=[
                create_foreign_asset(
                    value_current=Decimal("100000"),
                    country_code="249",  # USA
                )
            ]
        )
        analyzer = LegislationAlertsAnalyzer(decl)

        foreign_assets = analyzer._get_foreign_assets()
        assert len(foreign_assets) == 1

    def test_foreign_asset_detected_by_description(self):
        """Test that foreign assets are detected by description."""
        decl = create_declaration(
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.PARTICIPACOES_SOCIETARIAS,
                    codigo="31",
                    discriminacao="Ações Apple compradas via Interactive Brokers USA",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("50000"),
                    localizacao=Localizacao(pais="105"),  # Brazil but description says foreign
                )
            ]
        )
        analyzer = LegislationAlertsAnalyzer(decl)

        foreign_assets = analyzer._get_foreign_assets()
        assert len(foreign_assets) == 1


class TestDeclarationObligation:
    """Tests for declaration obligation alerts."""

    def test_high_taxable_income_obligation(self):
        """Test obligation alert for high taxable income."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("50000"),  # Above R$ 33.888 threshold
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should mention obligation
        obligation_suggestions = [
            s for s in suggestions if "Obrigatoriedade" in s.titulo
        ]
        assert len(obligation_suggestions) >= 1

    def test_high_patrimony_obligation(self):
        """Test obligation alert for high patrimony."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("20000"),  # Below income threshold
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento",
                    situacao_anterior=Decimal("800000"),
                    situacao_atual=Decimal("900000"),
                )
            ]
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should mention patrimony obligation
        obligation_suggestions = [
            s for s in suggestions if "Obrigatoriedade" in s.titulo
        ]
        assert len(obligation_suggestions) >= 1


class TestReductionBenefitEstimate:
    """Tests for reduction benefit estimation."""

    def test_full_exemption_benefit(self):
        """Test that full exemption calculates correct benefit."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("50000"),  # Below 60k
            imposto_devido=Decimal("5000"),
        )
        analyzer = LegislationAlertsAnalyzer(decl)

        benefit = analyzer._estimate_reduction_benefit(Decimal("50000"))
        assert benefit == Decimal("5000")  # Full tax as benefit

    def test_no_reduction_above_limit(self):
        """Test that no reduction above the limit."""
        decl = create_declaration(rendimentos_tributaveis=Decimal("100000"))
        analyzer = LegislationAlertsAnalyzer(decl)

        benefit = analyzer._estimate_reduction_benefit(Decimal("100000"))
        assert benefit == Decimal("0")

    def test_partial_reduction_in_zone(self):
        """Test partial reduction in transition zone."""
        decl = create_declaration(rendimentos_tributaveis=Decimal("74100"))
        analyzer = LegislationAlertsAnalyzer(decl)

        # R$ 74.1k is roughly midway between 60k and 88.2k
        benefit = analyzer._estimate_reduction_benefit(Decimal("74100"))
        assert benefit > Decimal("0")
        assert benefit < Decimal("312.89") * 12  # Max annual reduction


class TestAnalyzerSummary:
    """Tests for analyzer summary functionality."""

    def test_get_summary(self):
        """Test get_summary method."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("50000"),
            imposto_devido=Decimal("5000"),
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        analyzer.analyze()

        summary = analyzer.get_summary()
        assert "total_alerts" in summary
        assert "high_impact" in summary
        assert "upcoming_changes" in summary
        assert "action_required" in summary

    def test_get_all_alerts(self):
        """Test get_all_alerts method."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("50000"),
            imposto_devido=Decimal("5000"),
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        analyzer.analyze()

        alerts = analyzer.get_all_alerts()
        assert isinstance(alerts, list)


class TestConvenienceFunction:
    """Tests for the convenience function."""

    def test_analyze_legislation_function(self):
        """Test the analyze_legislation convenience function."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("50000"),
            imposto_devido=Decimal("5000"),
        )

        suggestions, warnings = analyze_legislation(decl)

        assert isinstance(suggestions, list)
        assert isinstance(warnings, list)

    def test_analyze_legislation_with_reference_date(self):
        """Test analyze_legislation with custom reference date."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("50000"),
            imposto_devido=Decimal("5000"),
        )

        suggestions, warnings = analyze_legislation(
            decl,
            reference_date=date(2025, 6, 1),
        )

        assert isinstance(suggestions, list)
        assert isinstance(warnings, list)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_declaration(self):
        """Test with minimal/empty declaration."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("0"),
            imposto_devido=Decimal("0"),
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should not crash
        assert isinstance(suggestions, list)
        assert isinstance(warnings, list)

    def test_no_bens_direitos(self):
        """Test with no assets."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("100000"),
            imposto_devido=Decimal("10000"),
            bens_direitos=[],
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should not have crypto or international warnings
        crypto_warnings = [w for w in warnings if "cripto" in w.mensagem.lower()]
        dcbe_warnings = [w for w in warnings if "DCBE" in w.mensagem]
        assert len(crypto_warnings) == 0
        assert len(dcbe_warnings) == 0

    def test_future_reference_date(self):
        """Test with future reference date."""
        decl = create_declaration(
            rendimentos_tributaveis=Decimal("50000"),
            imposto_devido=Decimal("5000"),
        )
        analyzer = LegislationAlertsAnalyzer(
            decl,
            reference_date=date(2027, 1, 1),  # After 2026 reform
        )
        suggestions, warnings = analyzer.analyze()

        # Should still work
        assert isinstance(suggestions, list)

    def test_mixed_assets(self):
        """Test with mixed crypto and foreign assets."""
        decl = create_declaration(
            bens_direitos=[
                create_crypto_asset(value_current=Decimal("50000")),
                create_foreign_asset(value_current=Decimal("100000")),
            ]
        )
        analyzer = LegislationAlertsAnalyzer(decl)
        suggestions, warnings = analyzer.analyze()

        # Should detect both types
        crypto_assets = analyzer._get_crypto_assets()
        foreign_assets = analyzer._get_foreign_assets()
        assert len(crypto_assets) == 1
        assert len(foreign_assets) == 1
