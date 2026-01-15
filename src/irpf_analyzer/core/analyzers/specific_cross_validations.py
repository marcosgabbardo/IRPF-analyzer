"""Specific cross-validation analyzer for IRPF declarations.

This module provides specific cross-validation checks including:
- Medical expenses vs taxpayer/dependent age
- Education expenses vs dependent age
- Real estate appreciation vs market indices
- Spouse declaration cross-validation

Based on Brazilian tax audit patterns and reasonable expectations.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import NamedTuple

from irpf_analyzer.core.models.analysis import (
    Inconsistency,
    InconsistencyType,
    RiskLevel,
    Warning,
    WarningCategory,
)
from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import GrupoBem, TipoDeducao


class AgeBasedMedicalThreshold(NamedTuple):
    """Medical expense threshold by age group."""

    min_age: int
    max_age: int
    expected_ratio: Decimal  # Expected ratio of medical expenses to income
    high_ratio: Decimal  # Ratio that triggers warning
    critical_ratio: Decimal  # Ratio that triggers inconsistency


class EducationLevel(NamedTuple):
    """Education level with typical age range."""

    name: str
    min_age: int
    max_age: int
    typical_annual_cost: Decimal


class SpecificCrossValidationAnalyzer:
    """Analyzer for specific cross-validations.

    Checks:
    - Medical expenses appropriate for age
    - Education expenses match dependent ages
    - Real estate appreciation within market norms
    - Consistency between spouse declarations
    """

    # Medical expense thresholds by age group
    # Based on typical health spending patterns in Brazil
    MEDICAL_THRESHOLDS: list[AgeBasedMedicalThreshold] = [
        # Young adults (18-30): typically low medical expenses
        AgeBasedMedicalThreshold(18, 30, Decimal("0.02"), Decimal("0.10"), Decimal("0.20")),
        # Adults (31-45): moderate expenses
        AgeBasedMedicalThreshold(31, 45, Decimal("0.04"), Decimal("0.15"), Decimal("0.25")),
        # Middle-aged (46-60): increasing expenses
        AgeBasedMedicalThreshold(46, 60, Decimal("0.06"), Decimal("0.20"), Decimal("0.35")),
        # Seniors (61-75): high expenses expected
        AgeBasedMedicalThreshold(61, 75, Decimal("0.10"), Decimal("0.30"), Decimal("0.50")),
        # Elderly (76+): very high expenses common
        AgeBasedMedicalThreshold(76, 120, Decimal("0.15"), Decimal("0.40"), Decimal("0.60")),
    ]

    # Education levels with typical age ranges
    EDUCATION_LEVELS: list[EducationLevel] = [
        EducationLevel("Creche", 0, 3, Decimal("15000")),
        EducationLevel("Pré-escola", 4, 5, Decimal("18000")),
        EducationLevel("Fundamental I", 6, 10, Decimal("20000")),
        EducationLevel("Fundamental II", 11, 14, Decimal("22000")),
        EducationLevel("Ensino Médio", 15, 17, Decimal("25000")),
        EducationLevel("Ensino Superior", 18, 30, Decimal("30000")),
        EducationLevel("Pós-graduação", 22, 60, Decimal("35000")),
    ]

    # Maximum real estate appreciation without improvements (annual)
    # Based on FIPEZAP index average + margin
    MAX_REAL_ESTATE_APPRECIATION = Decimal("0.15")  # 15% per year

    # Minimum value for real estate analysis
    MIN_REAL_ESTATE_VALUE = Decimal("100000")

    def __init__(
        self,
        declaration: Declaration,
        spouse_declaration: Declaration | None = None,
    ) -> None:
        """Initialize analyzer with declaration data.

        Args:
            declaration: The IRPF declaration to analyze
            spouse_declaration: Optional spouse declaration for cross-validation
        """
        self.declaration = declaration
        self.spouse_declaration = spouse_declaration
        self.inconsistencies: list[Inconsistency] = []
        self.warnings: list[Warning] = []

        # Calculate taxpayer age
        self._taxpayer_age = self._calculate_taxpayer_age()
        self._renda_tributavel = declaration.total_rendimentos_tributaveis

    def analyze(self) -> tuple[list[Inconsistency], list[Warning]]:
        """Run all specific cross-validation checks.

        Returns:
            Tuple of (inconsistencies, warnings) found during analysis
        """
        self._validate_medical_expenses_vs_age()
        self._validate_education_vs_dependent_age()
        self._validate_real_estate_appreciation()

        if self.spouse_declaration:
            self._validate_spouse_consistency()

        return self.inconsistencies, self.warnings

    def _calculate_taxpayer_age(self) -> int | None:
        """Calculate taxpayer's age from declaration."""
        if self.declaration.contribuinte.data_nascimento:
            today = date.today()
            birth = self.declaration.contribuinte.data_nascimento
            age = today.year - birth.year
            if (today.month, today.day) < (birth.month, birth.day):
                age -= 1
            return age
        return None

    def _validate_medical_expenses_vs_age(self) -> None:
        """Validate medical expenses are appropriate for taxpayer age.

        Young taxpayers with very high medical expenses may indicate:
        - Fabricated deductions
        - Expenses that belong to someone else
        - Legitimate chronic conditions (should be documented)
        """
        if self._taxpayer_age is None or self._renda_tributavel <= 0:
            return

        # Get total medical expenses
        total_medical = self.declaration.resumo_deducoes.despesas_medicas

        if total_medical <= 0:
            return

        # Calculate ratio
        medical_ratio = total_medical / self._renda_tributavel

        # Find applicable threshold
        threshold = self._get_medical_threshold(self._taxpayer_age)

        if threshold is None:
            return

        # Check against thresholds
        if medical_ratio >= threshold.critical_ratio:
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.DESPESAS_MEDICAS_ALTAS,
                    descricao=(
                        f"Despesas médicas extremamente altas para a faixa etária. "
                        f"Contribuinte com {self._taxpayer_age} anos declara "
                        f"R$ {total_medical:,.2f} ({medical_ratio*100:.1f}% da renda). "
                        f"Para essa faixa etária, o esperado é até {threshold.critical_ratio*100:.0f}%."
                    ),
                    valor_declarado=total_medical,
                    valor_esperado=self._renda_tributavel * threshold.expected_ratio,
                    risco=RiskLevel.HIGH,
                    recomendacao=(
                        "Mantenha todos os recibos e notas fiscais. "
                        "Se houver condição crônica, documente com laudos médicos."
                    ),
                    valor_impacto=total_medical,
                )
            )
        elif medical_ratio >= threshold.high_ratio:
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Despesas médicas acima do esperado para a idade. "
                        f"Contribuinte com {self._taxpayer_age} anos declara "
                        f"R$ {total_medical:,.2f} ({medical_ratio*100:.1f}% da renda). "
                        f"Esperado para essa faixa: até {threshold.high_ratio*100:.0f}%."
                    ),
                    risco=RiskLevel.MEDIUM,
                    campo="deducoes",
                    categoria=WarningCategory.CONSISTENCIA,
                    valor_impacto=total_medical - (self._renda_tributavel * threshold.expected_ratio),
                )
            )

    def _get_medical_threshold(self, age: int) -> AgeBasedMedicalThreshold | None:
        """Get medical expense threshold for a given age."""
        for threshold in self.MEDICAL_THRESHOLDS:
            if threshold.min_age <= age <= threshold.max_age:
                return threshold
        return None

    def _validate_education_vs_dependent_age(self) -> None:
        """Validate education expenses match dependent ages.

        Detects:
        - University expenses for young children
        - Elementary school expenses for adults
        - Education expenses without appropriate-aged dependents
        """
        # Get education deductions by beneficiary
        education_by_beneficiary: dict[str, Decimal] = defaultdict(Decimal)

        for deducao in self.declaration.deducoes:
            if deducao.tipo == TipoDeducao.DESPESAS_EDUCACAO:
                cpf = deducao.beneficiario_cpf or "TITULAR"
                education_by_beneficiary[cpf] += deducao.valor

        if not education_by_beneficiary:
            return

        # Build map of dependent ages
        dependent_ages: dict[str, int | None] = {}
        for dep in self.declaration.dependentes:
            dependent_ages[dep.cpf] = dep.idade

        # Check each education expense
        for cpf, valor in education_by_beneficiary.items():
            if cpf == "TITULAR":
                # Titular education - check taxpayer age for reasonableness
                if self._taxpayer_age and self._taxpayer_age < 16:
                    self.inconsistencies.append(
                        Inconsistency(
                            tipo=InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL,
                            descricao=(
                                f"Despesa de educação do titular (R$ {valor:,.2f}) "
                                f"mas contribuinte tem apenas {self._taxpayer_age} anos."
                            ),
                            valor_declarado=valor,
                            risco=RiskLevel.HIGH,
                            recomendacao="Verifique se a despesa está corretamente atribuída.",
                        )
                    )
                continue

            # Check if dependent exists and get age
            age = dependent_ages.get(cpf)

            if cpf not in dependent_ages:
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Despesa de educação de R$ {valor:,.2f} "
                            f"para CPF {cpf[:3]}.***.***-{cpf[-2:]} "
                            f"que não consta como dependente."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="deducoes",
                        categoria=WarningCategory.CONSISTENCIA,
                        valor_impacto=valor,
                    )
                )
                continue

            if age is None:
                continue

            # Validate expense amount vs age
            appropriate_levels = [
                level for level in self.EDUCATION_LEVELS
                if level.min_age <= age <= level.max_age
            ]

            if not appropriate_levels:
                # No appropriate education level for this age
                if age < 0:
                    continue  # Invalid age

                if age > 60:
                    # Very old dependent with education expenses
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Despesa de educação de R$ {valor:,.2f} "
                                f"para dependente com {age} anos. "
                                f"Verifique se é pós-graduação ou curso livre."
                            ),
                            risco=RiskLevel.LOW,
                            campo="deducoes",
                            categoria=WarningCategory.CONSISTENCIA,
                            informativo=True,
                        )
                    )

            # Check for age/expense mismatch
            if age <= 5 and valor > Decimal("25000"):
                # Young child with high education expenses
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Despesa de educação elevada (R$ {valor:,.2f}) "
                            f"para dependente de {age} anos. "
                            f"Verifique se o valor está correto."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="deducoes",
                        categoria=WarningCategory.CONSISTENCIA,
                        valor_impacto=valor,
                    )
                )

            # Check for university expenses for children
            if age < 16 and valor > Decimal("30000"):
                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL,
                        descricao=(
                            f"Despesa de educação de R$ {valor:,.2f} "
                            f"para dependente de apenas {age} anos. "
                            f"Valor é típico de ensino superior."
                        ),
                        valor_declarado=valor,
                        risco=RiskLevel.MEDIUM,
                        recomendacao=(
                            "Verifique se a despesa está atribuída ao dependente correto. "
                            "Limite de educação é R$ 3.561,50/pessoa."
                        ),
                    )
                )

    def _validate_real_estate_appreciation(self) -> None:
        """Validate real estate appreciation is within market norms.

        Real estate cannot appreciate significantly without:
        - Renovations/improvements (added to cost basis)
        - Market valuation (documented)
        - New construction on land

        High appreciation without explanation may indicate:
        - Attempt to increase cost basis
        - Money laundering
        - Simple error in declaration
        """
        for bem in self.declaration.bens_direitos:
            if bem.grupo != GrupoBem.IMOVEIS:
                continue

            if bem.situacao_anterior < self.MIN_REAL_ESTATE_VALUE:
                continue

            if bem.situacao_atual <= bem.situacao_anterior:
                continue  # No appreciation

            # Calculate appreciation
            appreciation = (
                (bem.situacao_atual - bem.situacao_anterior) / bem.situacao_anterior
            )

            if appreciation > self.MAX_REAL_ESTATE_APPRECIATION:
                appreciation_pct = appreciation * 100

                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.IMOVEL_SUBAVALIADO,
                        descricao=(
                            f"Valorização atípica de imóvel: {appreciation_pct:.1f}% no ano. "
                            f"'{bem.discriminacao[:40]}...' "
                            f"de R$ {bem.situacao_anterior:,.2f} para R$ {bem.situacao_atual:,.2f}. "
                            f"Máximo esperado sem benfeitorias: {self.MAX_REAL_ESTATE_APPRECIATION*100:.0f}%."
                        ),
                        valor_declarado=bem.situacao_atual,
                        valor_esperado=bem.situacao_anterior * (1 + self.MAX_REAL_ESTATE_APPRECIATION),
                        risco=RiskLevel.HIGH,
                        recomendacao=(
                            "Imóveis devem ser declarados pelo custo de aquisição. "
                            "Apenas benfeitorias documentadas podem ser adicionadas. "
                            "Guarde notas fiscais de reformas e melhorias."
                        ),
                        valor_impacto=bem.situacao_atual - bem.situacao_anterior,
                    )
                )
            elif appreciation > Decimal("0.08"):  # 8% warning threshold
                appreciation_pct = appreciation * 100

                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Valorização de imóvel acima da inflação: {appreciation_pct:.1f}%. "
                            f"'{bem.discriminacao[:30]}...' "
                            f"Certifique-se de ter documentação de benfeitorias."
                        ),
                        risco=RiskLevel.LOW,
                        campo="bens_direitos",
                        categoria=WarningCategory.CONSISTENCIA,
                        valor_impacto=bem.situacao_atual - bem.situacao_anterior,
                    )
                )

    def _validate_spouse_consistency(self) -> None:
        """Validate consistency between spouse declarations.

        Checks:
        - Same dependents declared by both (should match)
        - Shared assets declared consistently
        - No duplicate deductions
        """
        if not self.spouse_declaration:
            return

        # Check dependent overlap
        taxpayer_deps = {d.cpf for d in self.declaration.dependentes}
        spouse_deps = {d.cpf for d in self.spouse_declaration.dependentes}

        duplicates = taxpayer_deps & spouse_deps

        if duplicates:
            for cpf in duplicates:
                # Find dependent names
                dep_name = None
                for d in self.declaration.dependentes:
                    if d.cpf == cpf:
                        dep_name = d.nome
                        break

                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.DEPENDENTE_DUPLICADO,
                        descricao=(
                            f"Dependente '{dep_name or cpf}' declarado por ambos os cônjuges. "
                            f"Cada dependente só pode ser declarado por um contribuinte."
                        ),
                        risco=RiskLevel.HIGH,
                        recomendacao=(
                            "Remova o dependente de uma das declarações. "
                            "Analise em qual declaração a dedução é mais vantajosa."
                        ),
                    )
                )

        # Check for duplicate medical expense providers
        taxpayer_providers: set[str] = set()
        for d in self.declaration.deducoes:
            if d.tipo == TipoDeducao.DESPESAS_MEDICAS:
                if d.cnpj_prestador:
                    taxpayer_providers.add(d.cnpj_prestador)
                if d.cpf_prestador:
                    taxpayer_providers.add(d.cpf_prestador)

        spouse_providers: set[str] = set()
        for d in self.spouse_declaration.deducoes:
            if d.tipo == TipoDeducao.DESPESAS_MEDICAS:
                if d.cnpj_prestador:
                    spouse_providers.add(d.cnpj_prestador)
                if d.cpf_prestador:
                    spouse_providers.add(d.cpf_prestador)

        common_providers = taxpayer_providers & spouse_providers

        if common_providers:
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Encontrados {len(common_providers)} prestadores de saúde "
                        f"em comum entre as declarações do casal. "
                        f"Verifique se não há despesas duplicadas."
                    ),
                    risco=RiskLevel.MEDIUM,
                    campo="deducoes",
                    categoria=WarningCategory.CONSISTENCIA,
                )
            )

        # Check for shared real estate with different values
        taxpayer_properties: dict[str, Decimal] = {}
        for bem in self.declaration.bens_direitos:
            if bem.grupo == GrupoBem.IMOVEIS:
                key = bem.discriminacao.lower()[:30]
                taxpayer_properties[key] = bem.situacao_atual

        spouse_properties: dict[str, Decimal] = {}
        for bem in self.spouse_declaration.bens_direitos:
            if bem.grupo == GrupoBem.IMOVEIS:
                key = bem.discriminacao.lower()[:30]
                spouse_properties[key] = bem.situacao_atual

        # Check for similar property descriptions with different values
        for key, value in taxpayer_properties.items():
            if key in spouse_properties:
                spouse_value = spouse_properties[key]
                if value != spouse_value:
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Imóvel '{key}...' declarado com valores diferentes: "
                                f"R$ {value:,.2f} vs R$ {spouse_value:,.2f}. "
                                f"Verifique se os valores estão corretos."
                            ),
                            risco=RiskLevel.MEDIUM,
                            campo="bens_direitos",
                            categoria=WarningCategory.CONSISTENCIA,
                        )
                    )


def analyze_specific_cross_validations(
    declaration: Declaration,
    spouse_declaration: Declaration | None = None,
) -> tuple[list[Inconsistency], list[Warning]]:
    """Convenience function to run specific cross-validation analysis.

    Args:
        declaration: The IRPF declaration to analyze
        spouse_declaration: Optional spouse declaration for cross-validation

    Returns:
        Tuple of (inconsistencies, warnings) found
    """
    analyzer = SpecificCrossValidationAnalyzer(declaration, spouse_declaration)
    return analyzer.analyze()
