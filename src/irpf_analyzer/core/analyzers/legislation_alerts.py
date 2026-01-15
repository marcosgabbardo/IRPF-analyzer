"""Legislation changes alert analyzer for IRPF declarations.

This module monitors and alerts about legislative changes that may affect taxpayers:
- New tax rules and exemptions (Lei 15.270/2025 - Reforma IR 2026)
- Changes in deduction limits
- New reporting obligations
- Cryptocurrency regulations (IN RFB 1888/2019)
- International tax changes (exit tax, DCBE)

The analyzer checks the declaration against current and upcoming legislation,
alerting taxpayers about rules that affect their specific situation.
"""

from dataclasses import dataclass
from datetime import date
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
from irpf_analyzer.core.models.enums import GrupoBem
from irpf_analyzer.core.rules.tax_constants import (
    GANHO_CAPITAL_CRIPTO_MENSAL,
    ISENCAO_ANUAL_2026,
    ISENCAO_MENSAL_2026,
    LIMITE_DCBE_USD,
    LIMITE_IRPFM,
    LIMITE_IRPFM_MAXIMO,
    OBRIGATORIEDADE_PATRIMONIO,
    OBRIGATORIEDADE_RENDIMENTOS_ISENTOS,
    OBRIGATORIEDADE_RENDIMENTOS_TRIBUTAVEIS,
    PATRIMONIO_CRIPTO_OBRIGATORIO,
    REDUCAO_ANUAL_LIMITE_2026,
)


class LegislationCategory(str, Enum):
    """Category of legislation change."""

    TAX_REFORM = "tax_reform"  # IR reform (Lei 15.270/2025)
    DEDUCTION_LIMITS = "deduction_limits"  # Deduction limit changes
    REPORTING_OBLIGATION = "reporting_obligation"  # New reporting requirements
    CRYPTOCURRENCY = "cryptocurrency"  # Crypto regulations
    INTERNATIONAL = "international"  # International tax changes
    CAPITAL_GAINS = "capital_gains"  # Capital gains changes
    SOCIAL_SECURITY = "social_security"  # INSS changes


class ImpactLevel(str, Enum):
    """Impact level of a legislation change."""

    HIGH = "alto"  # Significant financial impact
    MEDIUM = "medio"  # Moderate impact
    LOW = "baixo"  # Minor impact
    INFORMATIONAL = "informativo"  # Good to know


class LegislationChange(NamedTuple):
    """Represents a legislation change."""

    name: str
    description: str
    effective_date: date
    category: LegislationCategory
    impact_level: ImpactLevel
    law_reference: str
    details: str


@dataclass
class LegislationAlert:
    """Alert about a legislation change affecting the taxpayer."""

    change: LegislationChange
    applies_to_taxpayer: bool
    reason: str
    potential_impact: Decimal | None = None
    action_required: str | None = None


class LegislationAlertsAnalyzer:
    """Analyzer for legislation changes affecting taxpayers.

    Monitors legislative changes and alerts taxpayers about:
    - New rules that affect their declaration
    - Upcoming changes they should prepare for
    - Changes in deduction limits
    - New reporting obligations
    """

    # Database of recent and upcoming legislation changes
    LEGISLATION_CHANGES: list[LegislationChange] = [
        # === Lei 15.270/2025 - IR Reform 2026 ===
        LegislationChange(
            name="Isenção IR até R$ 5.000/mês",
            description="Nova faixa de isenção para rendimentos até R$ 5.000 mensais",
            effective_date=date(2026, 1, 1),
            category=LegislationCategory.TAX_REFORM,
            impact_level=ImpactLevel.HIGH,
            law_reference="Lei 15.270/2025",
            details=(
                "Rendimentos até R$ 5.000/mês (R$ 60.000/ano) ficam isentos de IR. "
                "Entre R$ 5.000 e R$ 7.350/mês há redução progressiva do imposto."
            ),
        ),
        LegislationChange(
            name="IRPFM - Imposto Mínimo para Alta Renda",
            description="Contribuintes com renda > R$ 600k/ano terão imposto mínimo progressivo",
            effective_date=date(2026, 1, 1),
            category=LegislationCategory.TAX_REFORM,
            impact_level=ImpactLevel.HIGH,
            law_reference="Lei 15.270/2025",
            details=(
                "Renda entre R$ 600k e R$ 1,2M/ano: imposto mínimo progressivo até 10%. "
                "Renda acima de R$ 1,2M/ano: alíquota efetiva mínima de 10%. "
                "Inclui rendimentos isentos (dividendos, LCI/LCA) na base de cálculo."
            ),
        ),
        LegislationChange(
            name="Redução Progressiva R$ 5k-7,35k",
            description="Faixa de transição com redução gradual do imposto",
            effective_date=date(2026, 1, 1),
            category=LegislationCategory.TAX_REFORM,
            impact_level=ImpactLevel.MEDIUM,
            law_reference="Lei 15.270/2025",
            details=(
                "Para rendimentos entre R$ 5.000 e R$ 7.350 mensais, "
                "há uma redução progressiva de até R$ 312,89 no imposto devido, "
                "criando uma transição suave para evitar o 'cliff effect'."
            ),
        ),
        # === Cryptocurrency Regulations ===
        LegislationChange(
            name="Declaração Mensal Criptoativos > R$ 35k",
            description="Obrigação de declarar operações mensais com ganho > R$ 35.000",
            effective_date=date(2019, 8, 1),
            category=LegislationCategory.CRYPTOCURRENCY,
            impact_level=ImpactLevel.HIGH,
            law_reference="IN RFB 1888/2019",
            details=(
                "Operações com criptoativos que resultem em ganho de capital "
                "superior a R$ 35.000 no mês devem ser declaradas mensalmente "
                "à Receita Federal, além da declaração anual no IRPF."
            ),
        ),
        LegislationChange(
            name="Patrimônio Cripto > R$ 5.000",
            description="Obrigatoriedade de declarar criptoativos acima de R$ 5.000",
            effective_date=date(2019, 8, 1),
            category=LegislationCategory.CRYPTOCURRENCY,
            impact_level=ImpactLevel.MEDIUM,
            law_reference="IN RFB 1888/2019",
            details=(
                "Qualquer posição em criptoativos com valor superior a R$ 5.000 "
                "deve ser declarada na declaração anual de IRPF, "
                "identificando o tipo de ativo e exchange/custodiante."
            ),
        ),
        # === International Taxation ===
        LegislationChange(
            name="DCBE - Capitais Brasileiros no Exterior",
            description="Declaração obrigatória para ativos externos > USD 1 milhão",
            effective_date=date(2001, 3, 1),
            category=LegislationCategory.INTERNATIONAL,
            impact_level=ImpactLevel.HIGH,
            law_reference="Resolução BCB 3.854/2010, atualizada BCB 279/2022",
            details=(
                "Residentes no Brasil com ativos no exterior que totalizem "
                "USD 1.000.000 ou mais devem apresentar Declaração de Capitais "
                "Brasileiros no Exterior (DCBE) ao Banco Central anualmente."
            ),
        ),
        LegislationChange(
            name="Exit Tax - Imposto de Saída",
            description="Tributação sobre ganho não realizado ao deixar residência fiscal",
            effective_date=date(2023, 1, 1),
            category=LegislationCategory.INTERNATIONAL,
            impact_level=ImpactLevel.HIGH,
            law_reference="Lei 14.754/2023",
            details=(
                "Ao encerrar residência fiscal no Brasil, contribuintes devem "
                "declarar e pagar imposto sobre ganho de capital não realizado "
                "em ativos sujeitos a tributação (imóveis, ações, etc.)."
            ),
        ),
        # === Capital Gains Changes ===
        LegislationChange(
            name="Alíquotas Progressivas Ganho de Capital",
            description="Alíquotas de 15% a 22,5% conforme valor do ganho",
            effective_date=date(2016, 1, 1),
            category=LegislationCategory.CAPITAL_GAINS,
            impact_level=ImpactLevel.MEDIUM,
            law_reference="Lei 13.259/2016",
            details=(
                "Ganhos até R$ 5M: 15%. De R$ 5M a R$ 10M: 17,5%. "
                "De R$ 10M a R$ 30M: 20%. Acima de R$ 30M: 22,5%. "
                "Aplicável a imóveis, participações societárias e outros ativos."
            ),
        ),
        # === Deduction Limits Updates ===
        LegislationChange(
            name="Limite Desconto Simplificado 2025",
            description="Limite do desconto simplificado atualizado para R$ 16.754,34",
            effective_date=date(2025, 3, 1),
            category=LegislationCategory.DEDUCTION_LIMITS,
            impact_level=ImpactLevel.LOW,
            law_reference="IN RFB 2025",
            details=(
                "O desconto simplificado de 20% está limitado a R$ 16.754,34. "
                "Contribuintes com deduções maiores devem optar pelo modelo completo."
            ),
        ),
        LegislationChange(
            name="Limite Dedução Educação 2025",
            description="Limite de dedução por educação: R$ 3.561,50/pessoa/ano",
            effective_date=date(2025, 3, 1),
            category=LegislationCategory.DEDUCTION_LIMITS,
            impact_level=ImpactLevel.LOW,
            law_reference="IN RFB 2025",
            details=(
                "Despesas com educação são dedutíveis até R$ 3.561,50 por pessoa "
                "(titular, dependente ou alimentando). Não inclui cursos livres, "
                "idiomas fora de graduação, material escolar ou uniformes."
            ),
        ),
        LegislationChange(
            name="Dedução por Dependente 2025",
            description="Valor de dedução por dependente: R$ 2.275,08",
            effective_date=date(2025, 3, 1),
            category=LegislationCategory.DEDUCTION_LIMITS,
            impact_level=ImpactLevel.LOW,
            law_reference="IN RFB 2025",
            details=(
                "Cada dependente declarado gera dedução fixa de R$ 2.275,08 "
                "na base de cálculo do imposto. Aplica-se a filhos até 21 anos, "
                "universitários até 24 anos, cônjuge, e outros dependentes legais."
            ),
        ),
        # === Reporting Obligations ===
        LegislationChange(
            name="Obrigatoriedade Declaração 2026",
            description="Novos limites para obrigatoriedade de declaração",
            effective_date=date(2026, 3, 1),
            category=LegislationCategory.REPORTING_OBLIGATION,
            impact_level=ImpactLevel.MEDIUM,
            law_reference="IN RFB 2025",
            details=(
                "Obrigatório declarar se: rendimentos tributáveis > R$ 33.888, "
                "rendimentos isentos > R$ 200.000, patrimônio > R$ 800.000, "
                "ganho de capital em qualquer valor, ou receita rural > R$ 169.440."
            ),
        ),
    ]

    # Cryptocurrency asset groups
    CRYPTO_GROUPS = {GrupoBem.CRIPTOATIVOS, GrupoBem.OUTROS_BENS}

    def __init__(self, declaration: Declaration, reference_date: date | None = None) -> None:
        """Initialize analyzer with declaration data.

        Args:
            declaration: The IRPF declaration to analyze
            reference_date: Date to check legislation against (default: today)
        """
        self.declaration = declaration
        self.reference_date = reference_date or date.today()
        self.alerts: list[LegislationAlert] = []
        self.suggestions: list[Suggestion] = []
        self.warnings: list[Warning] = []

    def analyze(self) -> tuple[list[Suggestion], list[Warning]]:
        """Analyze declaration against legislation changes.

        Returns:
            Tuple of (suggestions, warnings) for the taxpayer.
        """
        # Check each legislation change for applicability
        for change in self.LEGISLATION_CHANGES:
            self._check_legislation_change(change)

        # Generate specific alerts based on declaration data
        self._check_2026_reform_impact()
        self._check_irpfm_impact()
        self._check_crypto_obligations()
        self._check_international_obligations()
        self._check_declaration_obligation()

        return self.suggestions, self.warnings

    def _check_legislation_change(self, change: LegislationChange) -> None:
        """Check if a legislation change applies to this taxpayer."""
        # Skip if change is not yet effective and not upcoming
        days_until_effective = (change.effective_date - self.reference_date).days
        if days_until_effective > 365:  # More than 1 year away
            return

        # Create alert based on category
        alert = self._evaluate_change_impact(change)
        if alert and alert.applies_to_taxpayer:
            self.alerts.append(alert)

    def _evaluate_change_impact(self, change: LegislationChange) -> LegislationAlert | None:
        """Evaluate if a change impacts this specific taxpayer."""
        total_income = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
        )

        # Tax reform changes
        if change.category == LegislationCategory.TAX_REFORM:
            if "Isenção" in change.name:
                # Check if taxpayer would benefit from new exemption
                annual_income = self.declaration.total_rendimentos_tributaveis
                if annual_income <= ISENCAO_ANUAL_2026:
                    return LegislationAlert(
                        change=change,
                        applies_to_taxpayer=True,
                        reason=f"Sua renda de R$ {annual_income:,.2f} ficará isenta",
                        potential_impact=self.declaration.imposto_devido,
                        action_required="Nenhuma ação necessária - benefício automático",
                    )
                elif annual_income <= REDUCAO_ANUAL_LIMITE_2026:
                    return LegislationAlert(
                        change=change,
                        applies_to_taxpayer=True,
                        reason="Você terá direito à redução progressiva",
                        potential_impact=None,
                        action_required="Aguarde atualização das tabelas em 2026",
                    )
            elif "IRPFM" in change.name:
                if total_income >= LIMITE_IRPFM:
                    return LegislationAlert(
                        change=change,
                        applies_to_taxpayer=True,
                        reason=f"Renda total de R$ {total_income:,.2f} excede R$ 600k",
                        potential_impact=None,
                        action_required="Revise planejamento tributário com contador",
                    )

        # Cryptocurrency regulations
        elif change.category == LegislationCategory.CRYPTOCURRENCY:
            crypto_assets = self._get_crypto_assets()
            if crypto_assets:
                total_crypto = sum(b.situacao_atual for b in crypto_assets)
                if total_crypto >= PATRIMONIO_CRIPTO_OBRIGATORIO:
                    return LegislationAlert(
                        change=change,
                        applies_to_taxpayer=True,
                        reason=f"Possui R$ {total_crypto:,.2f} em criptoativos",
                        action_required="Certifique-se de declarar todos os criptoativos",
                    )

        # International obligations
        elif change.category == LegislationCategory.INTERNATIONAL and "DCBE" in change.name:
            foreign_assets = self._get_foreign_assets()
            if foreign_assets:
                total_foreign = sum(b.situacao_atual for b in foreign_assets)
                # Approximate USD conversion (simplified)
                usd_estimate = total_foreign / Decimal("5")  # ~5 BRL/USD
                if usd_estimate >= LIMITE_DCBE_USD:
                    return LegislationAlert(
                        change=change,
                        applies_to_taxpayer=True,
                        reason=f"Ativos no exterior ~USD {usd_estimate:,.0f}",
                        action_required="Verifique obrigação de DCBE junto ao BACEN",
                    )

        return None

    def _check_2026_reform_impact(self) -> None:
        """Check impact of 2026 tax reform on taxpayer."""
        annual_income = self.declaration.total_rendimentos_tributaveis

        # Alert for those who will benefit from new exemption
        if annual_income > 0 and annual_income <= ISENCAO_ANUAL_2026:
            self.suggestions.append(
                Suggestion(
                    titulo="Reforma IR 2026: Você ficará isento",
                    descricao=(
                        f"A Lei 15.270/2025 isenta rendimentos até R$ {ISENCAO_MENSAL_2026:,.2f}/mês "
                        f"(R$ {ISENCAO_ANUAL_2026:,.2f}/ano). Sua renda de R$ {annual_income:,.2f} "
                        "ficará totalmente isenta a partir de janeiro/2026."
                    ),
                    economia_potencial=self.declaration.imposto_devido,
                    prioridade=1,
                )
            )
        elif annual_income <= REDUCAO_ANUAL_LIMITE_2026:
            # Calculate approximate reduction benefit
            reduction_benefit = self._estimate_reduction_benefit(annual_income)
            if reduction_benefit > Decimal("0"):
                self.suggestions.append(
                    Suggestion(
                        titulo="Reforma IR 2026: Redução Progressiva",
                        descricao=(
                            f"Com renda de R$ {annual_income:,.2f}, você terá direito "
                            "à redução progressiva do imposto em 2026. "
                            f"A redução pode chegar a R$ {reduction_benefit:,.2f}/ano."
                        ),
                        economia_potencial=reduction_benefit,
                        prioridade=2,
                    )
                )

    def _check_irpfm_impact(self) -> None:
        """Check if taxpayer is affected by IRPFM (minimum tax for high earners)."""
        total_income = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
            + self.declaration.total_rendimentos_exclusivos
        )

        if total_income >= LIMITE_IRPFM:
            # High income - IRPFM applies
            effective_rate = (
                self.declaration.imposto_devido / total_income
                if total_income > 0
                else Decimal("0")
            )

            if total_income >= LIMITE_IRPFM_MAXIMO:
                # Above R$ 1.2M - 10% minimum applies
                min_rate = Decimal("0.10")
                if effective_rate < min_rate:
                    additional_tax = (min_rate - effective_rate) * total_income
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"ATENÇÃO: Com renda total de R$ {total_income:,.2f}, "
                                f"a partir de 2026 você estará sujeito ao IRPFM (Imposto Mínimo). "
                                f"Alíquota efetiva atual: {effective_rate*100:.1f}%. "
                                f"Mínimo exigido: 10%. Imposto adicional estimado: R$ {additional_tax:,.2f}."
                            ),
                            risco=RiskLevel.HIGH,
                            categoria=WarningCategory.GERAL,
                            valor_impacto=additional_tax,
                        )
                    )
            else:
                # Between R$ 600k and R$ 1.2M - progressive minimum
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"ALERTA: Com renda total de R$ {total_income:,.2f}, "
                            "você pode estar sujeito ao IRPFM progressivo em 2026. "
                            "Consulte um contador para planejamento tributário."
                        ),
                        risco=RiskLevel.MEDIUM,
                        categoria=WarningCategory.GERAL,
                        informativo=True,
                    )
                )

    def _check_crypto_obligations(self) -> None:
        """Check cryptocurrency-related obligations."""
        crypto_assets = self._get_crypto_assets()
        if not crypto_assets:
            return

        total_crypto = sum(b.situacao_atual for b in crypto_assets)

        # Check if above declaration threshold
        if total_crypto >= PATRIMONIO_CRIPTO_OBRIGATORIO:
            # Count assets without proper exchange identification
            unidentified = sum(
                1 for b in crypto_assets
                if not b.cnpj_instituicao or b.cnpj_instituicao.strip() == ""
            )

            if unidentified > 0:
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"IN RFB 1888/2019: {unidentified} criptoativo(s) sem CNPJ de exchange. "
                            "Informe o CNPJ da exchange ou indique 'self-custody' na discriminação."
                        ),
                        risco=RiskLevel.MEDIUM,
                        categoria=WarningCategory.GERAL,
                        campo="bens_direitos",
                    )
                )

        # Check for potentially high monthly gains (estimated)
        crypto_gain_annual = sum(
            max(Decimal("0"), b.situacao_atual - b.situacao_anterior)
            for b in crypto_assets
        )
        estimated_monthly = crypto_gain_annual / 12

        if estimated_monthly > GANHO_CAPITAL_CRIPTO_MENSAL:
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"ALERTA: Ganho estimado em cripto de R$ {estimated_monthly:,.2f}/mês "
                        f"excede limite de R$ {GANHO_CAPITAL_CRIPTO_MENSAL:,.2f}. "
                        "Verifique obrigação de declaração mensal (IN RFB 1888/2019)."
                    ),
                    risco=RiskLevel.HIGH,
                    categoria=WarningCategory.GERAL,
                    valor_impacto=crypto_gain_annual,
                )
            )

    def _check_international_obligations(self) -> None:
        """Check international tax obligations."""
        foreign_assets = self._get_foreign_assets()
        if not foreign_assets:
            return

        total_foreign = sum(b.situacao_atual for b in foreign_assets)

        # Rough USD conversion
        usd_estimate = total_foreign / Decimal("5")

        if usd_estimate >= LIMITE_DCBE_USD:
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"DCBE OBRIGATÓRIO: Ativos no exterior de R$ {total_foreign:,.2f} "
                        f"(~USD {usd_estimate:,.0f}) excedem limite de USD 1 milhão. "
                        "Apresente a DCBE ao Banco Central até 5 de abril."
                    ),
                    risco=RiskLevel.HIGH,
                    categoria=WarningCategory.GERAL,
                    valor_impacto=total_foreign,
                )
            )
        elif usd_estimate >= Decimal("100000"):  # USD 100k - informational
            self.suggestions.append(
                Suggestion(
                    titulo="Ativos no Exterior - Acompanhe o limite DCBE",
                    descricao=(
                        f"Seus ativos no exterior (~USD {usd_estimate:,.0f}) estão "
                        f"abaixo do limite DCBE de USD 1 milhão. "
                        "Monitore o saldo e variação cambial."
                    ),
                    prioridade=3,
                )
            )

    def _check_declaration_obligation(self) -> None:
        """Check if declaration is obligatory and alert about new limits."""
        rendimentos = self.declaration.total_rendimentos_tributaveis
        isentos = self.declaration.total_rendimentos_isentos
        patrimonio = self.declaration.resumo_patrimonio.patrimonio_liquido_atual

        obligations_met = []

        if rendimentos >= OBRIGATORIEDADE_RENDIMENTOS_TRIBUTAVEIS:
            obligations_met.append(
                f"Rendimentos tributáveis (R$ {rendimentos:,.2f}) > R$ {OBRIGATORIEDADE_RENDIMENTOS_TRIBUTAVEIS:,.2f}"
            )

        if isentos >= OBRIGATORIEDADE_RENDIMENTOS_ISENTOS:
            obligations_met.append(
                f"Rendimentos isentos (R$ {isentos:,.2f}) > R$ {OBRIGATORIEDADE_RENDIMENTOS_ISENTOS:,.2f}"
            )

        if patrimonio >= OBRIGATORIEDADE_PATRIMONIO:
            obligations_met.append(
                f"Patrimônio (R$ {patrimonio:,.2f}) > R$ {OBRIGATORIEDADE_PATRIMONIO:,.2f}"
            )

        if obligations_met and len(obligations_met) >= 1:
            self.suggestions.append(
                Suggestion(
                    titulo="Obrigatoriedade de Declaração",
                    descricao=(
                        "Você é obrigado a declarar IRPF por: "
                        + "; ".join(obligations_met)
                        + ". Os limites foram atualizados para o exercício 2026."
                    ),
                    prioridade=5,
                )
            )

    def _get_crypto_assets(self) -> list:
        """Get cryptocurrency assets from declaration."""
        crypto_keywords = [
            "bitcoin", "btc", "ethereum", "eth", "cripto", "crypto",
            "binance", "mercado bitcoin", "foxbit", "novadax", "altcoin",
            "stable", "usdt", "usdc", "defi", "nft", "token",
        ]

        crypto_assets = []
        for bem in self.declaration.bens_direitos:
            # Check by group
            if bem.grupo in self.CRYPTO_GROUPS:
                crypto_assets.append(bem)
                continue

            # Check by description
            desc_lower = bem.discriminacao.lower()
            if any(kw in desc_lower for kw in crypto_keywords):
                crypto_assets.append(bem)

        return crypto_assets

    def _get_foreign_assets(self) -> list:
        """Get foreign assets from declaration."""
        brazil_country = "105"
        foreign_keywords = [
            "exterior", "foreign", "usa", "eua", "united states",
            "europe", "europa", "avenue", "interactive brokers",
            "charles schwab", "fidelity", "vanguard", "usd", "eur",
        ]

        foreign_assets = []
        for bem in self.declaration.bens_direitos:
            # Check by location
            if bem.localizacao and bem.localizacao.pais != brazil_country:
                foreign_assets.append(bem)
                continue

            # Check by description
            desc_lower = bem.discriminacao.lower()
            if any(kw in desc_lower for kw in foreign_keywords):
                foreign_assets.append(bem)

        return foreign_assets

    def _estimate_reduction_benefit(self, annual_income: Decimal) -> Decimal:
        """Estimate the benefit from the progressive reduction zone.

        For income between R$ 60k and R$ 88.2k/year, there's a progressive
        reduction that smoothly transitions from full exemption to normal rates.
        """
        if annual_income <= ISENCAO_ANUAL_2026:
            return self.declaration.imposto_devido

        if annual_income > REDUCAO_ANUAL_LIMITE_2026:
            return Decimal("0")

        # Linear interpolation of reduction benefit
        range_size = REDUCAO_ANUAL_LIMITE_2026 - ISENCAO_ANUAL_2026
        position_in_range = annual_income - ISENCAO_ANUAL_2026
        reduction_factor = 1 - (position_in_range / range_size)

        # Maximum annual reduction is ~R$ 3,754.68 (R$ 312.89 * 12)
        max_annual_reduction = Decimal("312.89") * 12
        return max_annual_reduction * reduction_factor

    def get_all_alerts(self) -> list[LegislationAlert]:
        """Get all legislation alerts for this taxpayer."""
        return self.alerts

    def get_summary(self) -> dict:
        """Get summary of legislation analysis."""
        return {
            "total_alerts": len(self.alerts),
            "high_impact": sum(
                1 for a in self.alerts if a.change.impact_level == ImpactLevel.HIGH
            ),
            "upcoming_changes": sum(
                1 for a in self.alerts
                if a.change.effective_date > self.reference_date
            ),
            "action_required": sum(
                1 for a in self.alerts if a.action_required is not None
            ),
        }


def analyze_legislation(
    declaration: Declaration,
    reference_date: date | None = None,
) -> tuple[list[Suggestion], list[Warning]]:
    """Analyze a declaration for legislation change impacts.

    This is a convenience function that creates an analyzer and runs analysis.

    Args:
        declaration: The IRPF declaration to analyze
        reference_date: Date to check legislation against (default: today)

    Returns:
        Tuple of (suggestions, warnings) for the taxpayer.
    """
    analyzer = LegislationAlertsAnalyzer(declaration, reference_date)
    return analyzer.analyze()
