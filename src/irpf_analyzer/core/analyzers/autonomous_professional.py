"""Autonomous Professional analyzer for IRPF declarations.

This module provides specialized analysis for self-employed professionals:
- Livro-caixa optimization
- Deductible expenses suggestions
- Tax regime comparison (Autônomo/PF vs Simples Nacional vs Lucro Presumido)

Based on Brazilian tax law for autonomous professionals.
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
from irpf_analyzer.core.models.enums import TipoDeducao, TipoRendimento
from irpf_analyzer.core.rules.tax_constants import (
    INSS_FAIXA_4,
    LIVRO_CAIXA_MAXIMO_RATIO,
    calcular_imposto_anual,
    obter_aliquota_marginal,
)


class TaxRegime(str, Enum):
    """Tax regime options for professionals."""

    AUTONOMO_PF = "autonomo_pf"  # Individual as autonomous
    SIMPLES_NACIONAL = "simples_nacional"  # Simples Nacional (MEI or ME)
    LUCRO_PRESUMIDO = "lucro_presumido"  # Presumed profit


class DeductibleExpenseCategory(NamedTuple):
    """Category of deductible expense for livro-caixa."""

    name: str
    description: str
    typical_ratio: Decimal  # Typical percentage of gross income
    examples: list[str]


class TaxRegimeComparison(NamedTuple):
    """Comparison result between tax regimes."""

    regime: TaxRegime
    gross_income: Decimal
    estimated_tax: Decimal
    effective_rate: Decimal
    notes: str


class AutonomousProfessionalAnalyzer:
    """Analyzer for self-employed professionals.

    Provides:
    - Livro-caixa optimization suggestions
    - Missing deductible expenses detection
    - Tax regime comparison
    """

    # Categories of deductible expenses for livro-caixa
    DEDUCTIBLE_CATEGORIES: list[DeductibleExpenseCategory] = [
        DeductibleExpenseCategory(
            name="Aluguel de consultório/escritório",
            description="Aluguel de espaço profissional",
            typical_ratio=Decimal("0.10"),
            examples=["Aluguel", "Condomínio profissional", "IPTU rateado"],
        ),
        DeductibleExpenseCategory(
            name="Material de trabalho",
            description="Materiais e insumos profissionais",
            typical_ratio=Decimal("0.05"),
            examples=["Material de escritório", "Impressão", "Software profissional"],
        ),
        DeductibleExpenseCategory(
            name="Comunicação",
            description="Telefone e internet profissional",
            typical_ratio=Decimal("0.03"),
            examples=["Telefone comercial", "Internet", "Hospedagem site"],
        ),
        DeductibleExpenseCategory(
            name="Deslocamento profissional",
            description="Transporte para atendimento de clientes",
            typical_ratio=Decimal("0.05"),
            examples=["Combustível", "Estacionamento", "Uber/Táxi profissional"],
        ),
        DeductibleExpenseCategory(
            name="Serviços de terceiros",
            description="Profissionais contratados para auxiliar",
            typical_ratio=Decimal("0.08"),
            examples=["Secretária", "Contador", "Auxiliar", "Advogado"],
        ),
        DeductibleExpenseCategory(
            name="Atualização profissional",
            description="Cursos e capacitação da área",
            typical_ratio=Decimal("0.03"),
            examples=["Cursos", "Congressos", "Livros técnicos", "Assinaturas"],
        ),
        DeductibleExpenseCategory(
            name="Equipamentos e manutenção",
            description="Equipamentos e sua manutenção",
            typical_ratio=Decimal("0.04"),
            examples=["Computador", "Impressora", "Manutenção equipamentos"],
        ),
        DeductibleExpenseCategory(
            name="Despesas bancárias",
            description="Taxas e tarifas bancárias da atividade",
            typical_ratio=Decimal("0.01"),
            examples=["Tarifas bancárias", "Taxa de maquininha", "IOF"],
        ),
    ]

    # Simples Nacional tax rates by revenue bracket (Anexo III - Serviços)
    # (limite_superior, aliquota_nominal, deducao)
    SIMPLES_ANEXO_III: list[tuple[Decimal, Decimal, Decimal]] = [
        (Decimal("180000"), Decimal("0.06"), Decimal("0")),
        (Decimal("360000"), Decimal("0.112"), Decimal("9360")),
        (Decimal("720000"), Decimal("0.135"), Decimal("17640")),
        (Decimal("1800000"), Decimal("0.16"), Decimal("35640")),
        (Decimal("3600000"), Decimal("0.21"), Decimal("125640")),
        (Decimal("4800000"), Decimal("0.33"), Decimal("648000")),
    ]

    # Lucro Presumido rates for services
    LUCRO_PRESUMIDO_BASE_SERVICOS = Decimal("0.32")  # 32% of revenue is presumed profit
    IRPJ_RATE = Decimal("0.15")  # 15% IRPJ
    IRPJ_ADICIONAL_THRESHOLD = Decimal("240000")  # 20k/month
    IRPJ_ADICIONAL_RATE = Decimal("0.10")  # 10% additional
    CSLL_RATE = Decimal("0.09")  # 9% CSLL
    PIS_RATE = Decimal("0.0065")  # 0.65% PIS
    COFINS_RATE = Decimal("0.03")  # 3% COFINS
    ISS_RATE = Decimal("0.05")  # 5% ISS (varies by municipality, using max)

    # Minimum income to suggest formalization
    INCOME_THRESHOLD_FORMALIZATION = Decimal("60000")

    # MEI limit (annual)
    MEI_LIMIT = Decimal("81000")

    # INSS autonomous rate
    INSS_AUTONOMO_RATE = Decimal("0.20")  # 20% of contribution base

    def __init__(self, declaration: Declaration) -> None:
        """Initialize analyzer with declaration data.

        Args:
            declaration: The IRPF declaration to analyze
        """
        self.declaration = declaration
        self.suggestions: list[Suggestion] = []
        self.warnings: list[Warning] = []

        # Calculate autonomous income
        self._renda_autonoma = self._calculate_autonomous_income()
        self._livro_caixa = declaration.resumo_deducoes.livro_caixa
        self._renda_tributavel = declaration.total_rendimentos_tributaveis

    def analyze(self) -> tuple[list[Suggestion], list[Warning]]:
        """Run all autonomous professional analysis.

        Returns:
            Tuple of (suggestions, warnings) found during analysis
        """
        if self._renda_autonoma <= 0:
            return self.suggestions, self.warnings

        self._analyze_livro_caixa_optimization()
        self._suggest_missing_deductible_expenses()
        self._compare_tax_regimes()

        return self.suggestions, self.warnings

    def _calculate_autonomous_income(self) -> Decimal:
        """Calculate total autonomous/self-employment income."""
        total = Decimal("0")
        for rendimento in self.declaration.rendimentos:
            if rendimento.tipo == TipoRendimento.TRABALHO_NAO_ASSALARIADO:
                total += rendimento.valor_anual
        return total

    def _analyze_livro_caixa_optimization(self) -> None:
        """Analyze livro-caixa optimization opportunities.

        Checks if the current livro-caixa deductions are being well utilized.
        """
        if self._renda_autonoma <= 0:
            return

        # Calculate current ratio
        current_ratio = (
            self._livro_caixa / self._renda_autonoma
            if self._renda_autonoma > 0
            else Decimal("0")
        )

        # Typical expected deductions for professionals (25-40% of income)
        expected_min_ratio = Decimal("0.20")
        expected_max_ratio = LIVRO_CAIXA_MAXIMO_RATIO

        # No livro-caixa at all
        if self._livro_caixa == 0:
            # Calculate potential savings
            typical_deductions = self._renda_autonoma * Decimal("0.30")
            aliquota = obter_aliquota_marginal(self._renda_tributavel)
            economia_potencial = typical_deductions * aliquota

            self.suggestions.append(
                Suggestion(
                    titulo="Utilize o livro-caixa",
                    descricao=(
                        f"Você tem renda autônoma de R$ {self._renda_autonoma:,.2f} "
                        f"mas não declarou despesas de livro-caixa. "
                        f"Profissionais autônomos podem deduzir despesas como "
                        f"aluguel de consultório, materiais, comunicação e deslocamentos. "
                        f"Economia estimada: R$ {economia_potencial:,.2f} "
                        f"(considerando 30% de despesas dedutíveis)."
                    ),
                    economia_potencial=economia_potencial,
                    prioridade=1,
                )
            )
            return

        # Very low livro-caixa utilization
        if current_ratio < expected_min_ratio:
            gap = expected_min_ratio - current_ratio
            additional_deductions = self._renda_autonoma * gap
            aliquota = obter_aliquota_marginal(self._renda_tributavel)
            economia_potencial = additional_deductions * aliquota

            self.suggestions.append(
                Suggestion(
                    titulo="Revise suas despesas de livro-caixa",
                    descricao=(
                        f"Suas despesas de livro-caixa representam apenas "
                        f"{current_ratio*100:.1f}% da renda autônoma. "
                        f"Profissionais tipicamente têm entre 20-40% de despesas dedutíveis. "
                        f"Verifique se todas as despesas estão sendo declaradas. "
                        f"Potencial adicional: R$ {additional_deductions:,.2f}."
                    ),
                    economia_potencial=economia_potencial,
                    prioridade=2,
                )
            )

        # Very high livro-caixa (potential audit risk)
        if current_ratio > expected_max_ratio:
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Livro-caixa representa {current_ratio*100:.1f}% da renda autônoma. "
                        f"Valores acima de 80% podem chamar atenção da Receita Federal. "
                        f"Certifique-se de ter documentação completa de todas as despesas."
                    ),
                    risco=RiskLevel.MEDIUM,
                    campo="deducoes",
                    categoria=WarningCategory.CONSISTENCIA,
                )
            )

    def _suggest_missing_deductible_expenses(self) -> None:
        """Suggest potentially missing deductible expense categories."""
        if self._renda_autonoma <= 0:
            return

        # Get current deduction descriptions
        deduction_keywords = set()
        for deducao in self.declaration.deducoes:
            if deducao.tipo == TipoDeducao.LIVRO_CAIXA:
                desc = (deducao.descricao or "").upper()
                deduction_keywords.update(desc.split())

        # Find potentially missing categories
        missing_categories: list[DeductibleExpenseCategory] = []
        potential_savings = Decimal("0")

        for category in self.DEDUCTIBLE_CATEGORIES:
            # Check if any example keyword is present
            category_found = False
            for example in category.examples:
                for word in example.upper().split():
                    if word in deduction_keywords:
                        category_found = True
                        break
                if category_found:
                    break

            if not category_found:
                missing_categories.append(category)
                potential_savings += self._renda_autonoma * category.typical_ratio

        if missing_categories and len(missing_categories) >= 2:
            # Only suggest if multiple categories are missing
            aliquota = obter_aliquota_marginal(self._renda_tributavel)
            economia_estimada = potential_savings * aliquota

            # Build category list
            categorias_str = ", ".join(c.name for c in missing_categories[:5])

            self.suggestions.append(
                Suggestion(
                    titulo="Despesas dedutíveis não identificadas",
                    descricao=(
                        f"Categorias de despesas potencialmente não declaradas: "
                        f"{categorias_str}. "
                        f"Profissionais autônomos podem deduzir diversas despesas "
                        f"relacionadas à atividade profissional. "
                        f"Economia potencial estimada: R$ {economia_estimada:,.2f}."
                    ),
                    economia_potencial=economia_estimada,
                    prioridade=2,
                )
            )

    def _compare_tax_regimes(self) -> None:
        """Compare tax burden across different tax regimes.

        Compares:
        - Autônomo/PF (current situation)
        - Simples Nacional (if eligible)
        - Lucro Presumido
        """
        if self._renda_autonoma < self.INCOME_THRESHOLD_FORMALIZATION:
            return  # Not worth formalizing for low income

        # Calculate tax for each regime
        regimes = self._calculate_all_regimes()

        # Find best regime
        current = next(r for r in regimes if r.regime == TaxRegime.AUTONOMO_PF)
        best = min(regimes, key=lambda r: r.estimated_tax)

        if best.regime != TaxRegime.AUTONOMO_PF:
            economia = current.estimated_tax - best.estimated_tax

            if economia > Decimal("1000"):  # Minimum savings to suggest
                regime_name = {
                    TaxRegime.SIMPLES_NACIONAL: "Simples Nacional",
                    TaxRegime.LUCRO_PRESUMIDO: "Lucro Presumido",
                    TaxRegime.AUTONOMO_PF: "Autônomo (PF)",
                }[best.regime]

                self.suggestions.append(
                    Suggestion(
                        titulo=f"Considere o regime {regime_name}",
                        descricao=(
                            f"Com receita bruta de R$ {self._renda_autonoma:,.2f}, "
                            f"o regime {regime_name} pode ser mais vantajoso. "
                            f"Carga atual (PF): {current.effective_rate*100:.1f}% = "
                            f"R$ {current.estimated_tax:,.2f}. "
                            f"{regime_name}: {best.effective_rate*100:.1f}% = "
                            f"R$ {best.estimated_tax:,.2f}. "
                            f"Economia potencial: R$ {economia:,.2f}/ano. "
                            f"{best.notes}"
                        ),
                        economia_potencial=economia,
                        prioridade=1,
                    )
                )

        # Add detailed comparison
        self._add_regime_comparison_details(regimes)

    def _calculate_all_regimes(self) -> list[TaxRegimeComparison]:
        """Calculate tax for all applicable regimes."""
        regimes = []

        # 1. Autônomo PF (current)
        regimes.append(self._calculate_autonomo_pf())

        # 2. Simples Nacional (if eligible)
        if self._renda_autonoma <= Decimal("4800000"):
            regimes.append(self._calculate_simples_nacional())

        # 3. Lucro Presumido
        regimes.append(self._calculate_lucro_presumido())

        return regimes

    def _calculate_autonomo_pf(self) -> TaxRegimeComparison:
        """Calculate tax as autonomous individual (PF).

        Includes:
        - IRPF (progressive table)
        - INSS (20% up to ceiling)
        """
        # INSS contribution (20% of income up to ceiling)
        base_inss = min(self._renda_autonoma, INSS_FAIXA_4 * 12)
        inss = base_inss * self.INSS_AUTONOMO_RATE

        # Taxable income after livro-caixa
        base_ir = self._renda_autonoma - self._livro_caixa

        # IRPF
        irpf = calcular_imposto_anual(base_ir)

        total_tax = inss + irpf
        effective_rate = total_tax / self._renda_autonoma if self._renda_autonoma > 0 else Decimal("0")

        return TaxRegimeComparison(
            regime=TaxRegime.AUTONOMO_PF,
            gross_income=self._renda_autonoma,
            estimated_tax=total_tax,
            effective_rate=effective_rate,
            notes="Inclui INSS (20%) + IRPF progressivo. Permite livro-caixa.",
        )

    def _calculate_simples_nacional(self) -> TaxRegimeComparison:
        """Calculate tax under Simples Nacional regime.

        Uses Anexo III (services) rates.
        """
        # Find applicable bracket
        tax = Decimal("0")
        for limite, aliquota, deducao in self.SIMPLES_ANEXO_III:
            if self._renda_autonoma <= limite:
                # Effective rate calculation
                tax = (self._renda_autonoma * aliquota - deducao)
                break
        else:
            # Above all brackets
            tax = self._renda_autonoma * Decimal("0.33") - Decimal("648000")

        # Ensure minimum
        tax = max(tax, Decimal("0"))

        effective_rate = tax / self._renda_autonoma if self._renda_autonoma > 0 else Decimal("0")

        notes = "Alíquotas progressivas. Inclui IRPJ, CSLL, PIS, COFINS, ISS e CPP."
        if self._renda_autonoma <= self.MEI_LIMIT:
            notes = "Pode ser MEI (R$71,60/mês fixo). " + notes

        return TaxRegimeComparison(
            regime=TaxRegime.SIMPLES_NACIONAL,
            gross_income=self._renda_autonoma,
            estimated_tax=tax,
            effective_rate=effective_rate,
            notes=notes,
        )

    def _calculate_lucro_presumido(self) -> TaxRegimeComparison:
        """Calculate tax under Lucro Presumido regime.

        For services:
        - Base: 32% of revenue
        - IRPJ: 15% + 10% adicional above 240k/year
        - CSLL: 9%
        - PIS: 0.65%
        - COFINS: 3%
        - ISS: ~5%
        """
        # Presumed profit base
        base_presumida = self._renda_autonoma * self.LUCRO_PRESUMIDO_BASE_SERVICOS

        # IRPJ
        irpj = base_presumida * self.IRPJ_RATE
        if base_presumida > self.IRPJ_ADICIONAL_THRESHOLD:
            irpj += (base_presumida - self.IRPJ_ADICIONAL_THRESHOLD) * self.IRPJ_ADICIONAL_RATE

        # CSLL
        csll = base_presumida * self.CSLL_RATE

        # PIS and COFINS (on gross revenue)
        pis = self._renda_autonoma * self.PIS_RATE
        cofins = self._renda_autonoma * self.COFINS_RATE

        # ISS (on gross revenue)
        iss = self._renda_autonoma * self.ISS_RATE

        total_tax = irpj + csll + pis + cofins + iss
        effective_rate = total_tax / self._renda_autonoma if self._renda_autonoma > 0 else Decimal("0")

        return TaxRegimeComparison(
            regime=TaxRegime.LUCRO_PRESUMIDO,
            gross_income=self._renda_autonoma,
            estimated_tax=total_tax,
            effective_rate=effective_rate,
            notes="Base 32% + impostos. Não há limite de receita.",
        )

    def _add_regime_comparison_details(
        self, regimes: list[TaxRegimeComparison]
    ) -> None:
        """Add detailed regime comparison as informational suggestion."""
        # Build comparison table
        lines = []
        for regime in sorted(regimes, key=lambda r: r.estimated_tax):
            regime_name = {
                TaxRegime.SIMPLES_NACIONAL: "Simples Nacional",
                TaxRegime.LUCRO_PRESUMIDO: "Lucro Presumido",
                TaxRegime.AUTONOMO_PF: "Autônomo (PF)",
            }[regime.regime]

            lines.append(
                f"• {regime_name}: R$ {regime.estimated_tax:,.2f} "
                f"({regime.effective_rate*100:.1f}%)"
            )

        self.suggestions.append(
            Suggestion(
                titulo="Comparativo de regimes tributários",
                descricao=(
                    f"Receita bruta anual: R$ {self._renda_autonoma:,.2f}\n\n"
                    "Carga tributária estimada por regime:\n"
                    + "\n".join(lines)
                    + "\n\nNota: Valores estimados. Consulte um contador "
                    "para análise detalhada considerando sua situação específica."
                ),
                economia_potencial=None,
                prioridade=5,  # Informational
            )
        )


def analyze_autonomous_professional(
    declaration: Declaration,
) -> tuple[list[Suggestion], list[Warning]]:
    """Convenience function to run autonomous professional analysis.

    Args:
        declaration: The IRPF declaration to analyze

    Returns:
        Tuple of (suggestions, warnings) found
    """
    analyzer = AutonomousProfessionalAnalyzer(declaration)
    return analyzer.analyze()
