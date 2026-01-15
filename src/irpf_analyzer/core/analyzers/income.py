"""Income analyzer for IRPF declarations.

This module provides comprehensive income analysis including:
- IRRF (withheld tax) vs income ratio validation
- Income concentration detection
- Previdência (social security) vs income consistency
- Alimony proportionality validation
- Income source pattern detection
"""

from collections import Counter
from decimal import Decimal
from typing import Optional

from irpf_analyzer.core.models.analysis import (
    Inconsistency,
    InconsistencyType,
    RiskLevel,
    Warning,
    WarningCategory,
)
from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import TipoDeducao, TipoRendimento
from irpf_analyzer.shared.validators import validar_cnpj
from irpf_analyzer.shared.statistics import (
    calcular_indice_gini,
    calcular_coeficiente_variacao,
)
from irpf_analyzer.core.rules.tax_constants import (
    FAIXAS_IR_ANUAL,
    obter_aliquota_marginal,
)


class IncomeAnalyzer:
    """Analyzes income patterns for inconsistencies and suspicious patterns.

    Detects:
    - IRRF ratio inconsistencies (withheld tax vs declared income)
    - Income concentration (single source dominates)
    - Previdência vs CLT income mismatches
    - Alimony proportionality issues
    - Livro-caixa vs autonomous income validation
    - Income source duplications
    """

    # Expected IRRF ranges by income bracket (conservative estimates)
    # Format: (min_income, max_income, min_irrf_ratio, max_irrf_ratio)
    IRRF_BRACKETS = [
        (Decimal("0"), Decimal("27110.52"), Decimal("0"), Decimal("0")),  # Exempt
        (Decimal("27110.52"), Decimal("33919.80"), Decimal("0"), Decimal("0.05")),  # 7.5%
        (Decimal("33919.80"), Decimal("45012.60"), Decimal("0.02"), Decimal("0.10")),  # 15%
        (Decimal("45012.60"), Decimal("55976.16"), Decimal("0.05"), Decimal("0.15")),  # 22.5%
        (Decimal("55976.16"), Decimal("999999999"), Decimal("0.08"), Decimal("0.20")),  # 27.5%
    ]

    # Previdência oficial rates (INSS)
    # 2024: 7.5% to 14% depending on salary bracket
    PREVIDENCIA_MIN_RATIO = Decimal("0.07")  # Minimum expected
    PREVIDENCIA_MAX_RATIO = Decimal("0.14")  # Maximum expected
    TETO_INSS_MENSAL = Decimal("7786.02")  # 2024 ceiling
    TETO_INSS_ANUAL = TETO_INSS_MENSAL * 12

    # Alimony proportionality limits
    PENSAO_MIN_RATIO = Decimal("0.10")  # Minimum expected (10% of income)
    PENSAO_MAX_RATIO = Decimal("0.40")  # Maximum expected (40% of income)

    # Income concentration threshold (Gini coefficient)
    GINI_CONCENTRACAO_LIMITE = Decimal("0.85")  # Above this = highly concentrated

    def __init__(self, declaration: Declaration):
        self.declaration = declaration
        self.inconsistencies: list[Inconsistency] = []
        self.warnings: list[Warning] = []

    def analyze(self) -> tuple[list[Inconsistency], list[Warning]]:
        """Run all income checks.

        Returns:
            Tuple of (inconsistencies, warnings) found
        """
        self._check_irrf_ratio()
        self._check_income_concentration()
        self._check_previdencia_vs_clt()
        self._check_pensao_proporcionalidade()
        self._check_livro_caixa_vs_autonomo()
        self._check_income_source_duplicates()
        self._check_decimo_terceiro_consistency()
        self._check_rendimentos_isentos_ratio()

        return self.inconsistencies, self.warnings

    def _check_irrf_ratio(self) -> None:
        """Validate IRRF (withheld tax) ratio vs declared income.

        The IRRF ratio should be consistent with tax brackets.
        Anomalies may indicate:
        - Typing errors
        - Missing income
        - Incorrect IRRF values
        """
        for rend in self.declaration.rendimentos:
            # Only check employment income (has predictable IRRF)
            if rend.tipo not in (
                TipoRendimento.TRABALHO_ASSALARIADO,
                TipoRendimento.TRABALHO_NAO_ASSALARIADO,
            ):
                continue

            if rend.valor_anual <= 0:
                continue

            # Calculate actual IRRF ratio
            irrf_ratio = rend.imposto_retido / rend.valor_anual if rend.valor_anual > 0 else Decimal("0")

            # Find expected bracket
            for min_income, max_income, min_ratio, max_ratio in self.IRRF_BRACKETS:
                if min_income <= rend.valor_anual < max_income:
                    # Check if IRRF is within expected range
                    if irrf_ratio > 0 and irrf_ratio < min_ratio - Decimal("0.02"):
                        # IRRF is too low for this income bracket
                        fonte = rend.fonte_pagadora.nome if rend.fonte_pagadora else "Não informada"
                        self.warnings.append(
                            Warning(
                                mensagem=(
                                    f"IRRF baixo para a faixa de renda: {irrf_ratio*100:.1f}% "
                                    f"(esperado mín {min_ratio*100:.0f}%) - {fonte}"
                                ),
                                risco=RiskLevel.LOW,
                                campo="rendimentos",
                                categoria=WarningCategory.CONSISTENCIA,
                                valor_impacto=rend.imposto_retido,
                            )
                        )
                    elif irrf_ratio > max_ratio + Decimal("0.05"):
                        # IRRF is too high for this income bracket
                        fonte = rend.fonte_pagadora.nome if rend.fonte_pagadora else "Não informada"
                        self.warnings.append(
                            Warning(
                                mensagem=(
                                    f"IRRF alto para a faixa de renda: {irrf_ratio*100:.1f}% "
                                    f"(esperado máx {max_ratio*100:.0f}%) - {fonte}. "
                                    f"Possível rendimento não declarado."
                                ),
                                risco=RiskLevel.MEDIUM,
                                campo="rendimentos",
                                categoria=WarningCategory.CONSISTENCIA,
                                valor_impacto=rend.imposto_retido,
                            )
                        )
                    break

    def _check_income_concentration(self) -> None:
        """Check for suspicious income concentration patterns.

        High concentration in single source may indicate:
        - Omission of other income sources
        - Dependency on single employer
        - Need for diversification (informational)
        """
        rendimentos_tributaveis = [
            r for r in self.declaration.rendimentos
            if r.tipo in (
                TipoRendimento.TRABALHO_ASSALARIADO,
                TipoRendimento.TRABALHO_NAO_ASSALARIADO,
                TipoRendimento.ALUGUEIS,
                TipoRendimento.LUCROS_DIVIDENDOS,
                TipoRendimento.RENDIMENTOS_PJ,
            ) and r.valor_anual > 0
        ]

        if len(rendimentos_tributaveis) < 2:
            return  # Need at least 2 sources for concentration analysis

        valores = [r.valor_anual for r in rendimentos_tributaveis]
        total = sum(valores)

        if total <= 0:
            return

        # Calculate Gini coefficient
        gini = calcular_indice_gini(valores)

        # Check concentration
        if gini > self.GINI_CONCENTRACAO_LIMITE:
            # Find dominant source
            maior_rend = max(rendimentos_tributaveis, key=lambda r: r.valor_anual)
            percentual = maior_rend.valor_anual / total * 100
            fonte = maior_rend.fonte_pagadora.nome if maior_rend.fonte_pagadora else "Não informada"

            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Renda altamente concentrada (Gini={gini:.2f}): "
                        f"{percentual:.0f}% de {fonte}. "
                        f"Verifique se há outras fontes de renda não declaradas."
                    ),
                    risco=RiskLevel.LOW,
                    campo="rendimentos",
                    categoria=WarningCategory.CONSISTENCIA,
                    informativo=True,
                )
            )

        # Check for identical values (possible duplication error)
        valor_counts = Counter(valores)
        for valor, count in valor_counts.items():
            if count >= 2 and valor > Decimal("10000"):
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Rendimentos idênticos detectados: {count}x R$ {valor:,.2f}. "
                            f"Verifique se não há duplicação."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="rendimentos",
                        categoria=WarningCategory.CONSISTENCIA,
                        valor_impacto=valor * (count - 1),  # Extra value
                    )
                )

    def _check_previdencia_vs_clt(self) -> None:
        """Validate previdência oficial (INSS) against CLT income.

        CLT workers must have INSS contribution. Discrepancies indicate:
        - Missing INSS deduction
        - Incorrect income classification
        - Possible informal employment
        """
        # Sum all CLT income
        renda_clt = Decimal("0")
        previdencia_declarada = Decimal("0")

        for rend in self.declaration.rendimentos:
            if rend.tipo == TipoRendimento.TRABALHO_ASSALARIADO:
                renda_clt += rend.valor_anual
                previdencia_declarada += rend.contribuicao_previdenciaria

        if renda_clt <= 0:
            return  # No CLT income

        # Calculate expected INSS range
        # Cap at INSS ceiling
        base_calculo = min(renda_clt, self.TETO_INSS_ANUAL)
        previdencia_min_esperada = base_calculo * self.PREVIDENCIA_MIN_RATIO
        previdencia_max_esperada = base_calculo * self.PREVIDENCIA_MAX_RATIO

        if previdencia_declarada == 0 and renda_clt > Decimal("27110.52"):
            # CLT income but no INSS - suspicious
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.VALOR_ZERADO_SUSPEITO,
                    descricao=(
                        f"Renda CLT de R$ {renda_clt:,.2f} declarada, "
                        f"mas sem contribuição previdenciária (INSS)"
                    ),
                    valor_declarado=Decimal("0"),
                    valor_esperado=previdencia_min_esperada,
                    risco=RiskLevel.HIGH,
                    recomendacao=(
                        "Trabalhadores CLT devem ter INSS retido. "
                        "Verifique informe de rendimentos."
                    ),
                    valor_impacto=previdencia_min_esperada,
                )
            )
        elif previdencia_declarada > 0:
            ratio = previdencia_declarada / renda_clt

            if ratio < self.PREVIDENCIA_MIN_RATIO - Decimal("0.02"):
                # INSS too low
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Contribuição previdenciária baixa: {ratio*100:.1f}% da renda CLT "
                            f"(esperado mín {self.PREVIDENCIA_MIN_RATIO*100:.0f}%)"
                        ),
                        risco=RiskLevel.LOW,
                        campo="rendimentos",
                        categoria=WarningCategory.CONSISTENCIA,
                    )
                )
            elif ratio > self.PREVIDENCIA_MAX_RATIO + Decimal("0.02"):
                # INSS too high
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Contribuição previdenciária alta: {ratio*100:.1f}% da renda CLT "
                            f"(esperado máx {self.PREVIDENCIA_MAX_RATIO*100:.0f}%)"
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="rendimentos",
                        categoria=WarningCategory.CONSISTENCIA,
                        valor_impacto=previdencia_declarada - previdencia_max_esperada,
                    )
                )

    def _check_pensao_proporcionalidade(self) -> None:
        """Validate alimony (pensão alimentícia) proportionality.

        Alimony deductions should be proportional to income.
        Anomalies may indicate:
        - Inflated alimony values
        - Attempt to reduce tax base artificially
        """
        # Get total alimony
        pensao_total = sum(
            d.valor for d in self.declaration.deducoes
            if d.tipo == TipoDeducao.PENSAO_ALIMENTICIA and d.valor > 0
        )

        if pensao_total <= 0:
            return  # No alimony declared

        # Get total income
        renda_total = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
        )

        if renda_total <= 0:
            return

        ratio = pensao_total / renda_total

        if ratio > self.PENSAO_MAX_RATIO:
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.DESPESAS_MEDICAS_ALTAS,  # Using similar type
                    descricao=(
                        f"Pensão alimentícia representa {ratio*100:.0f}% da renda "
                        f"(R$ {pensao_total:,.2f} de R$ {renda_total:,.2f}). "
                        f"Valor acima do esperado (máx ~{self.PENSAO_MAX_RATIO*100:.0f}%)"
                    ),
                    valor_declarado=pensao_total,
                    valor_esperado=renda_total * self.PENSAO_MAX_RATIO,
                    risco=RiskLevel.HIGH,
                    recomendacao=(
                        "Pensão alimentícia muito alta em relação à renda. "
                        "Tenha documentação judicial comprobatória."
                    ),
                    valor_impacto=pensao_total - (renda_total * self.PENSAO_MAX_RATIO),
                )
            )
        elif ratio > Decimal("0.30"):
            # Warning for moderately high values
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Pensão alimentícia representa {ratio*100:.0f}% da renda. "
                        f"Valor significativo - mantenha documentação comprobatória."
                    ),
                    risco=RiskLevel.LOW,
                    campo="deducoes",
                    categoria=WarningCategory.DEDUCAO,
                    informativo=True,
                    valor_impacto=pensao_total,
                )
            )

    def _check_livro_caixa_vs_autonomo(self) -> None:
        """Validate livro-caixa (cash book) vs autonomous income.

        Livro-caixa deductions are only valid for autonomous professionals.
        Discrepancies may indicate:
        - Incorrect use of livro-caixa by CLT workers
        - Missing autonomous income declaration
        """
        # Get livro-caixa deductions
        livro_caixa = sum(
            d.valor for d in self.declaration.deducoes
            if d.tipo == TipoDeducao.LIVRO_CAIXA and d.valor > 0
        )

        if livro_caixa <= 0:
            return  # No livro-caixa

        # Get autonomous income
        renda_autonoma = sum(
            r.valor_anual for r in self.declaration.rendimentos
            if r.tipo == TipoRendimento.TRABALHO_NAO_ASSALARIADO and r.valor_anual > 0
        )

        if renda_autonoma <= 0:
            # Livro-caixa without autonomous income - invalid
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.DEDUCAO_SEM_COMPROVANTE,
                    descricao=(
                        f"Dedução de livro-caixa (R$ {livro_caixa:,.2f}) "
                        f"sem rendimentos de trabalho autônomo declarados"
                    ),
                    valor_declarado=livro_caixa,
                    valor_esperado=Decimal("0"),
                    risco=RiskLevel.HIGH,
                    recomendacao=(
                        "Livro-caixa é válido apenas para profissionais autônomos. "
                        "Declare os rendimentos de trabalho não-assalariado correspondentes."
                    ),
                    valor_impacto=livro_caixa,
                )
            )
        else:
            # Check proportion
            ratio = livro_caixa / renda_autonoma
            if ratio > Decimal("0.80"):
                # Livro-caixa > 80% of autonomous income
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Livro-caixa representa {ratio*100:.0f}% da renda autônoma. "
                            f"Despesas muito altas - mantenha documentação completa."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="deducoes",
                        categoria=WarningCategory.DEDUCAO,
                        valor_impacto=livro_caixa,
                    )
                )

    def _check_income_source_duplicates(self) -> None:
        """Check for duplicate income sources (same CNPJ/CPF).

        Duplicate entries may indicate:
        - Data entry error
        - Double counting of same income
        """
        # Group by payment source
        por_fonte: dict[str, list] = {}

        for rend in self.declaration.rendimentos:
            if not rend.fonte_pagadora:
                continue

            cnpj_cpf = rend.fonte_pagadora.cnpj_cpf
            if cnpj_cpf not in por_fonte:
                por_fonte[cnpj_cpf] = []
            por_fonte[cnpj_cpf].append(rend)

        # Check for duplicates
        for cnpj_cpf, rendimentos in por_fonte.items():
            if len(rendimentos) < 2:
                continue

            # Group by tipo
            por_tipo: dict[TipoRendimento, list] = {}
            for rend in rendimentos:
                if rend.tipo not in por_tipo:
                    por_tipo[rend.tipo] = []
                por_tipo[rend.tipo].append(rend)

            for tipo, rends in por_tipo.items():
                if len(rends) >= 2:
                    # Same CNPJ, same type, multiple entries
                    total = sum(r.valor_anual for r in rends)
                    nome = rends[0].fonte_pagadora.nome if rends[0].fonte_pagadora else "?"

                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Múltiplos rendimentos do tipo '{tipo.value}' da mesma fonte "
                                f"({nome}): {len(rends)} entradas totalizando R$ {total:,.2f}. "
                                f"Verifique se há duplicação."
                            ),
                            risco=RiskLevel.MEDIUM,
                            campo="rendimentos",
                            categoria=WarningCategory.CONSISTENCIA,
                            valor_impacto=total / len(rends),  # Potential duplicate value
                        )
                    )

    def _check_decimo_terceiro_consistency(self) -> None:
        """Validate 13th salary consistency.

        13th salary should be approximately 1/12 of annual CLT income.
        Large discrepancies may indicate errors.
        """
        for rend in self.declaration.rendimentos:
            if rend.tipo != TipoRendimento.TRABALHO_ASSALARIADO:
                continue

            if rend.valor_anual <= 0 or rend.decimo_terceiro <= 0:
                continue

            # Expected 13th = ~8.3% of annual (1/12)
            esperado = rend.valor_anual / 12
            tolerancia = esperado * Decimal("0.20")  # 20% tolerance

            if abs(rend.decimo_terceiro - esperado) > tolerancia:
                fonte = rend.fonte_pagadora.nome if rend.fonte_pagadora else "Não informada"

                if rend.decimo_terceiro > esperado * Decimal("1.5"):
                    # Much higher than expected
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"13º salário acima do esperado de {fonte}: "
                                f"R$ {rend.decimo_terceiro:,.2f} vs esperado ~R$ {esperado:,.2f}"
                            ),
                            risco=RiskLevel.LOW,
                            campo="rendimentos",
                            categoria=WarningCategory.CONSISTENCIA,
                            informativo=True,
                        )
                    )
                elif rend.decimo_terceiro < esperado * Decimal("0.5"):
                    # Much lower than expected
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"13º salário abaixo do esperado de {fonte}: "
                                f"R$ {rend.decimo_terceiro:,.2f} vs esperado ~R$ {esperado:,.2f}"
                            ),
                            risco=RiskLevel.LOW,
                            campo="rendimentos",
                            categoria=WarningCategory.CONSISTENCIA,
                            informativo=True,
                        )
                    )

    def _check_rendimentos_isentos_ratio(self) -> None:
        """Check ratio of exempt income vs taxable income.

        High ratio of exempt income may indicate:
        - Aggressive tax planning
        - Income misclassification
        - Need for extra documentation
        """
        renda_tributavel = self.declaration.total_rendimentos_tributaveis
        renda_isenta = self.declaration.total_rendimentos_isentos

        if renda_tributavel <= 0 or renda_isenta <= 0:
            return

        total = renda_tributavel + renda_isenta
        ratio_isenta = renda_isenta / total

        if ratio_isenta > Decimal("0.60"):
            # More than 60% exempt income
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Proporção alta de rendimentos isentos: {ratio_isenta*100:.0f}% do total "
                        f"(R$ {renda_isenta:,.2f} de R$ {total:,.2f}). "
                        f"Mantenha documentação comprobatória."
                    ),
                    risco=RiskLevel.LOW,
                    campo="rendimentos",
                    categoria=WarningCategory.CONSISTENCIA,
                    informativo=True,
                )
            )


def analyze_income(declaration: Declaration) -> tuple[list[Inconsistency], list[Warning]]:
    """Convenience function to run income analysis.

    Args:
        declaration: Declaration to analyze

    Returns:
        Tuple of (inconsistencies, warnings) found
    """
    analyzer = IncomeAnalyzer(declaration)
    return analyzer.analyze()
