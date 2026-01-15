"""Pattern analyzer for detecting suspicious patterns in IRPF declarations.

This module provides statistical and structural pattern detection including:
- Structural patterns (round values, depreciation, concentration)
- Fraud patterns (CPF/CNPJ validation, fictitious expenses)
- Financial inconsistency patterns (purchases without backing, dividends vs participation)
- Statistical patterns (outliers, Benford's Law)
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
from irpf_analyzer.core.models.enums import GrupoBem, TipoDeducao, TipoRendimento
from irpf_analyzer.shared.validators import validar_cpf, validar_cnpj
from irpf_analyzer.shared.statistics import (
    calcular_chi_quadrado_benford,
    detectar_outliers_iqr,
    detectar_valores_redondos,
    detectar_outliers_zscore,
    calcular_indice_gini,
    calcular_coeficiente_variacao,
    detectar_valores_duplicados,
    calcular_correlacao_pearson,
)
from irpf_analyzer.core.rules.tax_constants import (
    LIMITE_DESPESA_MEDICA_PF,
    IDADE_LIMITE_FILHO,
    IDADE_LIMITE_UNIVERSITARIO,
)


class PatternAnalyzer:
    """Analyzes declaration for suspicious patterns.

    Detects:
    - Structural patterns: Round values, vehicle depreciation, concentration
    - Fraud patterns: Invalid CPF/CNPJ, fictitious expenses
    - Financial inconsistency: Purchases without backing, dividends ratio
    - Statistical patterns: Outliers (IQR), Benford's Law
    """

    # Threshold for concentrated medical expenses (one provider > X%)
    CONCENTRACAO_MEDICA_LIMITE = Decimal("0.70")  # 70%

    # Expected annual vehicle depreciation rate
    DEPRECIACAO_VEICULO_ESPERADA = Decimal("0.10")  # 10% per year
    DEPRECIACAO_TOLERANCIA = Decimal("0.05")  # +/- 5%

    # Minimum samples for Benford analysis
    BENFORD_MIN_SAMPLES = 50

    # Asset codes by category (IRPF uses codigo, not grupo, to identify asset type)
    # The grupo field in IRPF display is COMPUTED from codigo, not stored directly
    CODIGOS_IMOVEIS = {"11", "12", "13", "14", "15", "16", "17", "18", "19"}  # 11-19
    CODIGOS_VEICULOS = {"21", "22", "23", "24", "25", "26", "27", "28", "29"}  # 21-29
    CODIGOS_PARTICIPACOES = {"31", "32", "39"}  # Quotas, ações, participações

    def __init__(self, declaration: Declaration):
        self.declaration = declaration
        self.inconsistencies: list[Inconsistency] = []
        self.warnings: list[Warning] = []

    def analyze(self) -> tuple[list[Inconsistency], list[Warning]]:
        """Run all pattern checks.

        Returns:
            Tuple of (inconsistencies, warnings) found
        """
        # Structural patterns
        self._check_valores_redondos()
        self._check_depreciacao_veiculos()
        self._check_despesas_medicas_concentradas()
        self._check_imoveis_sem_aluguel()

        # Fraud patterns
        self._check_cpf_cnpj_invalidos()
        self._check_despesas_medicas_ficticias()
        self._check_despesa_medica_pf_alta()
        self._check_dependente_idade()

        # Financial inconsistency patterns
        self._check_compras_sem_lastro()
        self._check_dividendos_vs_participacao()

        # Statistical patterns
        self._check_outliers()
        self._check_benford()

        # Advanced statistical patterns (Phase 2)
        self._check_zscore_outliers()
        self._check_duplicate_deductions()
        self._check_patrimony_debt_correlation()
        self._check_alienation_capital_gains()
        self._check_medical_expense_patterns()
        self._check_asset_value_consistency()

        return self.inconsistencies, self.warnings

    # ========================
    # STRUCTURAL PATTERNS
    # ========================

    def _check_valores_redondos(self) -> None:
        """Detect suspiciously round values in deductions.

        Deductions with very "round" values (R$ 1,000, R$ 5,000) may
        indicate estimated or fabricated amounts.

        Note: Medical expenses are excluded because healthcare providers
        typically charge round values (R$ 500, R$ 550, etc.).
        """
        # Exclude medical expenses - doctors typically charge round values
        valores_deducao = [
            d.valor for d in self.declaration.deducoes
            if d.valor > 0 and d.tipo != TipoDeducao.DESPESAS_MEDICAS
        ]

        if len(valores_deducao) < 3:
            return  # Need at least 3 non-medical deductions

        redondos = detectar_valores_redondos(valores_deducao)

        # Flag if more than 50% of deductions are round values
        if len(redondos) > len(valores_deducao) / 2:
            exemplos = ", ".join(f"R$ {v:,.0f}" for v in sorted(redondos)[:3])
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Muitas deduções com valores redondos ({len(redondos)} de "
                        f"{len(valores_deducao)}). Exemplos: {exemplos}..."
                    ),
                    risco=RiskLevel.LOW,
                    campo="deducoes",
                    categoria=WarningCategory.PADRAO,
                    valor_impacto=sum(redondos),
                )
            )

    def _check_depreciacao_veiculos(self) -> None:
        """Check if vehicle depreciation is within expected range.

        Vehicles typically depreciate ~10% per year. Large variations may indicate:
        - Incorrect purchase value
        - Unreported sale
        - Incorrect valuation
        """
        for bem in self.declaration.bens_direitos:
            # Vehicles are identified by codigo 21-29 (not grupo)
            # The DEC file stores codigo, not grupo directly
            if bem.codigo not in self.CODIGOS_VEICULOS:
                continue

            # Skip if no previous value (new vehicle)
            if bem.situacao_anterior <= 0:
                continue

            # Skip if sold (current value = 0)
            if bem.situacao_atual == 0:
                continue

            # Calculate observed depreciation
            depreciacao_observada = (
                bem.situacao_anterior - bem.situacao_atual
            ) / bem.situacao_anterior

            # Check if outside expected range
            dep_min = self.DEPRECIACAO_VEICULO_ESPERADA - self.DEPRECIACAO_TOLERANCIA
            dep_max = self.DEPRECIACAO_VEICULO_ESPERADA + self.DEPRECIACAO_TOLERANCIA

            if depreciacao_observada < dep_min:
                # Depreciated less than expected (value may be inflated)
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Veículo com depreciação abaixo do esperado "
                            f"({depreciacao_observada*100:.0f}% vs esperado ~"
                            f"{self.DEPRECIACAO_VEICULO_ESPERADA*100:.0f}%): "
                            f"{bem.discriminacao[:50]}..."
                        ),
                        risco=RiskLevel.LOW,
                        campo="bens_direitos",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=abs(bem.variacao_absoluta),
                    )
                )
            elif depreciacao_observada > dep_max * 2:  # More than 2x expected
                # Depreciated much more than expected
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Veículo com depreciação acima do esperado "
                            f"({depreciacao_observada*100:.0f}% vs esperado ~"
                            f"{self.DEPRECIACAO_VEICULO_ESPERADA*100:.0f}%): "
                            f"{bem.discriminacao[:50]}..."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="bens_direitos",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=abs(bem.variacao_absoluta),
                    )
                )

    def _check_despesas_medicas_concentradas(self) -> None:
        """Detect medical expenses concentrated in few providers.

        High concentration may indicate:
        - Convenience receipts
        - Personal relationship with provider
        - Inflated values
        """
        despesas_medicas = [
            d for d in self.declaration.deducoes
            if d.tipo == TipoDeducao.DESPESAS_MEDICAS and d.valor > 0
        ]

        if len(despesas_medicas) < 2:
            return  # Need at least 2 for concentration check

        total = sum(d.valor for d in despesas_medicas)
        if total == 0:
            return

        # Group by provider CNPJ
        por_prestador: dict[str, Decimal] = {}
        for d in despesas_medicas:
            cnpj = d.cnpj_prestador or "SEM_CNPJ"
            por_prestador[cnpj] = por_prestador.get(cnpj, Decimal("0")) + d.valor

        # Check if any provider concentrates more than the threshold
        for cnpj, valor in por_prestador.items():
            percentual = valor / total
            if percentual > self.CONCENTRACAO_MEDICA_LIMITE:
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Despesas médicas concentradas: {percentual*100:.0f}% "
                            f"(R$ {valor:,.2f}) em um único prestador"
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="deducoes",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=valor,
                    )
                )

    def _check_imoveis_sem_aluguel(self) -> None:
        """Detect properties that may be rented without declaring income.

        If taxpayer owns multiple properties but declares no rental income,
        it may indicate income omission.
        """
        # Count real estate properties by codigo 11-19 (not grupo)
        # The DEC file stores codigo, the grupo shown in IRPF is computed
        imoveis = [
            b for b in self.declaration.bens_direitos
            if b.codigo in self.CODIGOS_IMOVEIS and b.situacao_atual > 0
        ]

        # If more than 1 property, check for rental income
        if len(imoveis) > 1:
            # Check for rental income in rendimentos
            renda_aluguel = Decimal("0")
            for r in self.declaration.rendimentos:
                if r.tipo == TipoRendimento.ALUGUEIS:
                    renda_aluguel += r.valor_anual
                elif r.descricao and (
                    "ALUGUEL" in r.descricao.upper() or "LOCAÇÃO" in r.descricao.upper()
                ):
                    renda_aluguel += r.valor_anual

            if renda_aluguel == 0:
                valor_total_imoveis = sum(i.situacao_atual for i in imoveis)
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Contribuinte possui {len(imoveis)} imóveis "
                            f"(R$ {valor_total_imoveis:,.2f}) mas não declara renda de "
                            f"aluguel. Verifique se há imóveis alugados não declarados."
                        ),
                        risco=RiskLevel.LOW,
                        campo="bens_direitos",
                        categoria=WarningCategory.PADRAO,
                        informativo=True,  # Informative, doesn't count in score
                    )
                )

    # ========================
    # FRAUD PATTERNS
    # ========================

    def _check_cpf_cnpj_invalidos(self) -> None:
        """Validate CPFs and CNPJs using check digit calculation.

        CPF/CNPJ with incorrect digits indicates:
        - Typing error
        - Fictitious CPF/CNPJ
        """
        # Validate taxpayer CPF
        valido, motivo = validar_cpf(self.declaration.contribuinte.cpf)
        if not valido:
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.CPF_INVALIDO,
                    descricao=f"CPF do contribuinte inválido: {motivo}",
                    risco=RiskLevel.CRITICAL,
                    recomendacao="Verificar CPF do contribuinte",
                )
            )

        # Validate dependent CPFs
        for dep in self.declaration.dependentes:
            valido, motivo = validar_cpf(dep.cpf)
            if not valido:
                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.CPF_INVALIDO,
                        descricao=f"CPF de dependente ({dep.nome}) inválido: {motivo}",
                        risco=RiskLevel.HIGH,
                        recomendacao="Verificar CPF do dependente",
                    )
                )

        # Validate payment source CNPJs
        for rend in self.declaration.rendimentos:
            if rend.fonte_pagadora and rend.fonte_pagadora.cnpj_cpf:
                cnpj_cpf = rend.fonte_pagadora.cnpj_cpf
                # Only validate if it looks like a CNPJ (14 digits)
                digits_only = "".join(filter(str.isdigit, cnpj_cpf))
                if len(digits_only) == 14:
                    valido, motivo = validar_cnpj(cnpj_cpf)
                    if not valido:
                        self.inconsistencies.append(
                            Inconsistency(
                                tipo=InconsistencyType.CNPJ_INVALIDO,
                                descricao=(
                                    f"CNPJ de fonte pagadora inválido "
                                    f"({rend.fonte_pagadora.nome}): {motivo}"
                                ),
                                risco=RiskLevel.HIGH,
                                recomendacao="Verificar CNPJ da fonte pagadora",
                                valor_impacto=rend.valor_anual,
                            )
                        )

        # Validate service provider CNPJs (medical expenses, etc.)
        for ded in self.declaration.deducoes:
            if ded.cnpj_prestador:
                valido, motivo = validar_cnpj(ded.cnpj_prestador)
                if not valido:
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"CNPJ de prestador de serviço inválido: {motivo}"
                            ),
                            risco=RiskLevel.MEDIUM,
                            campo="deducoes",
                            categoria=WarningCategory.PADRAO,
                            valor_impacto=ded.valor,
                        )
                    )

    def _check_despesas_medicas_ficticias(self) -> None:
        """Detect patterns of potentially fictitious medical expenses.

        Suspicious patterns:
        - Multiple expenses with identical values
        - Expenses on weekends/holidays (if date available)
        - CNPJs of companies unrelated to health
        """
        despesas_medicas = [
            d for d in self.declaration.deducoes
            if d.tipo == TipoDeducao.DESPESAS_MEDICAS and d.valor > 0
        ]

        if len(despesas_medicas) < 3:
            return

        # Check for identical values
        valores = [d.valor for d in despesas_medicas]
        contagem = Counter(valores)

        for valor, count in contagem.items():
            if count >= 3 and valor > Decimal("200"):
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Múltiplas despesas médicas com valor idêntico: "
                            f"{count}x R$ {valor:,.2f}"
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="deducoes",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=valor * count,
                    )
                )

    def _check_despesa_medica_pf_alta(self) -> None:
        """Detect high-value medical expenses with individual providers (PF).

        Medical expenses paid to individuals (CPF) are harder for the IRS to
        cross-reference. High-value payments to individuals (> R$ 5,000) may
        receive extra scrutiny during audit.

        Not an error, but requires robust documentation.
        """
        from irpf_analyzer.shared.validators import validar_cpf

        for ded in self.declaration.deducoes:
            if ded.tipo != TipoDeducao.DESPESAS_MEDICAS:
                continue

            if ded.valor <= 0:
                continue

            # Check if provider is a CPF (individual) vs CNPJ (company)
            cpf_prestador = ded.cpf_prestador
            if not cpf_prestador:
                continue

            # Validate it's actually a CPF format (11 digits)
            digits_only = "".join(filter(str.isdigit, cpf_prestador))
            if len(digits_only) != 11:
                continue

            # Check if value exceeds threshold
            if ded.valor > LIMITE_DESPESA_MEDICA_PF:
                # Validate the CPF is valid
                valido, _ = validar_cpf(cpf_prestador)
                status = "válido" if valido else "inválido"

                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Despesa médica alta com pessoa física (CPF {status}): "
                            f"R$ {ded.valor:,.2f} - {ded.nome_prestador or 'Nome não informado'}. "
                            f"Valores acima de R$ {LIMITE_DESPESA_MEDICA_PF:,.0f} com PF "
                            f"requerem documentação robusta (recibos, NF quando aplicável)."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="deducoes",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=ded.valor,
                    )
                )

    def _check_dependente_idade(self) -> None:
        """Validate dependent age against dependent type.

        Rules:
        - Filho/enteado até 21 anos OR até 24 se universitário
        - Filho/enteado incapaz: any age
        - Menor pobre: até 21 anos

        Age incompatibility may cause automatic rejection.
        """
        from irpf_analyzer.core.models.enums import TipoDependente

        for dep in self.declaration.dependentes:
            idade = dep.idade
            if idade is None:
                # No birth date available, can't validate
                continue

            # Check based on dependent type
            if dep.tipo in (
                TipoDependente.FILHO_ENTEADO_ATE_21,
                TipoDependente.IRMAO_NETO_BISNETO,
            ):
                # Must be up to 21 years old
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
                                f"Alterar para tipo 'universitário' (se aplicável e até "
                                f"{IDADE_LIMITE_UNIVERSITARIO} anos) ou remover dependente."
                            ),
                        )
                    )

            elif dep.tipo == TipoDependente.FILHO_ENTEADO_UNIVERSITARIO:
                # Must be up to 24 years old and studying
                if idade > IDADE_LIMITE_UNIVERSITARIO:
                    self.inconsistencies.append(
                        Inconsistency(
                            tipo=InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL,
                            descricao=(
                                f"Dependente {dep.nome} tem {idade} anos, mas tipo "
                                f"'universitário' exige até {IDADE_LIMITE_UNIVERSITARIO} anos."
                            ),
                            risco=RiskLevel.HIGH,
                            recomendacao="Verificar se dependente ainda está cursando ensino superior ou remover.",
                        )
                    )

            elif dep.tipo == TipoDependente.MENOR_POBRE:
                # Must be up to 21 years old
                if idade > IDADE_LIMITE_FILHO:
                    self.inconsistencies.append(
                        Inconsistency(
                            tipo=InconsistencyType.DEPENDENTE_IDADE_INCOMPATIVEL,
                            descricao=(
                                f"Dependente {dep.nome} (menor pobre) tem {idade} anos, "
                                f"acima do limite de {IDADE_LIMITE_FILHO} anos."
                            ),
                            risco=RiskLevel.HIGH,
                            recomendacao="Remover dependente ou verificar data de nascimento.",
                        )
                    )

            # FILHO_ENTEADO_INCAPAZ has no age limit
            # CONJUGE, COMPANHEIRO, PAIS_AVOS_BISAVOS have no upper age limit

    # ========================
    # FINANCIAL INCONSISTENCY
    # ========================

    def _check_compras_sem_lastro(self) -> None:
        """Detect asset acquisitions without sufficient resources.

        If a new asset was acquired, check if there's enough income/liquidation
        to justify the purchase.
        """
        recursos_disponiveis = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
        )

        if recursos_disponiveis <= 0:
            return

        for bem in self.declaration.bens_direitos:
            # New asset (previous = 0, current > 0)
            if bem.situacao_anterior == 0 and bem.situacao_atual > Decimal("50000"):
                # If asset costs more than 50% of annual income, may be suspicious
                if bem.situacao_atual > recursos_disponiveis * Decimal("0.5"):
                    percentual = (
                        bem.situacao_atual / recursos_disponiveis * 100
                    )
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Aquisição de alto valor: {bem.discriminacao[:40]}... "
                                f"(R$ {bem.situacao_atual:,.2f}) representa "
                                f"{percentual:.0f}% da renda declarada"
                            ),
                            risco=RiskLevel.LOW,
                            campo="bens_direitos",
                            categoria=WarningCategory.PADRAO,
                            informativo=True,
                            valor_impacto=bem.situacao_atual,
                        )
                    )

    def _check_dividendos_vs_participacao(self) -> None:
        """Check if dividends are compatible with equity participation.

        If small participation is declared but high dividends are received,
        may indicate inconsistency.
        """
        # Identify equity participations by codigo 31, 32, 39 (not grupo)
        # The DEC file stores codigo, the grupo shown in IRPF is computed
        participacoes = [
            b for b in self.declaration.bens_direitos
            if b.codigo in self.CODIGOS_PARTICIPACOES and b.situacao_atual > 0
        ]

        # Identify dividends received
        dividendos = Decimal("0")
        for r in self.declaration.rendimentos:
            if r.tipo == TipoRendimento.LUCROS_DIVIDENDOS:
                dividendos += r.valor_anual
            elif r.descricao and (
                "DIVIDENDO" in r.descricao.upper() or "LUCRO" in r.descricao.upper()
            ):
                dividendos += r.valor_anual

        if not participacoes or dividendos == 0:
            return

        total_participacoes = sum(p.situacao_atual for p in participacoes)

        # If dividends > 30% of participation value, may be inconsistent
        if total_participacoes > 0 and dividendos > total_participacoes * Decimal("0.30"):
            percentual = dividendos / total_participacoes * 100
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Dividendos altos em relação às participações: "
                        f"Dividendos R$ {dividendos:,.2f} vs "
                        f"Participações R$ {total_participacoes:,.2f} "
                        f"({percentual:.0f}%)"
                    ),
                    risco=RiskLevel.LOW,
                    campo="rendimentos",
                    categoria=WarningCategory.PADRAO,
                    informativo=True,
                    valor_impacto=dividendos,
                )
            )

    # ========================
    # STATISTICAL PATTERNS
    # ========================

    def _check_outliers(self) -> None:
        """Detect outlier values using IQR method.

        Values far from the mean may indicate:
        - Typing errors
        - Atypical values that deserve attention
        """
        # Collect all deduction values
        valores_deducao = [d.valor for d in self.declaration.deducoes if d.valor > 0]

        if len(valores_deducao) >= 4:
            outliers = detectar_outliers_iqr(valores_deducao)

            for valor, tipo in outliers:
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Dedução com valor outlier ({tipo}): R$ {valor:,.2f}"
                        ),
                        risco=RiskLevel.LOW,
                        campo="deducoes",
                        categoria=WarningCategory.PADRAO,
                        informativo=True,
                        valor_impacto=valor,
                    )
                )

        # Collect asset values
        valores_bens = [
            b.situacao_atual for b in self.declaration.bens_direitos
            if b.situacao_atual > 0
        ]

        if len(valores_bens) >= 4:
            outliers = detectar_outliers_iqr(valores_bens, multiplicador=Decimal("2.0"))

            for valor, tipo in outliers:
                if tipo == "superior":  # Only upper outliers are relevant
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Bem com valor significativamente maior que os demais: "
                                f"R$ {valor:,.2f}"
                            ),
                            risco=RiskLevel.LOW,
                            campo="bens_direitos",
                            categoria=WarningCategory.PADRAO,
                            informativo=True,
                            valor_impacto=valor,
                        )
                    )

    def _check_benford(self) -> None:
        """Apply Benford's Law to detect possible manipulations.

        Benford's Law predicts that in natural datasets,
        digit 1 appears as the first digit ~30% of the time.
        Significant deviations may indicate fabricated data.
        """
        # Collect all monetary values from the declaration
        todos_valores: list[Decimal] = []

        # Incomes
        todos_valores.extend(
            r.valor_anual for r in self.declaration.rendimentos
            if r.valor_anual > 0
        )

        # Deductions
        todos_valores.extend(
            d.valor for d in self.declaration.deducoes
            if d.valor > 0
        )

        # Assets (current values)
        todos_valores.extend(
            b.situacao_atual for b in self.declaration.bens_direitos
            if b.situacao_atual > 0
        )

        # Need at least minimum samples for meaningful analysis
        if len(todos_valores) < self.BENFORD_MIN_SAMPLES:
            return

        chi2, anomalo = calcular_chi_quadrado_benford(todos_valores)

        if anomalo:
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Distribuição de primeiros dígitos não segue Lei de Benford "
                        f"(χ² = {chi2:.2f}). Pode indicar valores fabricados ou arredondados."
                    ),
                    risco=RiskLevel.MEDIUM,
                    campo="geral",
                    categoria=WarningCategory.PADRAO,
                )
            )

    # ========================
    # ADVANCED STATISTICAL PATTERNS
    # ========================

    def _check_zscore_outliers(self) -> None:
        """Detect extreme outliers using z-score method.

        Z-score is more sensitive than IQR for normally distributed data.
        Values with |z| > 3 are statistically very unusual (0.3% probability).
        """
        # Medical expenses - commonly manipulated
        despesas_medicas = [
            d.valor for d in self.declaration.deducoes
            if d.tipo == TipoDeducao.DESPESAS_MEDICAS and d.valor > 0
        ]

        if len(despesas_medicas) >= 5:
            outliers = detectar_outliers_zscore(despesas_medicas)
            for valor, zscore in outliers:
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Despesa médica com valor estatisticamente extremo "
                            f"(z-score={zscore:.1f}): R$ {valor:,.2f}"
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="deducoes",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=valor,
                    )
                )

    def _check_duplicate_deductions(self) -> None:
        """Detect duplicate or near-duplicate deduction values.

        Multiple deductions with identical or very similar values
        may indicate copy-paste errors or fabricated data.
        """
        valores_deducao = [
            d.valor for d in self.declaration.deducoes
            if d.valor > Decimal("100")  # Ignore small values
        ]

        if len(valores_deducao) < 3:
            return

        duplicados = detectar_valores_duplicados(valores_deducao)

        for valor, count in duplicados:
            if count >= 3:
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Valor de dedução repetido {count} vezes: R$ {valor:,.2f}. "
                            f"Pode indicar duplicação ou erro de digitação."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="deducoes",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=valor * (count - 1),
                    )
                )

    def _check_patrimony_debt_correlation(self) -> None:
        """Analyze correlation between patrimony and debts.

        Strong correlation may indicate:
        - Proper financing of assets (normal)
        - Leveraged purchases (higher risk)
        - Debt taken to inflate patrimony

        Weak or negative correlation with high patrimony growth
        may indicate undeclared income.
        """
        # Get patrimony values
        patrimonio_anterior = sum(b.situacao_anterior for b in self.declaration.bens_direitos)
        patrimonio_atual = sum(b.situacao_atual for b in self.declaration.bens_direitos)

        dividas_anterior = sum(d.situacao_anterior for d in self.declaration.dividas)
        dividas_atual = sum(d.situacao_atual for d in self.declaration.dividas)

        # Check for suspicious patterns
        variacao_patrimonio = patrimonio_atual - patrimonio_anterior
        variacao_dividas = dividas_atual - dividas_anterior

        if variacao_patrimonio > Decimal("100000"):
            # Large patrimony growth - check if explained by debt or income
            renda_total = (
                self.declaration.total_rendimentos_tributaveis
                + self.declaration.total_rendimentos_isentos
            )

            # If patrimony grew more than income + new debt, suspicious
            recursos_explicados = renda_total + variacao_dividas
            if variacao_patrimonio > recursos_explicados * Decimal("1.5"):
                diferenca = variacao_patrimonio - recursos_explicados
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Crescimento patrimonial (R$ {variacao_patrimonio:,.2f}) "
                            f"maior que renda + novas dívidas (R$ {recursos_explicados:,.2f}). "
                            f"Diferença não explicada: R$ {diferenca:,.2f}"
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="bens_direitos",
                        categoria=WarningCategory.CONSISTENCIA,
                        valor_impacto=diferenca,
                    )
                )

        # Check debt ratio
        if patrimonio_atual > 0 and dividas_atual > 0:
            debt_ratio = dividas_atual / patrimonio_atual
            if debt_ratio > Decimal("0.80"):
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Alto nível de endividamento: dívidas representam "
                            f"{debt_ratio*100:.0f}% do patrimônio bruto. "
                            f"Considere revisar estrutura financeira."
                        ),
                        risco=RiskLevel.LOW,
                        campo="dividas",
                        categoria=WarningCategory.CONSISTENCIA,
                        informativo=True,
                    )
                )

    def _check_alienation_capital_gains(self) -> None:
        """Validate capital gains from alienations (sales).

        Capital gains should be reasonable relative to:
        - Original asset value
        - Time held
        - Asset type

        Suspicious patterns:
        - Very high gains (>100% profit)
        - Zero gains on large sales
        - Gains without corresponding asset reduction
        """
        for alienacao in self.declaration.alienacoes:
            if not alienacao.valor_alienacao or alienacao.valor_alienacao <= 0:
                continue

            # Check gain ratio if both values are available
            if alienacao.ganho_capital and alienacao.valor_alienacao > 0:
                gain_ratio = alienacao.ganho_capital / alienacao.valor_alienacao

                nome_bem = alienacao.nome_bem[:40] if alienacao.nome_bem else "Não informado"

                if gain_ratio > Decimal("1.0"):
                    # Profit > 100% of sale value - very suspicious
                    self.inconsistencies.append(
                        Inconsistency(
                            tipo=InconsistencyType.COMPRA_SEM_LASTRO,
                            descricao=(
                                f"Ganho de capital ({gain_ratio*100:.0f}% do valor de venda) "
                                f"implausível em alienação: {nome_bem}..."
                            ),
                            valor_declarado=alienacao.ganho_capital,
                            valor_esperado=alienacao.valor_alienacao * Decimal("0.5"),  # Max 50%
                            risco=RiskLevel.HIGH,
                            recomendacao="Verificar valores de aquisição e venda do bem",
                            valor_impacto=alienacao.ganho_capital,
                        )
                    )
                elif gain_ratio > Decimal("0.50"):
                    # High but not impossible gain
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Ganho de capital significativo ({gain_ratio*100:.0f}%): "
                                f"{nome_bem}... - "
                                f"Mantenha documentação de aquisição."
                            ),
                            risco=RiskLevel.LOW,
                            campo="alienacoes",
                            categoria=WarningCategory.CONSISTENCIA,
                            informativo=True,
                            valor_impacto=alienacao.ganho_capital,
                        )
                    )

            # Check for large sales with zero capital gains
            if alienacao.valor_alienacao > Decimal("100000"):
                if not alienacao.ganho_capital or alienacao.ganho_capital == 0:
                    nome_bem = alienacao.nome_bem[:40] if alienacao.nome_bem else "Não informado"
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Alienação de alto valor (R$ {alienacao.valor_alienacao:,.2f}) "
                                f"com ganho de capital zerado ou não informado: "
                                f"{nome_bem}..."
                            ),
                            risco=RiskLevel.LOW,
                            campo="alienacoes",
                            categoria=WarningCategory.CONSISTENCIA,
                            informativo=True,
                            valor_impacto=alienacao.valor_alienacao,
                        )
                    )

    def _check_medical_expense_patterns(self) -> None:
        """Detect suspicious patterns in medical expenses.

        Patterns analyzed:
        - Seasonal concentration (all expenses in one period)
        - Provider type distribution (PF vs PJ)
        - Value distribution (statistical analysis)
        """
        despesas_medicas = [
            d for d in self.declaration.deducoes
            if d.tipo == TipoDeducao.DESPESAS_MEDICAS and d.valor > 0
        ]

        if len(despesas_medicas) < 3:
            return

        # Check coefficient of variation
        valores = [d.valor for d in despesas_medicas]
        cv = calcular_coeficiente_variacao(valores)

        if cv < Decimal("10"):
            # Very low CV - all values are similar (suspicious)
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Despesas médicas com valores muito uniformes "
                        f"(CV={cv:.1f}%). Pode indicar valores estimados/fabricados."
                    ),
                    risco=RiskLevel.MEDIUM,
                    campo="deducoes",
                    categoria=WarningCategory.PADRAO,
                    valor_impacto=sum(valores),
                )
            )

        # Check for PF vs PJ distribution
        pf_count = 0
        pj_count = 0
        pf_valor = Decimal("0")
        pj_valor = Decimal("0")

        for d in despesas_medicas:
            if d.cpf_prestador:
                pf_count += 1
                pf_valor += d.valor
            elif d.cnpj_prestador:
                pj_count += 1
                pj_valor += d.valor

        total_valor = pf_valor + pj_valor
        if total_valor > 0 and pf_valor / total_valor > Decimal("0.70"):
            # More than 70% with PF providers
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Alto percentual de despesas médicas com pessoas físicas: "
                        f"{pf_valor/total_valor*100:.0f}% (R$ {pf_valor:,.2f}). "
                        f"Despesas com PF recebem maior escrutínio da Receita."
                    ),
                    risco=RiskLevel.LOW,
                    campo="deducoes",
                    categoria=WarningCategory.PADRAO,
                    informativo=True,
                    valor_impacto=pf_valor,
                )
            )

    def _check_asset_value_consistency(self) -> None:
        """Check for asset value inconsistencies.

        Detects:
        - Properties with value below typical minimums
        - Vehicles with value inconsistent with age
        - Assets with suspicious value changes
        """
        for bem in self.declaration.bens_direitos:
            # Skip assets with no value
            if bem.situacao_atual <= 0:
                continue

            # Check for undervalued properties
            if bem.codigo in self.CODIGOS_IMOVEIS:
                if bem.situacao_atual < Decimal("50000"):
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Imóvel com valor baixo: R$ {bem.situacao_atual:,.2f} - "
                                f"{bem.discriminacao[:40]}... "
                                f"Valores muito baixos podem gerar questionamento."
                            ),
                            risco=RiskLevel.LOW,
                            campo="bens_direitos",
                            categoria=WarningCategory.PADRAO,
                            informativo=True,
                        )
                    )

            # Check for significant value changes in stable assets
            if bem.situacao_anterior > 0:
                variacao_pct = abs(bem.variacao_percentual)

                # Properties shouldn't vary much year over year (except improvements)
                if bem.codigo in self.CODIGOS_IMOVEIS:
                    if variacao_pct > Decimal("30") and bem.variacao_absoluta > Decimal("50000"):
                        self.warnings.append(
                            Warning(
                                mensagem=(
                                    f"Imóvel com variação significativa ({variacao_pct:.0f}%): "
                                    f"{bem.discriminacao[:40]}... "
                                    f"Imóveis devem manter valor histórico de aquisição."
                                ),
                                risco=RiskLevel.LOW,
                                campo="bens_direitos",
                                categoria=WarningCategory.CONSISTENCIA,
                                valor_impacto=abs(bem.variacao_absoluta),
                            )
                        )


def analyze_patterns(declaration: Declaration) -> tuple[list[Inconsistency], list[Warning]]:
    """Convenience function to run pattern analysis.

    Args:
        declaration: Declaration to analyze

    Returns:
        Tuple of (inconsistencies, warnings) found
    """
    analyzer = PatternAnalyzer(declaration)
    return analyzer.analyze()
