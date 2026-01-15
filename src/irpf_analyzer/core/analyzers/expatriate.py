"""Expatriate and tax residency analyzer for IRPF declarations.

This module provides specialized analysis for:
- Exit tax (imposto de saída) for those leaving Brazil
- Foreign tax credit calculation (crédito de imposto pago no exterior)
- DCBE (Declaração de Capitais Brasileiros no Exterior) requirements
- Tax treaty considerations

Based on Brazilian tax law for non-residents and expatriates.
"""

from decimal import Decimal
from enum import Enum
from typing import NamedTuple

from irpf_analyzer.core.models.analysis import (
    RiskLevel,
    Suggestion,
    Warning,
    WarningCategory,
)
from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import GrupoBem, TipoRendimento
from irpf_analyzer.core.rules.tax_constants import (
    LIMITE_DCBE_USD,
    obter_aliquota_marginal,
)


class TaxTreatyCountry(str, Enum):
    """Countries with tax treaties with Brazil."""

    # Countries with double taxation treaties
    ARGENTINA = "AR"
    AUSTRIA = "AT"
    BELGIUM = "BE"
    CANADA = "CA"
    CHILE = "CL"
    CHINA = "CN"
    CZECH_REPUBLIC = "CZ"
    DENMARK = "DK"
    ECUADOR = "EC"
    FINLAND = "FI"
    FRANCE = "FR"
    GERMANY = "DE"
    HUNGARY = "HU"
    INDIA = "IN"
    ISRAEL = "IL"
    ITALY = "IT"
    JAPAN = "JP"
    KOREA = "KR"
    LUXEMBOURG = "LU"
    MEXICO = "MX"
    NETHERLANDS = "NL"
    NORWAY = "NO"
    PERU = "PE"
    PHILIPPINES = "PH"
    PORTUGAL = "PT"
    RUSSIA = "RU"
    SINGAPORE = "SG"
    SLOVAKIA = "SK"
    SOUTH_AFRICA = "ZA"
    SPAIN = "ES"
    SWEDEN = "SE"
    SWITZERLAND = "CH"
    TRINIDAD_TOBAGO = "TT"
    TURKEY = "TR"
    UAE = "AE"
    UKRAINE = "UA"
    UK = "GB"
    USA = "US"
    VENEZUELA = "VE"


class ForeignAssetCategory(NamedTuple):
    """Category of foreign asset for analysis."""

    name: str
    exit_tax_rate: Decimal  # Rate for exit tax if applicable
    requires_carne_leao: bool  # If income needs monthly carnê-leão


class ExitTaxCalculation(NamedTuple):
    """Result of exit tax calculation."""

    asset_type: str
    acquisition_value: Decimal
    current_value: Decimal
    capital_gain: Decimal
    exit_tax: Decimal
    notes: str


class ForeignTaxCredit(NamedTuple):
    """Foreign tax credit calculation result."""

    country: str
    foreign_income: Decimal
    foreign_tax_paid: Decimal
    brazilian_tax_on_income: Decimal
    credit_allowed: Decimal
    excess_credit: Decimal
    notes: str


class ExpatriateAnalyzer:
    """Analyzer for expatriates and tax residents.

    Provides:
    - Exit tax analysis for permanent departure
    - Foreign tax credit calculation
    - DCBE requirement alerts
    - Tax treaty guidance
    """

    # Brazil country code
    BRAZIL_COUNTRY_CODE = "105"

    # Exit tax rates by asset type
    EXIT_TAX_RATES = {
        GrupoBem.IMOVEIS: Decimal("0.15"),  # 15% on capital gain
        GrupoBem.PARTICIPACOES_SOCIETARIAS: Decimal("0.15"),
        GrupoBem.APLICACOES_FINANCEIRAS: Decimal("0.15"),
        GrupoBem.CRIPTOATIVOS: Decimal("0.15"),
        GrupoBem.OUTROS_BENS: Decimal("0.15"),
    }

    # Progressive capital gains rates for foreign income (Lei 14.754/2023)
    CAPITAL_GAINS_RATES = [
        (Decimal("5000000"), Decimal("0.15")),  # Up to 5M: 15%
        (Decimal("10000000"), Decimal("0.175")),  # 5M-10M: 17.5%
        (Decimal("30000000"), Decimal("0.20")),  # 10M-30M: 20%
        (Decimal("999999999999"), Decimal("0.225")),  # Above 30M: 22.5%
    ]

    # Foreign income tax rate for carnê-leão
    CARNE_LEAO_RATE = Decimal("0.275")  # Maximum marginal rate

    # DCBE threshold in USD
    DCBE_THRESHOLD_USD = LIMITE_DCBE_USD

    # Assumed USD/BRL exchange rate (should be updated)
    USD_BRL_RATE = Decimal("5.50")

    # Minimum foreign assets to analyze
    MIN_FOREIGN_ASSETS = Decimal("10000")

    def __init__(
        self,
        declaration: Declaration,
        is_leaving_brazil: bool = False,
        foreign_tax_paid: Decimal = Decimal("0"),
    ) -> None:
        """Initialize analyzer with declaration data.

        Args:
            declaration: The IRPF declaration to analyze
            is_leaving_brazil: Whether taxpayer is leaving Brazil permanently
            foreign_tax_paid: Total tax paid in foreign countries
        """
        self.declaration = declaration
        self.is_leaving_brazil = is_leaving_brazil
        self.foreign_tax_paid = foreign_tax_paid
        self.suggestions: list[Suggestion] = []
        self.warnings: list[Warning] = []

        # Calculate foreign assets and income
        self._foreign_assets = self._calculate_foreign_assets()
        self._foreign_income = self._calculate_foreign_income()
        self._total_foreign_value = sum(
            a.situacao_atual for a in self._foreign_assets
        )

    def analyze(self) -> tuple[list[Suggestion], list[Warning]]:
        """Run all expatriate analysis.

        Returns:
            Tuple of (suggestions, warnings) found during analysis
        """
        self._check_dcbe_requirement()
        self._analyze_foreign_tax_credit()

        if self.is_leaving_brazil:
            self._analyze_exit_tax()

        self._check_tax_treaty_opportunities()

        return self.suggestions, self.warnings

    def _calculate_foreign_assets(self) -> list:
        """Get list of foreign assets from declaration."""
        foreign_assets = []
        for bem in self.declaration.bens_direitos:
            # Check if asset is foreign (not Brazil) or description suggests foreign
            if (
                bem.localizacao and bem.localizacao.pais != self.BRAZIL_COUNTRY_CODE
            ) or self._is_likely_foreign_asset(bem.discriminacao):
                foreign_assets.append(bem)
        return foreign_assets

    def _is_likely_foreign_asset(self, description: str) -> bool:
        """Check if asset description suggests foreign location."""
        foreign_indicators = [
            "exterior", "foreign", "usa", "eua", "united states",
            "europe", "europa", "avenue", "interactive brokers",
            "charles schwab", "fidelity", "vanguard", "td ameritrade",
            "usd", "eur", "gbp", "offshore", "international",
        ]
        desc_lower = description.lower()
        return any(ind in desc_lower for ind in foreign_indicators)

    def _calculate_foreign_income(self) -> Decimal:
        """Calculate total foreign income."""
        total = Decimal("0")
        for rendimento in self.declaration.rendimentos:
            if rendimento.tipo == TipoRendimento.RENDIMENTOS_EXTERIOR:
                total += rendimento.valor_anual
        return total

    def _check_dcbe_requirement(self) -> None:
        """Check if DCBE (foreign capital declaration) is required.

        DCBE is required when foreign assets exceed USD 1 million.
        Must be filed with Central Bank by April 5th.
        """
        if self._total_foreign_value < self.MIN_FOREIGN_ASSETS:
            return

        # Estimate value in USD
        value_in_usd = self._total_foreign_value / self.USD_BRL_RATE

        if value_in_usd >= self.DCBE_THRESHOLD_USD:
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"DCBE obrigatória: patrimônio no exterior estimado em "
                        f"USD {value_in_usd:,.0f} (R$ {self._total_foreign_value:,.2f}). "
                        f"A Declaração de Capitais Brasileiros no Exterior deve ser "
                        f"entregue ao Banco Central até 5 de abril."
                    ),
                    risco=RiskLevel.HIGH,
                    campo="bens_direitos",
                    categoria=WarningCategory.CONSISTENCIA,
                )
            )
        elif value_in_usd >= self.DCBE_THRESHOLD_USD * Decimal("0.8"):
            # Approaching threshold
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Atenção ao limite DCBE: patrimônio no exterior estimado em "
                        f"USD {value_in_usd:,.0f}. O limite para declaração obrigatória "
                        f"ao Banco Central é USD 1.000.000."
                    ),
                    risco=RiskLevel.MEDIUM,
                    campo="bens_direitos",
                    categoria=WarningCategory.CONSISTENCIA,
                    informativo=True,
                )
            )

    def _analyze_foreign_tax_credit(self) -> None:
        """Analyze foreign tax credit opportunities.

        Brazil allows credit for taxes paid abroad on income that is also
        taxed in Brazil, limited to the Brazilian tax on that income.
        """
        if self._foreign_income <= 0:
            return

        # Calculate Brazilian tax on foreign income
        brazilian_tax = self._calculate_tax_on_foreign_income()

        if self.foreign_tax_paid > 0:
            # Calculate allowable credit
            credit_allowed = min(self.foreign_tax_paid, brazilian_tax)
            excess = self.foreign_tax_paid - credit_allowed

            self.suggestions.append(
                Suggestion(
                    titulo="Crédito de imposto pago no exterior",
                    descricao=(
                        f"Imposto pago no exterior: R$ {self.foreign_tax_paid:,.2f}. "
                        f"Imposto brasileiro sobre renda exterior: R$ {brazilian_tax:,.2f}. "
                        f"Crédito aproveitável: R$ {credit_allowed:,.2f}. "
                        + (
                            f"Excesso não compensável: R$ {excess:,.2f}. "
                            if excess > 0 else ""
                        )
                        + "Utilize a ficha 'Imposto Pago/Retido' para informar o crédito."
                    ),
                    economia_potencial=credit_allowed,
                    prioridade=1,
                )
            )
        else:
            # No foreign tax declared - suggest checking
            self.suggestions.append(
                Suggestion(
                    titulo="Verifique impostos pagos no exterior",
                    descricao=(
                        f"Você declarou R$ {self._foreign_income:,.2f} de renda do exterior. "
                        f"Se pagou imposto no país de origem, pode ter direito a crédito "
                        f"de até R$ {brazilian_tax:,.2f} (imposto brasileiro sobre essa renda). "
                        f"Guarde comprovantes de pagamento de impostos estrangeiros."
                    ),
                    economia_potencial=brazilian_tax,
                    prioridade=2,
                )
            )

    def _calculate_tax_on_foreign_income(self) -> Decimal:
        """Calculate Brazilian tax on foreign income."""
        # Foreign income is taxed at progressive rates
        aliquota = obter_aliquota_marginal(
            self.declaration.total_rendimentos_tributaveis
        )
        return self._foreign_income * aliquota

    def _analyze_exit_tax(self) -> None:
        """Analyze exit tax implications for leaving Brazil.

        When leaving Brazil permanently, unrealized capital gains on
        certain assets are taxed as if sold (imposto de saída).
        """
        if not self._foreign_assets and not self.declaration.bens_direitos:
            return

        exit_tax_items: list[ExitTaxCalculation] = []
        total_exit_tax = Decimal("0")

        # Analyze each asset
        for bem in self.declaration.bens_direitos:
            if bem.situacao_atual <= bem.situacao_anterior:
                continue  # No gain

            # Calculate unrealized gain
            gain = bem.situacao_atual - bem.situacao_anterior

            if gain <= 0:
                continue

            # Get applicable rate
            rate = self.EXIT_TAX_RATES.get(bem.grupo, Decimal("0.15"))
            exit_tax = gain * rate

            if exit_tax > Decimal("100"):  # Only report significant amounts
                exit_tax_items.append(
                    ExitTaxCalculation(
                        asset_type=bem.grupo.value,
                        acquisition_value=bem.situacao_anterior,
                        current_value=bem.situacao_atual,
                        capital_gain=gain,
                        exit_tax=exit_tax,
                        notes=bem.discriminacao[:50],
                    )
                )
                total_exit_tax += exit_tax

        if total_exit_tax > 0:
            # Build details string
            details = []
            for item in exit_tax_items[:5]:  # Top 5 items
                details.append(
                    f"• {item.notes}: ganho R$ {item.capital_gain:,.2f} → "
                    f"imposto R$ {item.exit_tax:,.2f}"
                )

            self.warnings.append(
                Warning(
                    mensagem=(
                        f"IMPOSTO DE SAÍDA: Ao deixar o Brasil definitivamente, "
                        f"há tributação sobre ganhos não realizados. "
                        f"Imposto estimado: R$ {total_exit_tax:,.2f}.\n"
                        + "\n".join(details)
                    ),
                    risco=RiskLevel.HIGH,
                    campo="bens_direitos",
                    categoria=WarningCategory.CONSISTENCIA,
                    valor_impacto=total_exit_tax,
                )
            )

            # Add suggestion about timing
            self.suggestions.append(
                Suggestion(
                    titulo="Planejamento do imposto de saída",
                    descricao=(
                        f"Imposto de saída estimado: R$ {total_exit_tax:,.2f}. "
                        f"Considere estratégias para reduzir esse impacto:\n"
                        f"• Vender ativos com prejuízo antes da saída para compensação\n"
                        f"• Verificar tratados de bitributação com o país de destino\n"
                        f"• Avaliar momento da mudança de residência fiscal\n"
                        f"• Manter no Brasil apenas ativos essenciais\n"
                        f"Prazo: Comunicação de Saída Definitiva até último dia do mês seguinte."
                    ),
                    economia_potencial=None,
                    prioridade=1,
                )
            )

    def _check_tax_treaty_opportunities(self) -> None:
        """Check for tax treaty optimization opportunities."""
        if self._foreign_income <= Decimal("10000"):
            return  # Not significant enough

        # Provide general guidance about treaties
        self.suggestions.append(
            Suggestion(
                titulo="Tratados de bitributação",
                descricao=(
                    f"Brasil possui tratados com {len(TaxTreatyCountry)} países "
                    f"para evitar dupla tributação. Com renda exterior de "
                    f"R$ {self._foreign_income:,.2f}, verifique:\n"
                    f"• Se o país de origem tem tratado com Brasil\n"
                    f"• Qual país tem direito prioritário de tributação\n"
                    f"• Limite de crédito de imposto permitido pelo tratado\n"
                    f"• Formulários de residência fiscal necessários\n"
                    f"Países com tratado incluem: EUA, Alemanha, Portugal, "
                    f"Reino Unido, França, Japão, entre outros."
                ),
                economia_potencial=None,
                prioridade=4,  # Informational
            )
        )

    def calculate_exit_tax(self) -> list[ExitTaxCalculation]:
        """Calculate detailed exit tax for all applicable assets.

        Returns:
            List of exit tax calculations by asset
        """
        calculations = []

        for bem in self.declaration.bens_direitos:
            gain = bem.situacao_atual - bem.situacao_anterior
            if gain <= 0:
                continue

            rate = self.EXIT_TAX_RATES.get(bem.grupo, Decimal("0.15"))
            tax = gain * rate

            calculations.append(
                ExitTaxCalculation(
                    asset_type=bem.grupo.value,
                    acquisition_value=bem.situacao_anterior,
                    current_value=bem.situacao_atual,
                    capital_gain=gain,
                    exit_tax=tax,
                    notes=bem.discriminacao[:50],
                )
            )

        return calculations

    def calculate_foreign_tax_credit(
        self,
        country: str,
        foreign_income: Decimal,
        foreign_tax_paid: Decimal,
    ) -> ForeignTaxCredit:
        """Calculate foreign tax credit for a specific country/income.

        Args:
            country: Country code or name
            foreign_income: Income received from that country
            foreign_tax_paid: Tax paid in that country

        Returns:
            ForeignTaxCredit calculation result
        """
        # Calculate Brazilian tax on this income
        aliquota = obter_aliquota_marginal(
            self.declaration.total_rendimentos_tributaveis
        )
        brazilian_tax = foreign_income * aliquota

        # Credit is limited to Brazilian tax on that income
        credit_allowed = min(foreign_tax_paid, brazilian_tax)
        excess = foreign_tax_paid - credit_allowed

        notes = ""
        if excess > 0:
            notes = (
                f"Excesso de R$ {excess:,.2f} não pode ser compensado. "
                f"Verifique se há tratado de bitributação para regras especiais."
            )
        elif credit_allowed == foreign_tax_paid:
            notes = "Crédito integral aproveitado."

        return ForeignTaxCredit(
            country=country,
            foreign_income=foreign_income,
            foreign_tax_paid=foreign_tax_paid,
            brazilian_tax_on_income=brazilian_tax,
            credit_allowed=credit_allowed,
            excess_credit=excess,
            notes=notes,
        )


def analyze_expatriate(
    declaration: Declaration,
    is_leaving_brazil: bool = False,
    foreign_tax_paid: Decimal = Decimal("0"),
) -> tuple[list[Suggestion], list[Warning]]:
    """Convenience function to run expatriate analysis.

    Args:
        declaration: The IRPF declaration to analyze
        is_leaving_brazil: Whether taxpayer is leaving Brazil permanently
        foreign_tax_paid: Total tax paid in foreign countries

    Returns:
        Tuple of (suggestions, warnings) found
    """
    analyzer = ExpatriateAnalyzer(
        declaration,
        is_leaving_brazil=is_leaving_brazil,
        foreign_tax_paid=foreign_tax_paid,
    )
    return analyzer.analyze()
