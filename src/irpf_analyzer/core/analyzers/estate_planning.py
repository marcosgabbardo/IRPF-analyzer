"""Estate planning analyzer for succession optimization.

This module provides estate planning analysis including:
- ITCMD (donation/inheritance tax) comparison between donation in life vs inheritance
- State-specific ITCMD rates for all Brazilian states
- Family holding structure suggestions for tax optimization
- Patrimony transfer cost projections

Based on Brazilian state tax regulations (ITCMD) as of 2025.
"""

from decimal import Decimal
from enum import Enum
from typing import NamedTuple

from irpf_analyzer.core.models.analysis import Suggestion
from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import GrupoBem


class BrazilianState(str, Enum):
    """Brazilian states and Federal District."""

    AC = "AC"  # Acre
    AL = "AL"  # Alagoas
    AM = "AM"  # Amazonas
    AP = "AP"  # Amapá
    BA = "BA"  # Bahia
    CE = "CE"  # Ceará
    DF = "DF"  # Distrito Federal
    ES = "ES"  # Espírito Santo
    GO = "GO"  # Goiás
    MA = "MA"  # Maranhão
    MG = "MG"  # Minas Gerais
    MS = "MS"  # Mato Grosso do Sul
    MT = "MT"  # Mato Grosso
    PA = "PA"  # Pará
    PB = "PB"  # Paraíba
    PE = "PE"  # Pernambuco
    PI = "PI"  # Piauí
    PR = "PR"  # Paraná
    RJ = "RJ"  # Rio de Janeiro
    RN = "RN"  # Rio Grande do Norte
    RO = "RO"  # Rondônia
    RR = "RR"  # Roraima
    RS = "RS"  # Rio Grande do Sul
    SC = "SC"  # Santa Catarina
    SE = "SE"  # Sergipe
    SP = "SP"  # São Paulo
    TO = "TO"  # Tocantins


class ITCMDRate(NamedTuple):
    """ITCMD rate information for a state."""

    state: BrazilianState
    donation_rate: Decimal  # Taxa para doação
    inheritance_rate: Decimal  # Taxa para herança (causa mortis)
    progressive: bool  # Se a alíquota é progressiva
    max_rate: Decimal  # Alíquota máxima (para estados progressivos)
    exemption_limit: Decimal  # Limite de isenção (se houver)
    notes: str  # Observações


# ITCMD rates by state (updated 2025)
# Sources: State tax legislation (Lei do ITCMD de cada estado)
# Note: Some states have progressive rates based on the value transferred
ITCMD_RATES: dict[BrazilianState, ITCMDRate] = {
    BrazilianState.AC: ITCMDRate(
        BrazilianState.AC, Decimal("4"), Decimal("4"), False, Decimal("4"),
        Decimal("0"), "Alíquota única de 4%"
    ),
    BrazilianState.AL: ITCMDRate(
        BrazilianState.AL, Decimal("4"), Decimal("4"), False, Decimal("4"),
        Decimal("0"), "Alíquota única de 4%"
    ),
    BrazilianState.AM: ITCMDRate(
        BrazilianState.AM, Decimal("2"), Decimal("2"), False, Decimal("2"),
        Decimal("0"), "Alíquota única de 2% (mais baixa do Brasil)"
    ),
    BrazilianState.AP: ITCMDRate(
        BrazilianState.AP, Decimal("4"), Decimal("4"), False, Decimal("4"),
        Decimal("0"), "Alíquota única de 4%"
    ),
    BrazilianState.BA: ITCMDRate(
        BrazilianState.BA, Decimal("3.5"), Decimal("8"), True, Decimal("8"),
        Decimal("100000"), "Progressiva: 3.5% até R$100k, até 8% acima de R$1M"
    ),
    BrazilianState.CE: ITCMDRate(
        BrazilianState.CE, Decimal("4"), Decimal("8"), True, Decimal("8"),
        Decimal("50000"), "Progressiva: até 8% para heranças > R$600k"
    ),
    BrazilianState.DF: ITCMDRate(
        BrazilianState.DF, Decimal("4"), Decimal("6"), True, Decimal("6"),
        Decimal("0"), "Progressiva: 4% doação, 4-6% herança"
    ),
    BrazilianState.ES: ITCMDRate(
        BrazilianState.ES, Decimal("4"), Decimal("4"), False, Decimal("4"),
        Decimal("0"), "Alíquota única de 4%"
    ),
    BrazilianState.GO: ITCMDRate(
        BrazilianState.GO, Decimal("4"), Decimal("8"), True, Decimal("8"),
        Decimal("25000"), "Progressiva: até 8% para heranças > R$200k"
    ),
    BrazilianState.MA: ITCMDRate(
        BrazilianState.MA, Decimal("3"), Decimal("7"), True, Decimal("7"),
        Decimal("0"), "Progressiva: 3% doação, 3-7% herança"
    ),
    BrazilianState.MG: ITCMDRate(
        BrazilianState.MG, Decimal("5"), Decimal("5"), False, Decimal("5"),
        Decimal("48000"), "5% com isenção até R$48k para doações"
    ),
    BrazilianState.MS: ITCMDRate(
        BrazilianState.MS, Decimal("3"), Decimal("6"), True, Decimal("6"),
        Decimal("0"), "Progressiva: 3% doação, 3-6% herança"
    ),
    BrazilianState.MT: ITCMDRate(
        BrazilianState.MT, Decimal("4"), Decimal("8"), True, Decimal("8"),
        Decimal("0"), "Progressiva: 2-4% doação, 2-8% herança"
    ),
    BrazilianState.PA: ITCMDRate(
        BrazilianState.PA, Decimal("4"), Decimal("6"), True, Decimal("6"),
        Decimal("0"), "Progressiva: 4% doação, 4-6% herança"
    ),
    BrazilianState.PB: ITCMDRate(
        BrazilianState.PB, Decimal("4"), Decimal("8"), True, Decimal("8"),
        Decimal("20000"), "Progressiva: 2-8% com isenção até R$20k"
    ),
    BrazilianState.PE: ITCMDRate(
        BrazilianState.PE, Decimal("5"), Decimal("8"), True, Decimal("8"),
        Decimal("50000"), "Progressiva: 2-8% com isenção até R$50k"
    ),
    BrazilianState.PI: ITCMDRate(
        BrazilianState.PI, Decimal("4"), Decimal("6"), True, Decimal("6"),
        Decimal("0"), "Progressiva: 4% doação, 4-6% herança"
    ),
    BrazilianState.PR: ITCMDRate(
        BrazilianState.PR, Decimal("4"), Decimal("4"), False, Decimal("4"),
        Decimal("0"), "Alíquota única de 4%"
    ),
    BrazilianState.RJ: ITCMDRate(
        BrazilianState.RJ, Decimal("4"), Decimal("8"), True, Decimal("8"),
        Decimal("60000"), "Progressiva: 4-8% com isenção até R$60k"
    ),
    BrazilianState.RN: ITCMDRate(
        BrazilianState.RN, Decimal("3"), Decimal("6"), True, Decimal("6"),
        Decimal("0"), "Progressiva: 3% doação, 3-6% herança"
    ),
    BrazilianState.RO: ITCMDRate(
        BrazilianState.RO, Decimal("4"), Decimal("4"), False, Decimal("4"),
        Decimal("0"), "Alíquota única de 4%"
    ),
    BrazilianState.RR: ITCMDRate(
        BrazilianState.RR, Decimal("4"), Decimal("4"), False, Decimal("4"),
        Decimal("0"), "Alíquota única de 4%"
    ),
    BrazilianState.RS: ITCMDRate(
        BrazilianState.RS, Decimal("4"), Decimal("6"), True, Decimal("6"),
        Decimal("0"), "Progressiva: 3-6% para heranças"
    ),
    BrazilianState.SC: ITCMDRate(
        BrazilianState.SC, Decimal("4"), Decimal("8"), True, Decimal("8"),
        Decimal("20000"), "Progressiva: 1-8% com isenção até R$20k"
    ),
    BrazilianState.SE: ITCMDRate(
        BrazilianState.SE, Decimal("4"), Decimal("8"), True, Decimal("8"),
        Decimal("50000"), "Progressiva: 4-8% com isenção até R$50k"
    ),
    BrazilianState.SP: ITCMDRate(
        BrazilianState.SP, Decimal("4"), Decimal("4"), False, Decimal("4"),
        Decimal("89450"), "4% com isenção até ~R$89k (2.500 UFESPs)"
    ),
    BrazilianState.TO: ITCMDRate(
        BrazilianState.TO, Decimal("4"), Decimal("8"), True, Decimal("8"),
        Decimal("25000"), "Progressiva: 2-8% com isenção até R$25k"
    ),
}


class HoldingBenefit(NamedTuple):
    """Benefits of family holding structure."""

    category: str
    description: str
    potential_savings_pct: Decimal  # Percentage savings estimate


class EstatePlanningAnalyzer:
    """Analyzer for estate planning and succession optimization.

    Provides:
    - ITCMD comparison between donation in life vs inheritance
    - State-specific tax calculations
    - Family holding structure recommendations
    - Patrimony transfer cost projections
    """

    # Minimum patrimony to suggest estate planning (R$ 500k)
    PATRIMONIO_MINIMO_PLANEJAMENTO = Decimal("500000")

    # Minimum patrimony to suggest family holding (R$ 2M)
    PATRIMONIO_MINIMO_HOLDING = Decimal("2000000")

    # Typical costs of holding structure
    CUSTO_ABERTURA_HOLDING = Decimal("15000")  # Estimated setup cost
    CUSTO_MANUTENCAO_ANUAL = Decimal("8000")  # Annual maintenance

    # Tax benefits of holding structure
    HOLDING_BENEFITS: list[HoldingBenefit] = [
        HoldingBenefit(
            "ITCMD",
            "Redução do valor venal dos imóveis para doação de quotas",
            Decimal("20"),  # ~20% reduction on property valuation
        ),
        HoldingBenefit(
            "ITBI",
            "Isenção de ITBI na integralização de imóveis ao capital",
            Decimal("3"),  # Saves 3% ITBI
        ),
        HoldingBenefit(
            "Ganho de Capital",
            "Diferimento do ganho de capital na integralização",
            Decimal("15"),  # Defers 15% capital gains tax
        ),
        HoldingBenefit(
            "Inventário",
            "Evita processo de inventário judicial ou extrajudicial",
            Decimal("10"),  # Saves ~10% in inventory costs
        ),
        HoldingBenefit(
            "Proteção Patrimonial",
            "Blindagem contra credores pessoais dos sócios",
            Decimal("0"),  # Non-monetary benefit
        ),
    ]

    def __init__(
        self,
        declaration: Declaration,
        state: BrazilianState = BrazilianState.SP,
        num_heirs: int = 2,
    ) -> None:
        """Initialize analyzer with declaration data.

        Args:
            declaration: The IRPF declaration to analyze
            state: Brazilian state for ITCMD calculation (default: SP)
            num_heirs: Number of heirs for inheritance calculation (default: 2)
        """
        self.declaration = declaration
        self.state = state
        self.num_heirs = max(1, num_heirs)
        self.suggestions: list[Suggestion] = []

        # Calculate total patrimony
        self._patrimonio_total = self._calculate_patrimony()
        self._patrimonio_imoveis = self._calculate_real_estate()

    def analyze(self) -> list[Suggestion]:
        """Run all estate planning checks.

        Returns:
            List of suggestions for estate planning optimization
        """
        # Only analyze if patrimony is significant
        if self._patrimonio_total < self.PATRIMONIO_MINIMO_PLANEJAMENTO:
            return []

        self._analyze_donation_vs_inheritance()
        self._analyze_state_comparison()
        self._analyze_holding_opportunity()
        self._analyze_gradual_donation()

        return sorted(self.suggestions, key=lambda s: s.prioridade)

    def _calculate_patrimony(self) -> Decimal:
        """Calculate total patrimony from declaration."""
        return sum(bem.situacao_atual for bem in self.declaration.bens_direitos)

    def _calculate_real_estate(self) -> Decimal:
        """Calculate real estate patrimony."""
        return sum(
            bem.situacao_atual
            for bem in self.declaration.bens_direitos
            if bem.grupo == GrupoBem.IMOVEIS
        )

    def calculate_itcmd_donation(
        self,
        value: Decimal,
        state: BrazilianState | None = None,
    ) -> Decimal:
        """Calculate ITCMD for donation.

        Args:
            value: Value to be donated
            state: State for calculation (uses analyzer's state if None)

        Returns:
            ITCMD tax amount for donation
        """
        state = state or self.state
        rate_info = ITCMD_RATES.get(state)

        if not rate_info:
            return value * Decimal("0.04")  # Default 4%

        # Apply exemption if applicable
        taxable_value = max(Decimal("0"), value - rate_info.exemption_limit)

        if taxable_value <= 0:
            return Decimal("0")

        return taxable_value * (rate_info.donation_rate / 100)

    def calculate_itcmd_inheritance(
        self,
        value: Decimal,
        state: BrazilianState | None = None,
    ) -> Decimal:
        """Calculate ITCMD for inheritance (causa mortis).

        Args:
            value: Value to be inherited
            state: State for calculation (uses analyzer's state if None)

        Returns:
            ITCMD tax amount for inheritance
        """
        state = state or self.state
        rate_info = ITCMD_RATES.get(state)

        if not rate_info:
            return value * Decimal("0.04")  # Default 4%

        # Apply exemption if applicable
        taxable_value = max(Decimal("0"), value - rate_info.exemption_limit)

        if taxable_value <= 0:
            return Decimal("0")

        # For progressive states, use max rate for simplicity
        # In practice, would need full bracket calculation
        if rate_info.progressive:
            effective_rate = rate_info.max_rate / 100
        else:
            effective_rate = rate_info.inheritance_rate / 100

        return taxable_value * effective_rate

    def _analyze_donation_vs_inheritance(self) -> None:
        """Compare costs of donation in life vs inheritance."""
        patrimonio = self._patrimonio_total

        # Calculate ITCMD for each scenario
        itcmd_donation = self.calculate_itcmd_donation(patrimonio)
        itcmd_inheritance = self.calculate_itcmd_inheritance(patrimonio)

        # Estimate inventory costs (5-15% of estate value)
        custo_inventario = patrimonio * Decimal("0.08")  # 8% average

        # Total inheritance cost
        custo_total_heranca = itcmd_inheritance + custo_inventario

        # Savings from donation in life
        economia = custo_total_heranca - itcmd_donation

        rate_info = ITCMD_RATES.get(self.state)
        state_notes = rate_info.notes if rate_info else ""

        if economia > Decimal("1000"):
            self.suggestions.append(
                Suggestion(
                    titulo="Doação em Vida vs Herança",
                    descricao=(
                        f"Patrimônio atual: R$ {patrimonio:,.2f}\n\n"
                        f"**Cenário 1 - Doação em vida:**\n"
                        f"• ITCMD ({self.state.value}): R$ {itcmd_donation:,.2f}\n\n"
                        f"**Cenário 2 - Herança (inventário):**\n"
                        f"• ITCMD ({self.state.value}): R$ {itcmd_inheritance:,.2f}\n"
                        f"• Custos de inventário (~8%): R$ {custo_inventario:,.2f}\n"
                        f"• Total: R$ {custo_total_heranca:,.2f}\n\n"
                        f"**Economia com doação em vida: R$ {economia:,.2f}**\n\n"
                        f"Nota: {state_notes}"
                    ),
                    economia_potencial=economia,
                    prioridade=1,
                )
            )

    def _analyze_state_comparison(self) -> None:
        """Compare ITCMD rates across states for optimization."""
        patrimonio = self._patrimonio_total
        current_rate = ITCMD_RATES.get(self.state)

        if not current_rate:
            return

        # Find states with lower donation rates
        better_states: list[tuple[BrazilianState, Decimal, Decimal]] = []

        for state, rate_info in ITCMD_RATES.items():
            if state == self.state:
                continue

            current_cost = self.calculate_itcmd_donation(patrimonio, self.state)
            other_cost = self.calculate_itcmd_donation(patrimonio, state)
            savings = current_cost - other_cost

            if savings > patrimonio * Decimal("0.005"):  # >0.5% savings
                better_states.append((state, rate_info.donation_rate, savings))

        # Sort by savings
        better_states.sort(key=lambda x: x[2], reverse=True)

        if better_states:
            top_states = better_states[:3]
            states_info = "\n".join(
                f"• {s.value}: {r}% (economia R$ {e:,.2f})"
                for s, r, e in top_states
            )

            self.suggestions.append(
                Suggestion(
                    titulo="Comparativo ITCMD por Estado",
                    descricao=(
                        f"Seu estado ({self.state.value}) tem alíquota de "
                        f"{current_rate.donation_rate}% para doação.\n\n"
                        f"Estados com menor tributação:\n{states_info}\n\n"
                        f"Nota: A mudança de domicílio fiscal requer planejamento "
                        f"e deve ser avaliada com assessoria jurídica."
                    ),
                    economia_potencial=top_states[0][2] if top_states else None,
                    prioridade=3,
                )
            )

    def _analyze_holding_opportunity(self) -> None:
        """Analyze opportunity for family holding structure."""
        patrimonio = self._patrimonio_total
        imoveis = self._patrimonio_imoveis

        if patrimonio < self.PATRIMONIO_MINIMO_HOLDING:
            return

        # Calculate potential savings
        itcmd_direto = self.calculate_itcmd_donation(patrimonio)

        # Holding reduces property valuation by ~20-30% for ITCMD purposes
        # (quotas valued at book value, not market value)
        patrimonio_holding = patrimonio * Decimal("0.75")  # 25% discount
        itcmd_holding = self.calculate_itcmd_donation(patrimonio_holding)

        economia_itcmd = itcmd_direto - itcmd_holding

        # ITBI savings (3% on real estate integralização)
        economia_itbi = imoveis * Decimal("0.03")

        # Inventory savings
        economia_inventario = patrimonio * Decimal("0.08")

        # Total potential savings
        economia_total = economia_itcmd + economia_itbi + economia_inventario

        # Deduct holding costs (setup + 10 years maintenance)
        custo_holding = self.CUSTO_ABERTURA_HOLDING + (
            self.CUSTO_MANUTENCAO_ANUAL * 10
        )

        economia_liquida = economia_total - custo_holding

        if economia_liquida > Decimal("10000"):
            benefits_list = "\n".join(
                f"• {b.category}: {b.description}"
                for b in self.HOLDING_BENEFITS
            )

            self.suggestions.append(
                Suggestion(
                    titulo="Estrutura de Holding Familiar",
                    descricao=(
                        f"Com patrimônio de R$ {patrimonio:,.2f} "
                        f"(imóveis: R$ {imoveis:,.2f}), uma holding familiar "
                        f"pode trazer economia significativa.\n\n"
                        f"**Benefícios:**\n{benefits_list}\n\n"
                        f"**Projeção de economia:**\n"
                        f"• ITCMD (desconto no valor): R$ {economia_itcmd:,.2f}\n"
                        f"• ITBI (isenção integralização): R$ {economia_itbi:,.2f}\n"
                        f"• Inventário evitado: R$ {economia_inventario:,.2f}\n"
                        f"• (-) Custos da holding (10 anos): R$ {custo_holding:,.2f}\n"
                        f"• **Economia líquida: R$ {economia_liquida:,.2f}**\n\n"
                        f"Recomendação: Consulte advogado tributarista e contador "
                        f"para análise personalizada."
                    ),
                    economia_potencial=economia_liquida,
                    prioridade=2,
                )
            )

    def _analyze_gradual_donation(self) -> None:
        """Analyze gradual donation strategy to use exemptions."""
        patrimonio = self._patrimonio_total
        rate_info = ITCMD_RATES.get(self.state)

        if not rate_info or rate_info.exemption_limit <= 0:
            return

        exemption = rate_info.exemption_limit
        num_heirs = self.num_heirs

        # Calculate how many years to transfer via exemption
        annual_exempt_transfer = exemption * num_heirs
        years_to_transfer = (
            int(patrimonio / annual_exempt_transfer) + 1
            if annual_exempt_transfer > 0 else 0
        )

        if years_to_transfer <= 20 and annual_exempt_transfer > Decimal("10000"):
            economia_total = self.calculate_itcmd_donation(patrimonio)

            self.suggestions.append(
                Suggestion(
                    titulo="Doação Gradual com Isenção",
                    descricao=(
                        f"O estado {self.state.value} oferece isenção de ITCMD "
                        f"para doações até R$ {exemption:,.2f} por donatário.\n\n"
                        f"**Estratégia:**\n"
                        f"• Doação anual por herdeiro: R$ {exemption:,.2f}\n"
                        f"• Número de herdeiros: {num_heirs}\n"
                        f"• Transferência anual isenta: R$ {annual_exempt_transfer:,.2f}\n"
                        f"• Tempo para transferir patrimônio: ~{years_to_transfer} anos\n\n"
                        f"**Economia potencial: R$ {economia_total:,.2f}** "
                        f"(ITCMD que seria pago em doação única)"
                    ),
                    economia_potencial=economia_total,
                    prioridade=2,
                )
            )


def analyze_estate_planning(
    declaration: Declaration,
    state: BrazilianState = BrazilianState.SP,
    num_heirs: int = 2,
) -> list[Suggestion]:
    """Convenience function to run estate planning analysis.

    Args:
        declaration: The IRPF declaration to analyze
        state: Brazilian state for ITCMD calculation
        num_heirs: Number of heirs for inheritance calculation

    Returns:
        List of estate planning suggestions
    """
    analyzer = EstatePlanningAnalyzer(declaration, state, num_heirs)
    return analyzer.analyze()


def get_itcmd_rate(state: BrazilianState) -> ITCMDRate | None:
    """Get ITCMD rate information for a state.

    Args:
        state: Brazilian state

    Returns:
        ITCMDRate with tax information or None if not found
    """
    return ITCMD_RATES.get(state)


def list_states_by_lowest_rate() -> list[tuple[BrazilianState, Decimal]]:
    """List states ordered by lowest ITCMD donation rate.

    Returns:
        List of (state, rate) tuples sorted by ascending rate
    """
    return sorted(
        [(s, r.donation_rate) for s, r in ITCMD_RATES.items()],
        key=lambda x: x[1],
    )
