"""Cross-validation analyzer for simulating Receita Federal data crossings.

This module simulates the automatic crossings that the Brazilian Federal Revenue
performs to detect inconsistencies:
- DIRF: Cross with employer-reported income
- DIMOB: Cross with real estate transactions
- DOC/TED: Cross with bank transfers
- e-Financeira: Cross with financial institution reports
- DECRED: Cross with credit card transactions
- DMED: Cross with medical provider reports
"""

from collections import defaultdict
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
from irpf_analyzer.core.models.enums import GrupoBem, TipoDeducao, TipoRendimento
from irpf_analyzer.shared.statistics import (
    calcular_indice_gini,
    calcular_coeficiente_variacao,
)
from irpf_analyzer.core.rules.tax_constants import LIMITE_EFINANCEIRA


class CrossValidationAnalyzer:
    """Simulates Receita Federal cross-validation checks.

    This analyzer doesn't have access to actual government databases,
    but it can:
    1. Flag values that are likely to be cross-referenced
    2. Identify patterns that typically trigger crossings
    3. Warn about common divergence scenarios
    4. Calculate risk based on exposure to automatic detection
    """

    # Threshold for significant bank balance (e-Financeira reports > R$ 5000)
    EFINANCEIRA_THRESHOLD = LIMITE_EFINANCEIRA

    # Threshold for high medical expenses that trigger DMED crossing
    DMED_THRESHOLD = Decimal("5000")

    # Threshold for rental income that triggers DIMOB crossing
    DIMOB_RENTAL_THRESHOLD = Decimal("6000")  # Per month

    # Real estate transaction threshold for DIMOB
    DIMOB_TRANSACTION_THRESHOLD = Decimal("30000")

    # Credit card threshold for DECRED
    DECRED_THRESHOLD = Decimal("5000")  # Monthly

    def __init__(self, declaration: Declaration):
        self.declaration = declaration
        self.inconsistencies: list[Inconsistency] = []
        self.warnings: list[Warning] = []

    def analyze(self) -> tuple[list[Inconsistency], list[Warning]]:
        """Run all cross-validation simulations.

        Returns:
            Tuple of (inconsistencies, warnings) found
        """
        self._check_dirf_crossing()
        self._check_dimob_crossing()
        self._check_efinanceira_crossing()
        self._check_dmed_crossing()
        self._check_decred_exposure()
        self._check_employer_consistency()
        self._check_rental_income_dimob()
        self._check_asset_acquisition_doc()

        return self.inconsistencies, self.warnings

    def _check_dirf_crossing(self) -> None:
        """Simulate DIRF (employer income declaration) crossing.

        DIRF is filed by employers reporting all payments to employees.
        The system automatically crosses this with individual declarations.

        Red flags:
        - Income declared lower than DIRF would show
        - IRRF different from what employer reported
        - Missing income sources
        """
        for rend in self.declaration.rendimentos:
            if rend.tipo not in (
                TipoRendimento.TRABALHO_ASSALARIADO,
                TipoRendimento.TRABALHO_NAO_ASSALARIADO,
                TipoRendimento.RENDIMENTOS_PJ,
            ):
                continue

            if not rend.fonte_pagadora:
                continue

            # Flag high-value income that will definitely be crossed
            if rend.valor_anual > Decimal("100000"):
                # Just informational - this WILL be crossed
                pass  # Normal, no warning needed

            # Check for potential IRRF divergence
            if rend.valor_anual > Decimal("50000") and rend.imposto_retido == 0:
                # High income with no IRRF - employer may have reported differently
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Renda de R$ {rend.valor_anual:,.2f} sem IRRF declarado. "
                            f"O empregador ({rend.fonte_pagadora.nome}) reporta via DIRF - "
                            f"divergências serão detectadas automaticamente."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="rendimentos",
                        categoria=WarningCategory.CONSISTENCIA,
                        valor_impacto=rend.valor_anual,
                    )
                )

    def _check_dimob_crossing(self) -> None:
        """Simulate DIMOB (real estate declaration) crossing.

        DIMOB is filed by real estate companies, notaries, and property managers
        reporting all real estate transactions and rental income.

        Red flags:
        - Property purchases without declared source
        - Sales without declared capital gains
        - Rental income not matching property manager reports
        """
        # Check for real estate purchases without financing or income source
        for bem in self.declaration.bens_direitos:
            if bem.codigo not in PatternAnalyzerCodes.CODIGOS_IMOVEIS:
                continue

            # New property acquisition
            if bem.situacao_anterior == 0 and bem.situacao_atual > Decimal("100000"):
                # This will be crossed with DIMOB
                renda_total = (
                    self.declaration.total_rendimentos_tributaveis
                    + self.declaration.total_rendimentos_isentos
                )

                if bem.situacao_atual > renda_total:
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Aquisição de imóvel (R$ {bem.situacao_atual:,.2f}) "
                                f"será cruzada com DIMOB. Valor superior à renda declarada "
                                f"(R$ {renda_total:,.2f}) - tenha documentação de origem."
                            ),
                            risco=RiskLevel.MEDIUM,
                            campo="bens_direitos",
                            categoria=WarningCategory.CONSISTENCIA,
                            valor_impacto=bem.situacao_atual,
                        )
                    )

    def _check_efinanceira_crossing(self) -> None:
        """Simulate e-Financeira crossing.

        Financial institutions report monthly balances > R$ 5,000 and
        all financial movements to the Receita Federal.

        Red flags:
        - Bank balance not declared
        - Financial applications not declared
        - Movements inconsistent with declared income
        """
        # Calculate total financial assets declared
        total_financeiro = Decimal("0")
        depositos_vista = Decimal("0")
        aplicacoes = Decimal("0")

        for bem in self.declaration.bens_direitos:
            if bem.grupo == GrupoBem.DEPOSITOS_VISTA:
                depositos_vista += bem.situacao_atual
            elif bem.grupo in (
                GrupoBem.APLICACOES_FINANCEIRAS,
                GrupoBem.POUPANCA,
                GrupoBem.FUNDOS,
            ):
                aplicacoes += bem.situacao_atual
            total_financeiro += bem.situacao_atual

        # Check if financial assets are consistent with income
        renda_total = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
            + self.declaration.total_rendimentos_exclusivos
        )

        if total_financeiro > renda_total * Decimal("3"):
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Patrimônio financeiro (R$ {total_financeiro:,.2f}) "
                        f"muito superior à renda declarada (R$ {renda_total:,.2f}). "
                        f"e-Financeira reporta automaticamente - "
                        f"mantenha documentação de origem."
                    ),
                    risco=RiskLevel.LOW,
                    campo="bens_direitos",
                    categoria=WarningCategory.CONSISTENCIA,
                    informativo=True,
                )
            )

        # Warn about e-Financeira threshold
        if depositos_vista > self.EFINANCEIRA_THRESHOLD or aplicacoes > self.EFINANCEIRA_THRESHOLD:
            # Just informational - this is normal
            pass

    def _check_dmed_crossing(self) -> None:
        """Simulate DMED (medical declaration) crossing.

        Medical providers report all payments received via DMED.
        The system crosses this with declared medical deductions.

        Red flags:
        - Medical expenses with providers that didn't report
        - Values different from provider reports
        - Fictitious provider CNPJs
        """
        despesas_medicas = [
            d for d in self.declaration.deducoes
            if d.tipo == TipoDeducao.DESPESAS_MEDICAS and d.valor > 0
        ]

        if not despesas_medicas:
            return

        total_medico = sum(d.valor for d in despesas_medicas)

        # Group by provider
        por_prestador: dict[str, Decimal] = {}
        for d in despesas_medicas:
            cnpj = d.cnpj_prestador or d.cpf_prestador or "SEM_ID"
            por_prestador[cnpj] = por_prestador.get(cnpj, Decimal("0")) + d.valor

        # Check high values that will definitely be crossed
        for cnpj, valor in por_prestador.items():
            if valor > self.DMED_THRESHOLD:
                if cnpj == "SEM_ID":
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Despesas médicas de R$ {valor:,.2f} sem identificação "
                                f"do prestador. DMED cruza automaticamente - "
                                f"despesas sem CPF/CNPJ têm maior risco de rejeição."
                            ),
                            risco=RiskLevel.MEDIUM,
                            campo="deducoes",
                            categoria=WarningCategory.DEDUCAO,
                            valor_impacto=valor,
                        )
                    )
                else:
                    # Informational - will be crossed
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Despesas médicas de R$ {valor:,.2f} serão cruzadas "
                                f"com DMED do prestador. Guarde recibos/notas fiscais."
                            ),
                            risco=RiskLevel.LOW,
                            campo="deducoes",
                            categoria=WarningCategory.DEDUCAO,
                            informativo=True,
                        )
                    )

    def _check_decred_exposure(self) -> None:
        """Check exposure to DECRED (credit card declaration) crossing.

        Credit card companies report all users who spend > R$ 5,000/month.
        High spending with low declared income raises red flags.
        """
        # We can't know actual credit card spending from the declaration,
        # but we can estimate lifestyle based on patrimony and income
        renda_total = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
        )

        patrimonio = self.declaration.resumo_patrimonio.total_bens_atual

        # High patrimony with low income suggests lifestyle inconsistency
        if patrimonio > Decimal("1000000") and renda_total < Decimal("100000"):
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Patrimônio alto (R$ {patrimonio:,.2f}) com renda relativamente "
                        f"baixa (R$ {renda_total:,.2f}). DECRED reporta gastos em cartão - "
                        f"estilo de vida deve ser compatível com renda declarada."
                    ),
                    risco=RiskLevel.LOW,
                    campo="geral",
                    categoria=WarningCategory.CONSISTENCIA,
                    informativo=True,
                )
            )

    def _check_employer_consistency(self) -> None:
        """Check consistency between employer data.

        Multiple employments should have consistent data.
        Benefits like health insurance should match across sources.
        """
        empregadores = {}
        for rend in self.declaration.rendimentos:
            if rend.tipo != TipoRendimento.TRABALHO_ASSALARIADO:
                continue
            if not rend.fonte_pagadora:
                continue

            cnpj = rend.fonte_pagadora.cnpj_cpf
            if cnpj in empregadores:
                # Multiple entries from same employer
                existing = empregadores[cnpj]
                if abs(existing - rend.valor_anual) > Decimal("1000"):
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Múltiplas entradas de renda do mesmo empregador "
                                f"({rend.fonte_pagadora.nome}). Verifique se não há duplicação."
                            ),
                            risco=RiskLevel.MEDIUM,
                            campo="rendimentos",
                            categoria=WarningCategory.CONSISTENCIA,
                            valor_impacto=rend.valor_anual,
                        )
                    )
            else:
                empregadores[cnpj] = rend.valor_anual

    def _check_rental_income_dimob(self) -> None:
        """Check rental income for DIMOB exposure.

        Property managers report all rental payments via DIMOB.
        Rental income must match manager reports.
        Uses built properties only (excludes land/terrenos which are not rentable).
        """
        # Check if has built properties but no rental income
        # Excludes terrenos (code 13) and terra nua (code 18) as they are not typically rented
        imoveis_edificados = [
            b for b in self.declaration.bens_direitos
            if b.codigo in PatternAnalyzerCodes.CODIGOS_IMOVEIS_EDIFICADOS
            and b.situacao_atual > 0
        ]

        renda_aluguel = sum(
            r.valor_anual for r in self.declaration.rendimentos
            if r.tipo == TipoRendimento.ALUGUEIS
        )

        # Multiple built properties but no rental income
        if len(imoveis_edificados) >= 2 and renda_aluguel == 0:
            total_imoveis = sum(i.situacao_atual for i in imoveis_edificados)
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Possui {len(imoveis_edificados)} imóveis edificados (R$ {total_imoveis:,.2f}) "
                        f"sem renda de aluguel declarada. Se algum está alugado, "
                        f"DIMOB reportará e haverá cruzamento automático."
                    ),
                    risco=RiskLevel.LOW,
                    campo="rendimentos",
                    categoria=WarningCategory.CONSISTENCIA,
                    informativo=True,
                )
            )

    def _check_asset_acquisition_doc(self) -> None:
        """Check asset acquisitions that may trigger DOC/TED crossing.

        Large transfers > R$ 10,000 are reported via DOC.
        Asset acquisitions should match bank transfer records.
        """
        for bem in self.declaration.bens_direitos:
            # New high-value acquisition
            if bem.situacao_anterior == 0 and bem.situacao_atual > Decimal("50000"):
                # Will likely have DOC/TED record
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Aquisição de R$ {bem.situacao_atual:,.2f} será cruzada "
                            f"com registros de DOC/TED. Mantenha documentação de "
                            f"transferência e origem dos recursos."
                        ),
                        risco=RiskLevel.LOW,
                        campo="bens_direitos",
                        categoria=WarningCategory.CONSISTENCIA,
                        informativo=True,
                    )
                )


class PatternAnalyzerCodes:
    """Asset codes for cross-validation checks."""

    CODIGOS_IMOVEIS = {"11", "12", "13", "14", "15", "16", "17", "18", "19"}
    # Imóveis edificados (excluindo terrenos - código 13 e terra nua - código 18)
    CODIGOS_IMOVEIS_EDIFICADOS = {"11", "12", "14", "15", "16", "17", "19"}
    CODIGOS_VEICULOS = {"21", "22", "23", "24", "25", "26", "27", "28", "29"}
    CODIGOS_PARTICIPACOES = {"31", "32", "39"}


def analyze_cross_validation(declaration: Declaration) -> tuple[list[Inconsistency], list[Warning]]:
    """Convenience function to run cross-validation analysis.

    Args:
        declaration: Declaration to analyze

    Returns:
        Tuple of (inconsistencies, warnings) found
    """
    analyzer = CrossValidationAnalyzer(declaration)
    return analyzer.analyze()
