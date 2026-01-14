"""Optimization analyzer for tax savings suggestions."""

from decimal import Decimal
from typing import Optional

from irpf_analyzer.core.models.analysis import Suggestion
from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import TipoDeclaracao, TipoDeducao, TipoRendimento
from irpf_analyzer.core.rules.tax_constants import (
    ALIQUOTA_MAXIMA,
    ECONOMIA_MINIMA_SUGESTAO,
    ESPACO_MINIMO_PGBL,
    LIMITE_DOACOES_PERCENTUAL,
    LIMITE_EDUCACAO_PESSOA,
    LIMITE_PGBL_PERCENTUAL,
    LIMITE_SIMPLIFICADA,
    RENDA_MAXIMA_VALIDA,
    RENDA_MINIMA_PGBL,
    RENDA_MINIMA_VALIDA,
    obter_aliquota_marginal,
)


class OptimizationAnalyzer:
    """Analyzes declaration for tax optimization opportunities.

    Checks for:
    - Simplified vs complete declaration optimization
    - PGBL contribution opportunities
    - Education expense limits
    - Incentive donation opportunities
    - Self-employed book-keeping deductions
    """

    def __init__(self, declaration: Declaration):
        self.declaration = declaration
        self.suggestions: list[Suggestion] = []

        # Cache common values
        self._renda_tributavel = declaration.total_rendimentos_tributaveis
        self._resumo_deducoes = declaration.resumo_deducoes
        self._total_deducoes = sum(d.valor for d in declaration.deducoes)

    def analyze(self) -> list[Suggestion]:
        """Run all optimization checks and return suggestions sorted by priority."""
        # Skip if income looks invalid (parsing issues)
        if not self._is_income_valid():
            return []

        self._check_declaration_type()
        self._check_pgbl_opportunity()
        self._check_education_limit()
        self._check_incentive_donations()
        self._check_livro_caixa()

        return sorted(self.suggestions, key=lambda s: s.prioridade)

    def _is_income_valid(self) -> bool:
        """Check if income data looks valid (sanity check)."""
        return RENDA_MINIMA_VALIDA < self._renda_tributavel < RENDA_MAXIMA_VALIDA

    def _check_declaration_type(self) -> None:
        """Compare simplified vs complete declaration to find best option.

        Simplified declaration uses 20% discount capped at R$ 16.754,34.
        Complete declaration uses itemized deductions.

        Suggests switching if simplified is more advantageous.
        """
        # Calculate simplified discount
        desconto_simplificado = min(
            self._renda_tributavel * Decimal("0.20"),
            LIMITE_SIMPLIFICADA,
        )

        # Compare with actual deductions
        if self.declaration.tipo_declaracao == TipoDeclaracao.COMPLETA:
            if desconto_simplificado > self._total_deducoes:
                economia = desconto_simplificado - self._total_deducoes

                if economia >= ECONOMIA_MINIMA_SUGESTAO:
                    # Calculate actual tax savings
                    aliquota = obter_aliquota_marginal(self._renda_tributavel)
                    economia_imposto = economia * aliquota

                    self.suggestions.append(
                        Suggestion(
                            titulo="Considere declaração simplificada",
                            descricao=(
                                f"Desconto simplificado (R$ {desconto_simplificado:,.2f}) "
                                f"é maior que suas deduções (R$ {self._total_deducoes:,.2f}). "
                                f"A economia estimada de IR seria R$ {economia_imposto:,.2f}."
                            ),
                            economia_potencial=economia_imposto,
                            prioridade=1,
                        )
                    )

        elif self.declaration.tipo_declaracao == TipoDeclaracao.SIMPLIFICADA:
            # Check if complete would be better
            if self._total_deducoes > desconto_simplificado:
                economia = self._total_deducoes - desconto_simplificado
                aliquota = obter_aliquota_marginal(self._renda_tributavel)
                economia_imposto = economia * aliquota

                if economia_imposto >= ECONOMIA_MINIMA_SUGESTAO:
                    self.suggestions.append(
                        Suggestion(
                            titulo="Considere declaração completa",
                            descricao=(
                                f"Suas deduções (R$ {self._total_deducoes:,.2f}) "
                                f"são maiores que o desconto simplificado (R$ {desconto_simplificado:,.2f}). "
                                f"A economia estimada de IR seria R$ {economia_imposto:,.2f}."
                            ),
                            economia_potencial=economia_imposto,
                            prioridade=1,
                        )
                    )

    def _check_pgbl_opportunity(self) -> None:
        """Check for PGBL contribution opportunities.

        PGBL allows deducting up to 12% of gross taxable income for those who:
        - Use complete declaration
        - Contribute to official pension (INSS/RPPS)
        """
        # Skip if income too low (simplified is likely better anyway)
        if self._renda_tributavel < RENDA_MINIMA_PGBL:
            return

        # Calculate PGBL limit
        limite_pgbl = self._renda_tributavel * LIMITE_PGBL_PERCENTUAL
        pgbl_usado = self._resumo_deducoes.previdencia_privada

        # Check if there's room for more PGBL
        espaco_disponivel = limite_pgbl - pgbl_usado

        if espaco_disponivel >= ESPACO_MINIMO_PGBL:
            # Estimate savings at marginal rate
            aliquota = obter_aliquota_marginal(self._renda_tributavel)
            economia_estimada = espaco_disponivel * aliquota

            if economia_estimada >= ECONOMIA_MINIMA_SUGESTAO:
                self.suggestions.append(
                    Suggestion(
                        titulo="Oportunidade: Contribuição PGBL",
                        descricao=(
                            f"Você pode deduzir até R$ {limite_pgbl:,.2f} em PGBL "
                            f"(12% da renda bruta tributável). "
                            f"Espaço disponível: R$ {espaco_disponivel:,.2f}. "
                            f"Aporte até 31/12 do ano-calendário para aproveitar."
                        ),
                        economia_potencial=economia_estimada,
                        prioridade=1,
                    )
                )

    def _check_education_limit(self) -> None:
        """Check if education deductions are at the limit.

        Education limit is R$ 3.561,50 per person per year.
        Includes: taxpayer and each dependent.
        """
        educacao_total = self._resumo_deducoes.despesas_educacao
        num_pessoas = 1 + len(self.declaration.dependentes)

        # Calculate theoretical maximum
        limite_maximo = LIMITE_EDUCACAO_PESSOA * num_pessoas

        # Only suggest if using less than 50% of potential
        if educacao_total > 0 and educacao_total < limite_maximo * Decimal("0.5"):
            espaco = limite_maximo - educacao_total

            # This is informational - we can't know if they have more expenses
            self.suggestions.append(
                Suggestion(
                    titulo="Verifique despesas com educação",
                    descricao=(
                        f"Limite de educação: R$ {LIMITE_EDUCACAO_PESSOA:,.2f}/pessoa "
                        f"({num_pessoas} pessoas = R$ {limite_maximo:,.2f}). "
                        f"Declarado: R$ {educacao_total:,.2f}. "
                        f"Certifique-se de incluir todas as despesas elegíveis "
                        f"(escolas, faculdades, cursos técnicos)."
                    ),
                    economia_potencial=None,  # Can't estimate without knowing actual expenses
                    prioridade=3,
                )
            )

    def _check_incentive_donations(self) -> None:
        """Check for incentive donation opportunities.

        Donations to specific funds (Child, Elderly, Culture, Sports) can be
        deducted directly from tax owed, up to 6% of the tax.

        This is only relevant for those who owe tax.
        """
        imposto_devido = self.declaration.imposto_devido

        # Skip if no tax owed (nothing to deduct from)
        if imposto_devido <= 0:
            return

        limite_doacoes = imposto_devido * LIMITE_DOACOES_PERCENTUAL

        # Get current incentive donations
        doacoes_atuais = self._get_incentive_donations()

        if doacoes_atuais < limite_doacoes:
            espaco = limite_doacoes - doacoes_atuais

            if espaco >= ECONOMIA_MINIMA_SUGESTAO:
                self.suggestions.append(
                    Suggestion(
                        titulo="Oportunidade: Doações Incentivadas",
                        descricao=(
                            f"Você pode direcionar até R$ {limite_doacoes:,.2f} "
                            f"(6% do IR devido) para fundos incentivados "
                            f"(Criança, Idoso, Cultura, Audiovisual, Desporto). "
                            f"Espaço disponível: R$ {espaco:,.2f}. "
                            f"O valor é abatido diretamente do imposto devido."
                        ),
                        economia_potencial=espaco,  # 100% returns as tax reduction
                        prioridade=2,
                    )
                )

    def _check_livro_caixa(self) -> None:
        """Check if self-employed professionals are using livro-caixa.

        Self-employed (trabalho não-assalariado) can deduct professional
        expenses through livro-caixa, reducing taxable income.
        """
        renda_autonoma = self._get_self_employment_income()

        # Skip if no self-employment income
        if renda_autonoma <= 0:
            return

        livro_caixa = self._resumo_deducoes.livro_caixa

        # If self-employed but no livro-caixa deductions
        if livro_caixa == 0:
            self.suggestions.append(
                Suggestion(
                    titulo="Verifique deduções de livro-caixa",
                    descricao=(
                        f"Você tem renda de trabalho autônomo (R$ {renda_autonoma:,.2f}) "
                        f"mas não declarou deduções de livro-caixa. "
                        f"Despesas como aluguel de consultório, materiais, "
                        f"equipamentos e deslocamentos profissionais são dedutíveis."
                    ),
                    economia_potencial=None,  # Can't estimate
                    prioridade=3,
                )
            )

    def _get_incentive_donations(self) -> Decimal:
        """Get total of incentive donations (ECA, Idoso, Cultura, etc.)."""
        # These are usually in a specific section of the declaration
        # For now, we'll check deductions marked as donations
        total = Decimal("0")

        for deducao in self.declaration.deducoes:
            # Check if it's a donation type
            descricao = getattr(deducao, 'descricao', None) or ""
            descricao_upper = descricao.upper()
            if any(kw in descricao_upper for kw in [
                "ECA", "CRIANÇA", "ADOLESCENTE",
                "IDOSO", "CULTURA", "AUDIOVISUAL",
                "DESPORTO", "PRONON", "PRONAS",
            ]):
                total += deducao.valor

        return total

    def _get_self_employment_income(self) -> Decimal:
        """Get total self-employment income."""
        total = Decimal("0")

        for rendimento in self.declaration.rendimentos:
            if rendimento.tipo == TipoRendimento.TRABALHO_NAO_ASSALARIADO:
                total += rendimento.valor_anual

        return total


def analyze_optimization(declaration: Declaration) -> list[Suggestion]:
    """Convenience function to run optimization analysis.

    Args:
        declaration: The IRPF declaration to analyze

    Returns:
        List of optimization suggestions sorted by priority
    """
    analyzer = OptimizationAnalyzer(declaration)
    return analyzer.analyze()
