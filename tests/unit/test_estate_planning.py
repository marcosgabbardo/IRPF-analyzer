"""Tests for estate planning analyzer."""

from decimal import Decimal

from irpf_analyzer.core.analyzers.estate_planning import (
    ITCMD_RATES,
    BrazilianState,
    EstatePlanningAnalyzer,
    analyze_estate_planning,
    get_itcmd_rate,
    list_states_by_lowest_rate,
)
from irpf_analyzer.core.models import (
    BemDireito,
    Declaration,
    GrupoBem,
    TipoDeclaracao,
)
from irpf_analyzer.core.models.declaration import Contribuinte


class TestITCMDRates:
    """Tests for ITCMD rate data."""

    def test_all_states_have_rates(self):
        """Test that all Brazilian states have ITCMD rates defined."""
        for state in BrazilianState:
            assert state in ITCMD_RATES, f"Missing ITCMD rate for {state.value}"

    def test_rates_are_valid(self):
        """Test that all rates are valid percentages."""
        for state, rate in ITCMD_RATES.items():
            assert rate.donation_rate >= Decimal("0"), f"Invalid donation rate for {state.value}"
            assert rate.donation_rate <= Decimal("8"), f"Donation rate too high for {state.value}"
            assert rate.inheritance_rate >= Decimal("0"), f"Invalid inheritance rate for {state.value}"
            assert rate.inheritance_rate <= Decimal("8"), f"Inheritance rate too high for {state.value}"
            assert rate.max_rate >= rate.inheritance_rate, f"Max rate inconsistent for {state.value}"

    def test_amazonas_lowest_rate(self):
        """Test that Amazonas has the lowest rate (2%)."""
        am_rate = ITCMD_RATES[BrazilianState.AM]
        assert am_rate.donation_rate == Decimal("2")
        assert am_rate.inheritance_rate == Decimal("2")

    def test_progressive_states_identified(self):
        """Test that progressive states are correctly identified."""
        progressive_states = [s for s, r in ITCMD_RATES.items() if r.progressive]
        non_progressive_states = [s for s, r in ITCMD_RATES.items() if not r.progressive]

        # Known progressive states
        assert BrazilianState.BA in progressive_states
        assert BrazilianState.RJ in progressive_states
        assert BrazilianState.SC in progressive_states

        # Known non-progressive states
        assert BrazilianState.SP in non_progressive_states
        assert BrazilianState.PR in non_progressive_states

    def test_get_itcmd_rate(self):
        """Test the get_itcmd_rate helper function."""
        sp_rate = get_itcmd_rate(BrazilianState.SP)
        assert sp_rate is not None
        assert sp_rate.donation_rate == Decimal("4")

    def test_list_states_by_lowest_rate(self):
        """Test that states are sorted by donation rate."""
        states = list_states_by_lowest_rate()

        assert len(states) == len(BrazilianState)
        assert states[0][0] == BrazilianState.AM  # Lowest rate (2%)
        assert states[0][1] == Decimal("2")

        # Verify sorting
        for i in range(1, len(states)):
            assert states[i][1] >= states[i - 1][1]


class TestITCMDCalculation:
    """Tests for ITCMD tax calculation."""

    def test_calculate_donation_sp(self):
        """Test donation ITCMD calculation for São Paulo."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("1000000"),
                ),
            ],
        )

        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.SP)

        # SP: 4% with exemption of ~R$89,450
        itcmd = analyzer.calculate_itcmd_donation(Decimal("1000000"))
        expected = (Decimal("1000000") - Decimal("89450")) * Decimal("0.04")
        assert itcmd == expected

    def test_calculate_donation_am(self):
        """Test donation ITCMD calculation for Amazonas (lowest rate)."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.AM)

        # AM: 2% without exemption
        itcmd = analyzer.calculate_itcmd_donation(Decimal("1000000"))
        expected = Decimal("1000000") * Decimal("0.02")
        assert itcmd == expected

    def test_calculate_inheritance_progressive(self):
        """Test inheritance ITCMD calculation for progressive state."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.RJ)

        # RJ: Progressive up to 8% with R$60k exemption
        itcmd = analyzer.calculate_itcmd_inheritance(Decimal("1000000"))
        expected = (Decimal("1000000") - Decimal("60000")) * Decimal("0.08")
        assert itcmd == expected

    def test_calculate_below_exemption(self):
        """Test ITCMD is zero when below exemption threshold."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.SP)

        # SP exemption is ~R$89,450
        itcmd = analyzer.calculate_itcmd_donation(Decimal("50000"))
        assert itcmd == Decimal("0")


class TestDonationVsInheritance:
    """Tests for donation vs inheritance comparison."""

    def test_suggests_donation_for_large_patrimony(self):
        """Test that donation is suggested for large patrimony."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("2000000"),
                ),
            ],
        )

        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.SP)
        suggestions = analyzer.analyze()

        # Should suggest donation vs inheritance comparison
        donation_suggestions = [
            s for s in suggestions
            if "Doação em Vida" in s.titulo
        ]
        assert len(donation_suggestions) > 0
        assert donation_suggestions[0].economia_potencial > 0

    def test_no_suggestion_for_small_patrimony(self):
        """Test that no suggestion for patrimony below threshold."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.POUPANCA,
                    codigo="01",
                    discriminacao="Poupança",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("100000"),
                ),
            ],
        )

        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.SP)
        suggestions = analyzer.analyze()

        # Should not suggest for small patrimony
        assert len(suggestions) == 0


class TestHoldingStructure:
    """Tests for family holding structure suggestions."""

    def test_suggests_holding_for_large_patrimony(self):
        """Test that holding is suggested for very large patrimony."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Imóvel 1",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("3000000"),
                ),
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Imóvel 2",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("2000000"),
                ),
            ],
        )

        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.SP)
        suggestions = analyzer.analyze()

        # Should suggest holding structure
        holding_suggestions = [
            s for s in suggestions
            if "Holding" in s.titulo
        ]
        assert len(holding_suggestions) > 0
        assert holding_suggestions[0].economia_potencial > 0

    def test_no_holding_for_medium_patrimony(self):
        """Test that holding is not suggested for medium patrimony."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Casa",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("800000"),
                ),
            ],
        )

        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.SP)
        suggestions = analyzer.analyze()

        # Should NOT suggest holding for medium patrimony
        holding_suggestions = [
            s for s in suggestions
            if "Holding" in s.titulo
        ]
        assert len(holding_suggestions) == 0


class TestStateComparison:
    """Tests for state ITCMD comparison."""

    def test_suggests_better_states(self):
        """Test that states with lower rates are suggested."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("2000000"),
                ),
            ],
        )

        # Use RJ which has high progressive rate
        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.RJ)
        suggestions = analyzer.analyze()

        # Should suggest comparison with other states
        state_suggestions = [
            s for s in suggestions
            if "Comparativo ITCMD" in s.titulo
        ]
        assert len(state_suggestions) > 0


class TestGradualDonation:
    """Tests for gradual donation strategy."""

    def test_suggests_gradual_donation_with_exemption(self):
        """Test that gradual donation is suggested when exemption exists."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("1000000"),
                ),
            ],
        )

        # SP has exemption of ~R$89k
        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.SP, num_heirs=3)
        suggestions = analyzer.analyze()

        # Should suggest gradual donation
        gradual_suggestions = [
            s for s in suggestions
            if "Doação Gradual" in s.titulo
        ]
        assert len(gradual_suggestions) > 0

    def test_no_gradual_for_state_without_exemption(self):
        """Test that gradual donation is not suggested when no exemption."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("1000000"),
                ),
            ],
        )

        # AM has no exemption
        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.AM)
        suggestions = analyzer.analyze()

        # Should NOT suggest gradual donation
        gradual_suggestions = [
            s for s in suggestions
            if "Doação Gradual" in s.titulo
        ]
        assert len(gradual_suggestions) == 0


class TestConvenienceFunction:
    """Tests for convenience functions."""

    def test_analyze_estate_planning_returns_list(self):
        """Test that the convenience function returns a list."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Apartamento",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("1000000"),
                ),
            ],
        )

        result = analyze_estate_planning(decl, BrazilianState.SP, 2)

        assert isinstance(result, list)

    def test_analyze_empty_declaration(self):
        """Test analysis of declaration with no assets."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        suggestions = analyze_estate_planning(decl)

        # Empty declaration should have no suggestions
        assert len(suggestions) == 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_handles_zero_patrimony(self):
        """Test that zero patrimony is handled correctly."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Imóvel vendido",
                    situacao_anterior=Decimal("500000"),
                    situacao_atual=Decimal("0"),
                ),
            ],
        )

        analyzer = EstatePlanningAnalyzer(decl)
        suggestions = analyzer.analyze()

        assert len(suggestions) == 0

    def test_minimum_heirs(self):
        """Test that minimum heirs is enforced."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        # Try to set 0 heirs
        analyzer = EstatePlanningAnalyzer(decl, num_heirs=0)
        assert analyzer.num_heirs == 1  # Should be minimum 1

    def test_real_estate_calculation(self):
        """Test that real estate is calculated separately."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Casa",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("1000000"),
                ),
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="41",
                    discriminacao="CDB",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("500000"),
                ),
            ],
        )

        analyzer = EstatePlanningAnalyzer(decl)

        assert analyzer._patrimonio_total == Decimal("1500000")
        assert analyzer._patrimonio_imoveis == Decimal("1000000")

    def test_suggestions_sorted_by_priority(self):
        """Test that suggestions are sorted by priority."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="01",
                    discriminacao="Imóvel grande",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("5000000"),
                ),
            ],
        )

        analyzer = EstatePlanningAnalyzer(decl, BrazilianState.SP, num_heirs=3)
        suggestions = analyzer.analyze()

        # Verify sorting by priority
        for i in range(1, len(suggestions)):
            assert suggestions[i].prioridade >= suggestions[i - 1].prioridade
