"""Deduction analyzer for IRPF declarations."""

from decimal import Decimal

from irpf_analyzer.core.models.analysis import (
    Inconsistency,
    InconsistencyType,
    RiskLevel,
    Warning,
)
from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import TipoDeducao


class DeductionAnalyzer:
    """Analyzes deductions for suspicious patterns."""

    # Medical expenses above 15% of income is a red flag
    MEDICAL_EXPENSE_THRESHOLD = Decimal("0.15")

    # Education expense limit per dependent (2024)
    EDUCATION_LIMIT_2024 = Decimal("3561.50")

    # Deduction per dependent (2024)
    DEPENDENT_DEDUCTION_2024 = Decimal("2275.08")

    def __init__(self, declaration: Declaration):
        self.declaration = declaration
        self.inconsistencies: list[Inconsistency] = []
        self.warnings: list[Warning] = []

    def analyze(self) -> tuple[list[Inconsistency], list[Warning]]:
        """Run all deduction checks."""
        self._check_medical_expenses()
        self._check_education_expenses()
        self._check_dependent_deductions()
        self._check_high_value_deductions()

        return self.inconsistencies, self.warnings

    def _check_medical_expenses(self) -> None:
        """Check if medical expenses are suspiciously high."""
        resumo = self.declaration.resumo_deducoes
        despesas_medicas = resumo.despesas_medicas

        # Get total income
        renda_total = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
        )

        if renda_total <= 0 or despesas_medicas <= 0:
            return

        ratio = despesas_medicas / renda_total

        if ratio > self.MEDICAL_EXPENSE_THRESHOLD:
            percentual = ratio * 100

            if percentual > 30:
                risco = RiskLevel.HIGH
            elif percentual > 20:
                risco = RiskLevel.MEDIUM
            else:
                risco = RiskLevel.LOW

            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.DESPESAS_MEDICAS_ALTAS,
                    descricao=(
                        f"Despesas médicas representam {percentual:.1f}% da renda "
                        f"(R$ {despesas_medicas:,.2f} de R$ {renda_total:,.2f})"
                    ),
                    valor_declarado=despesas_medicas,
                    valor_esperado=renda_total * self.MEDICAL_EXPENSE_THRESHOLD,
                    risco=risco,
                    recomendacao=(
                        "Proporção alta de despesas médicas requer "
                        "documentação completa (notas fiscais, recibos)"
                    ),
                )
            )

    def _check_education_expenses(self) -> None:
        """Check education expenses against legal limits."""
        resumo = self.declaration.resumo_deducoes
        despesas_educacao = resumo.despesas_educacao

        if despesas_educacao <= 0:
            return

        # Calculate maximum allowed (titulars + dependents)
        num_pessoas = 1 + len(self.declaration.dependentes)
        limite_maximo = self.EDUCATION_LIMIT_2024 * num_pessoas

        if despesas_educacao > limite_maximo:
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.DESPESAS_EDUCACAO_LIMITE,
                    descricao=(
                        f"Despesas com educação (R$ {despesas_educacao:,.2f}) "
                        f"excedem limite legal de R$ {limite_maximo:,.2f} "
                        f"para {num_pessoas} pessoa(s)"
                    ),
                    valor_declarado=despesas_educacao,
                    valor_esperado=limite_maximo,
                    risco=RiskLevel.HIGH,
                    recomendacao=(
                        "Limite de dedução com educação é "
                        f"R$ {self.EDUCATION_LIMIT_2024:,.2f} por pessoa/ano"
                    ),
                )
            )

    def _check_dependent_deductions(self) -> None:
        """Check dependent-related deductions."""
        num_dependentes = len(self.declaration.dependentes)

        if num_dependentes == 0:
            return

        # Check for duplicate CPFs among dependents
        cpfs = [d.cpf for d in self.declaration.dependentes]
        seen = set()
        duplicates = set()

        for cpf in cpfs:
            if cpf in seen:
                duplicates.add(cpf)
            seen.add(cpf)

        if duplicates:
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.DEPENDENTE_DUPLICADO,
                    descricao=(
                        f"CPF(s) de dependente(s) duplicado(s): "
                        f"{', '.join(duplicates)}"
                    ),
                    risco=RiskLevel.CRITICAL,
                    recomendacao="Cada dependente deve aparecer apenas uma vez",
                )
            )

    def _check_high_value_deductions(self) -> None:
        """Check for high-value individual deductions that need attention."""
        for deducao in self.declaration.deducoes:
            # Medical expense over 5000 should have clear documentation
            if (
                deducao.tipo == TipoDeducao.DESPESAS_MEDICAS
                and deducao.valor > Decimal("5000")
            ):
                if not deducao.cnpj_prestador:
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Despesa médica de R$ {deducao.valor:,.2f} "
                                f"sem CNPJ do prestador informado"
                            ),
                            risco=RiskLevel.MEDIUM,
                            campo="deducoes",
                        )
                    )
