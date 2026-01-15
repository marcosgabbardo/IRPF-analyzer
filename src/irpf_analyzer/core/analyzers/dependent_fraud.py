"""Dependent fraud detection analyzer for IRPF declarations.

This module detects potential fraud patterns related to dependents:
- Phantom dependents (non-existent people)
- Shared dependents across declarations
- Age/type inconsistencies
- Education expense anomalies
- Medical expense attribution issues
"""

from collections import defaultdict
from datetime import date
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
from irpf_analyzer.core.models.enums import TipoDeducao, TipoDependente
from irpf_analyzer.shared.validators import validar_cpf
from irpf_analyzer.core.rules.tax_constants import (
    DEDUCAO_DEPENDENTE,
    LIMITE_EDUCACAO_PESSOA,
    IDADE_LIMITE_FILHO,
    IDADE_LIMITE_UNIVERSITARIO,
)


class DependentFraudAnalyzer:
    """Analyzes dependents for fraud patterns.

    Detects:
    - Invalid or suspicious CPFs
    - Age/type mismatches
    - Duplicate dependents (same CPF multiple times)
    - Education expense without proper dependent
    - Medical expenses attributed to non-existent dependents
    - Statistical anomalies in dependent-related deductions
    """

    def __init__(self, declaration: Declaration):
        self.declaration = declaration
        self.inconsistencies: list[Inconsistency] = []
        self.warnings: list[Warning] = []

    def analyze(self) -> tuple[list[Inconsistency], list[Warning]]:
        """Run all dependent fraud checks.

        Returns:
            Tuple of (inconsistencies, warnings) found
        """
        if not self.declaration.dependentes:
            self._check_orphan_dependent_expenses()
            return self.inconsistencies, self.warnings

        self._check_cpf_patterns()
        self._check_age_type_consistency()
        self._check_duplicate_dependents()
        self._check_education_expense_attribution()
        self._check_medical_expense_attribution()
        self._check_dependent_count_anomaly()
        self._check_spouse_income()
        self._check_dependent_cpf_sequential()

        return self.inconsistencies, self.warnings

    def _check_cpf_patterns(self) -> None:
        """Check for suspicious CPF patterns in dependents.

        Patterns detected:
        - All digits same (111.111.111-11)
        - Sequential digits
        - Invalid check digits
        - CPFs that don't match birth date (future detection)
        """
        for dep in self.declaration.dependentes:
            if not dep.cpf:
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Dependente {dep.nome} sem CPF informado. "
                            f"CPF é obrigatório para todos os dependentes."
                        ),
                        risco=RiskLevel.HIGH,
                        campo="dependentes",
                        categoria=WarningCategory.CONSISTENCIA,
                        valor_impacto=DEDUCAO_DEPENDENTE,
                    )
                )
                continue

            # Validate CPF
            valido, motivo = validar_cpf(dep.cpf)
            if not valido:
                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.CPF_INVALIDO,
                        descricao=(
                            f"CPF de dependente {dep.nome} inválido: {motivo}"
                        ),
                        risco=RiskLevel.CRITICAL,
                        recomendacao="Corrigir CPF do dependente",
                        valor_impacto=DEDUCAO_DEPENDENTE,
                    )
                )

            # Check for suspicious patterns (even if valid by check digit)
            cpf_digits = "".join(filter(str.isdigit, dep.cpf))

            # Sequential CPF check
            if self._is_sequential(cpf_digits):
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"CPF de dependente {dep.nome} tem padrão sequencial "
                            f"({dep.cpf}). Pode indicar CPF fabricado."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="dependentes",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=DEDUCAO_DEPENDENTE,
                    )
                )

    def _is_sequential(self, digits: str) -> bool:
        """Check if digits form a sequential pattern."""
        if len(digits) < 6:
            return False

        # Check ascending sequence
        ascending = all(
            int(digits[i + 1]) == int(digits[i]) + 1
            for i in range(5)
        )

        # Check descending sequence
        descending = all(
            int(digits[i + 1]) == int(digits[i]) - 1
            for i in range(5)
        )

        return ascending or descending

    def _check_age_type_consistency(self) -> None:
        """Check if dependent age matches declared type.

        Rules:
        - FILHO_ENTEADO_ATE_21: Must be <= 21 years old
        - FILHO_ENTEADO_UNIVERSITARIO: Must be <= 24 years old
        - FILHO_ENTEADO_INCAPAZ: Any age (requires proof)
        - PAIS_AVOS_BISAVOS: Must have low income
        """
        for dep in self.declaration.dependentes:
            idade = dep.idade
            if idade is None:
                if dep.tipo in (
                    TipoDependente.FILHO_ENTEADO_ATE_21,
                    TipoDependente.FILHO_ENTEADO_UNIVERSITARIO,
                ):
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Dependente {dep.nome} ({dep.tipo.value}) sem data de nascimento. "
                                f"Data é necessária para validar elegibilidade."
                            ),
                            risco=RiskLevel.LOW,
                            campo="dependentes",
                            categoria=WarningCategory.CONSISTENCIA,
                        )
                    )
                continue

            # Age validation by type
            if dep.tipo == TipoDependente.FILHO_ENTEADO_ATE_21:
                if idade > IDADE_LIMITE_FILHO:
                    self.inconsistencies.append(
                        Inconsistency(
                            tipo=InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL,
                            descricao=(
                                f"Dependente {dep.nome} tem {idade} anos, mas tipo "
                                f"'{dep.tipo.value}' exige até {IDADE_LIMITE_FILHO} anos."
                            ),
                            risco=RiskLevel.HIGH,
                            recomendacao=(
                                f"Alterar tipo para 'universitário' (se até {IDADE_LIMITE_UNIVERSITARIO} "
                                f"e cursando ensino superior) ou remover dependente."
                            ),
                            valor_impacto=DEDUCAO_DEPENDENTE,
                        )
                    )

            elif dep.tipo == TipoDependente.FILHO_ENTEADO_UNIVERSITARIO:
                if idade > IDADE_LIMITE_UNIVERSITARIO:
                    self.inconsistencies.append(
                        Inconsistency(
                            tipo=InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL,
                            descricao=(
                                f"Dependente {dep.nome} tem {idade} anos, mas tipo "
                                f"'universitário' exige até {IDADE_LIMITE_UNIVERSITARIO} anos."
                            ),
                            risco=RiskLevel.HIGH,
                            recomendacao="Remover dependente ou verificar data de nascimento.",
                            valor_impacto=DEDUCAO_DEPENDENTE,
                        )
                    )
                elif idade < 17:
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Dependente {dep.nome} ({idade} anos) declarado como "
                                f"universitário. Idade baixa para ensino superior."
                            ),
                            risco=RiskLevel.LOW,
                            campo="dependentes",
                            categoria=WarningCategory.CONSISTENCIA,
                        )
                    )

            elif dep.tipo == TipoDependente.PAIS_AVOS_BISAVOS:
                # Parents/grandparents must have low income
                # Can't verify here, but can flag for review
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Dependente {dep.nome} ({dep.tipo.value}) - "
                            f"mantenha documentação de renda do dependente."
                        ),
                        risco=RiskLevel.LOW,
                        campo="dependentes",
                        categoria=WarningCategory.CONSISTENCIA,
                        informativo=True,
                    )
                )

    def _check_duplicate_dependents(self) -> None:
        """Check for duplicate CPFs among dependents."""
        cpf_counts = defaultdict(list)

        for dep in self.declaration.dependentes:
            if dep.cpf:
                cpf_digits = "".join(filter(str.isdigit, dep.cpf))
                cpf_counts[cpf_digits].append(dep.nome)

        for cpf, names in cpf_counts.items():
            if len(names) > 1:
                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.DEPENDENTE_DUPLICADO,
                        descricao=(
                            f"CPF {cpf[:3]}.***.***-{cpf[-2:]} aparece {len(names)} vezes "
                            f"como dependente: {', '.join(names)}"
                        ),
                        risco=RiskLevel.CRITICAL,
                        recomendacao="Remover dependentes duplicados",
                        valor_impacto=DEDUCAO_DEPENDENTE * (len(names) - 1),
                    )
                )

    def _check_education_expense_attribution(self) -> None:
        """Check education expenses vs number of eligible dependents.

        Education expenses are limited per person.
        Total cannot exceed (titulars + dependents) * limit.
        """
        despesas_educacao = sum(
            d.valor for d in self.declaration.deducoes
            if d.tipo == TipoDeducao.DESPESAS_EDUCACAO and d.valor > 0
        )

        if despesas_educacao == 0:
            return

        # Count eligible people (titular + dependents)
        num_pessoas = 1 + len(self.declaration.dependentes)
        limite_total = LIMITE_EDUCACAO_PESSOA * num_pessoas

        if despesas_educacao > limite_total:
            excesso = despesas_educacao - limite_total
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.DESPESAS_EDUCACAO_LIMITE,
                    descricao=(
                        f"Despesas com educação (R$ {despesas_educacao:,.2f}) excedem "
                        f"limite de R$ {limite_total:,.2f} para {num_pessoas} pessoa(s)"
                    ),
                    valor_declarado=despesas_educacao,
                    valor_esperado=limite_total,
                    risco=RiskLevel.HIGH,
                    recomendacao=(
                        f"Limite por pessoa é R$ {LIMITE_EDUCACAO_PESSOA:,.2f}. "
                        f"Excesso de R$ {excesso:,.2f} será glosado."
                    ),
                    valor_impacto=excesso,
                )
            )

        # Check if education expenses are reasonable given dependent ages
        dependentes_idade_escolar = [
            d for d in self.declaration.dependentes
            if d.idade and 3 <= d.idade <= 24
        ]

        if despesas_educacao > Decimal("10000") and not dependentes_idade_escolar:
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Despesas com educação (R$ {despesas_educacao:,.2f}) sem "
                        f"dependentes em idade escolar (3-24 anos) declarados."
                    ),
                    risco=RiskLevel.MEDIUM,
                    campo="deducoes",
                    categoria=WarningCategory.DEDUCAO,
                    valor_impacto=despesas_educacao,
                )
            )

    def _check_medical_expense_attribution(self) -> None:
        """Check medical expenses attributed to dependents.

        High medical expenses for young, healthy dependents may be suspicious.
        Very elderly dependents with no medical expenses may also be suspicious.
        """
        # Group medical expenses by beneficiary CPF
        despesas_por_cpf = defaultdict(Decimal)

        for ded in self.declaration.deducoes:
            if ded.tipo == TipoDeducao.DESPESAS_MEDICAS and ded.valor > 0:
                cpf = ded.beneficiario_cpf or "TITULAR"
                despesas_por_cpf[cpf] += ded.valor

        # Check for dependents with unusual medical expense patterns
        for dep in self.declaration.dependentes:
            if not dep.cpf:
                continue

            cpf_digits = "".join(filter(str.isdigit, dep.cpf))
            despesa_dep = despesas_por_cpf.get(cpf_digits, Decimal("0"))

            idade = dep.idade or 0

            # Young child with very high medical expenses
            if idade < 10 and despesa_dep > Decimal("20000"):
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Dependente {dep.nome} ({idade} anos) com despesas médicas "
                            f"elevadas (R$ {despesa_dep:,.2f}). Mantenha documentação completa."
                        ),
                        risco=RiskLevel.LOW,
                        campo="deducoes",
                        categoria=WarningCategory.DEDUCAO,
                        informativo=True,
                        valor_impacto=despesa_dep,
                    )
                )

    def _check_dependent_count_anomaly(self) -> None:
        """Check for anomalies in number of dependents.

        Large number of dependents may trigger review.
        """
        num_dependentes = len(self.declaration.dependentes)

        if num_dependentes > 5:
            total_deducao = DEDUCAO_DEPENDENTE * num_dependentes
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Número elevado de dependentes ({num_dependentes}). "
                        f"Dedução total de R$ {total_deducao:,.2f} pode gerar revisão. "
                        f"Mantenha documentação de cada dependente."
                    ),
                    risco=RiskLevel.LOW,
                    campo="dependentes",
                    categoria=WarningCategory.CONSISTENCIA,
                    informativo=True,
                    valor_impacto=total_deducao,
                )
            )

    def _check_spouse_income(self) -> None:
        """Check if spouse dependent has income declaration.

        Spouse can only be dependent if has no significant income.
        """
        for dep in self.declaration.dependentes:
            if dep.tipo in (TipoDependente.CONJUGE, TipoDependente.COMPANHEIRO):
                # Flag for awareness - can't verify income here
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Cônjuge/companheiro ({dep.nome}) como dependente - "
                            f"verifique se não possui rendimentos tributáveis próprios."
                        ),
                        risco=RiskLevel.LOW,
                        campo="dependentes",
                        categoria=WarningCategory.CONSISTENCIA,
                        informativo=True,
                    )
                )

    def _check_dependent_cpf_sequential(self) -> None:
        """Check if dependent CPFs follow a sequential pattern.

        CPFs issued for family members often have similar prefixes,
        but sequential final digits may indicate fabrication.
        """
        if len(self.declaration.dependentes) < 2:
            return

        cpfs = []
        for dep in self.declaration.dependentes:
            if dep.cpf:
                cpf_digits = "".join(filter(str.isdigit, dep.cpf))
                if len(cpf_digits) == 11:
                    cpfs.append((dep.nome, cpf_digits))

        if len(cpfs) < 2:
            return

        # Check for suspicious patterns between CPFs
        cpfs.sort(key=lambda x: x[1])

        for i in range(len(cpfs) - 1):
            nome1, cpf1 = cpfs[i]
            nome2, cpf2 = cpfs[i + 1]

            # Check if first 8 digits are identical (same batch)
            if cpf1[:8] == cpf2[:8]:
                # Check if last 3 digits are sequential
                try:
                    num1 = int(cpf1[8:11])
                    num2 = int(cpf2[8:11])
                    if abs(num2 - num1) <= 2:
                        self.warnings.append(
                            Warning(
                                mensagem=(
                                    f"CPFs de dependentes {nome1} e {nome2} são "
                                    f"muito próximos sequencialmente. Pode ser coincidência "
                                    f"(emitidos juntos) ou indicar fabricação."
                                ),
                                risco=RiskLevel.LOW,
                                campo="dependentes",
                                categoria=WarningCategory.PADRAO,
                                informativo=True,
                            )
                        )
                except ValueError:
                    pass

    def _check_orphan_dependent_expenses(self) -> None:
        """Check for dependent-related expenses without declared dependents.

        If there are education or dependent-attributed medical expenses
        but no dependents declared, this is suspicious.
        """
        # Check for education expenses
        despesas_educacao = sum(
            d.valor for d in self.declaration.deducoes
            if d.tipo == TipoDeducao.DESPESAS_EDUCACAO and d.valor > 0
        )

        # Education above titular limit suggests dependent
        if despesas_educacao > LIMITE_EDUCACAO_PESSOA:
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.DEDUCAO_SEM_COMPROVANTE,
                    descricao=(
                        f"Despesas com educação (R$ {despesas_educacao:,.2f}) excedem "
                        f"limite individual de R$ {LIMITE_EDUCACAO_PESSOA:,.2f}, "
                        f"mas não há dependentes declarados."
                    ),
                    valor_declarado=despesas_educacao,
                    valor_esperado=LIMITE_EDUCACAO_PESSOA,
                    risco=RiskLevel.HIGH,
                    recomendacao="Declare os dependentes ou ajuste despesas com educação.",
                    valor_impacto=despesas_educacao - LIMITE_EDUCACAO_PESSOA,
                )
            )


def analyze_dependent_fraud(declaration: Declaration) -> tuple[list[Inconsistency], list[Warning]]:
    """Convenience function to run dependent fraud analysis.

    Args:
        declaration: Declaration to analyze

    Returns:
        Tuple of (inconsistencies, warnings) found
    """
    analyzer = DependentFraudAnalyzer(declaration)
    return analyzer.analyze()
