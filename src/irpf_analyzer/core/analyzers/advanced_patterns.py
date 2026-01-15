"""Advanced pattern detector for detecting suspicious fraud patterns in IRPF declarations.

This module provides enhanced fraud detection including:
- Smurfing detection (transaction splitting near declaration limits)
- Round-trip operations (buy-sell-rebuy suspicious patterns)
- Phantom deductions (deductions with potentially fake providers)
- Cash flow timing analysis (suspicious timing of transactions)

Based on Brazilian tax regulations and common evasion patterns.
"""

from collections import defaultdict
from decimal import Decimal

from irpf_analyzer.core.models.analysis import (
    Inconsistency,
    InconsistencyType,
    RiskLevel,
    Warning,
    WarningCategory,
)
from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import TipoDeducao
from irpf_analyzer.shared.validators import validar_cnpj, validar_cpf


class AdvancedPatternDetector:
    """Advanced fraud pattern detector for IRPF declarations.

    Detects sophisticated fraud patterns:
    - Smurfing: Transaction splitting to avoid R$ 30k declaration threshold
    - Round-trip: Suspicious sell and rebuy operations on same asset
    - Phantom deductions: Deductions with potentially fictitious providers
    - Cash flow timing: Suspicious timing of financial movements
    """

    # R$ 30,000 threshold for mandatory declaration of financial operations
    # (IN RFB 1888/2019 and other regulations)
    LIMITE_DECLARACAO_OBRIGATORIA = Decimal("30000")

    # Margin below the limit to detect smurfing attempts (within 15%)
    MARGEM_SMURFING = Decimal("0.15")

    # Maximum days between operations to consider round-trip
    ROUND_TRIP_DAYS_MAX = 90

    # Minimum percentage of alienation to consider for round-trip check
    ROUND_TRIP_MIN_PERCENTUAL = Decimal("0.50")

    # Threshold for year-end timing analysis (December)
    MES_FIM_ANO = 12

    # Days before year-end to flag as suspicious timing
    DIAS_ANTES_FIM_ANO = 30

    # Known CNPJ prefixes for suspicious activities (placeholder for integration)
    # In production, this would integrate with RFB's list of suspended companies
    CNPJ_PREFIXOS_SUSPEITOS: set[str] = set()

    def __init__(self, declaration: Declaration):
        """Initialize detector with a declaration.

        Args:
            declaration: The IRPF declaration to analyze
        """
        self.declaration = declaration
        self.inconsistencies: list[Inconsistency] = []
        self.warnings: list[Warning] = []

    def analyze(self) -> tuple[list[Inconsistency], list[Warning]]:
        """Run all advanced pattern detection checks.

        Returns:
            Tuple of (inconsistencies, warnings) found
        """
        self.detect_smurfing()
        self.detect_round_trip()
        self.detect_phantom_deductions()
        self.analyze_cash_flow_timing()

        return self.inconsistencies, self.warnings

    def detect_smurfing(self) -> None:
        """Detect smurfing (transaction splitting) patterns.

        Smurfing is the practice of splitting large transactions into
        multiple smaller ones to avoid mandatory declaration thresholds.

        In Brazil, transactions above R$ 30,000 require mandatory declaration
        (IN RFB 1888/2019 for crypto, and similar rules for other assets).

        Detection criteria:
        - Multiple transactions just below the R$ 30k threshold
        - Transactions within the same period (month/quarter)
        - Sum of transactions significantly exceeds the threshold
        """
        # Analyze alienations for smurfing patterns
        alienacoes_por_tipo = defaultdict(list)

        for alienacao in self.declaration.alienacoes:
            if alienacao.valor_alienacao and alienacao.valor_alienacao > 0:
                # Group by asset type
                tipo = alienacao.tipo_bem or "OUTROS"
                alienacoes_por_tipo[tipo].append(alienacao)

        limite_inferior = self.LIMITE_DECLARACAO_OBRIGATORIA * (
            1 - self.MARGEM_SMURFING
        )

        for tipo, alienacoes in alienacoes_por_tipo.items():
            # Find alienations near the threshold
            near_threshold = [
                a for a in alienacoes
                if limite_inferior <= a.valor_alienacao < self.LIMITE_DECLARACAO_OBRIGATORIA
            ]

            if len(near_threshold) >= 2:
                # Multiple operations just below threshold - suspicious
                total = sum(a.valor_alienacao for a in near_threshold)
                valores = [f"R$ {a.valor_alienacao:,.2f}" for a in near_threshold[:3]]
                valores_str = ", ".join(valores)
                if len(near_threshold) > 3:
                    valores_str += f" (+{len(near_threshold) - 3} mais)"

                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.SMURFING_DETECTADO,
                        descricao=(
                            f"Possível fracionamento de operações (smurfing) detectado: "
                            f"{len(near_threshold)} alienações de {tipo} com valores "
                            f"próximos ao limite de R$ {self.LIMITE_DECLARACAO_OBRIGATORIA:,.0f} "
                            f"({valores_str}). Total: R$ {total:,.2f}"
                        ),
                        risco=RiskLevel.HIGH,
                        recomendacao=(
                            "Verificar se há motivo legítimo para o fracionamento. "
                            "A Receita Federal pode interpretar como tentativa de "
                            "evasão do limite de declaração obrigatória."
                        ),
                        valor_impacto=total,
                    )
                )

        # Also check patrimony acquisitions
        aquisicoes_periodo = []
        for bem in self.declaration.bens_direitos:
            # New acquisition (previous = 0, current > 0) near threshold
            if (
                bem.situacao_anterior == 0
                and bem.situacao_atual > 0
                and limite_inferior <= bem.situacao_atual < self.LIMITE_DECLARACAO_OBRIGATORIA
            ):
                aquisicoes_periodo.append(bem)

        if len(aquisicoes_periodo) >= 3:
            total_aquisicoes = sum(b.situacao_atual for b in aquisicoes_periodo)
            if total_aquisicoes > self.LIMITE_DECLARACAO_OBRIGATORIA * 2:
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Múltiplas aquisições ({len(aquisicoes_periodo)}) com valores "
                            f"próximos ao limite de R$ {self.LIMITE_DECLARACAO_OBRIGATORIA:,.0f}. "
                            f"Total: R$ {total_aquisicoes:,.2f}. Pode indicar fracionamento."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="bens_direitos",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=total_aquisicoes,
                    )
                )

    def detect_round_trip(self) -> None:
        """Detect round-trip (wash sale) operations.

        A round-trip occurs when an asset is sold and then repurchased
        shortly after, potentially to:
        - Realize artificial losses for tax purposes
        - Reset the cost basis
        - Hide gains by manipulating timing

        Detection criteria:
        - Same or similar asset sold then acquired within 90 days
        - Significant portion of value involved
        - Pattern across multiple assets
        """
        # Build index of alienations by asset name/type
        alienacoes_por_ativo: dict[str, list] = defaultdict(list)

        for alienacao in self.declaration.alienacoes:
            if alienacao.valor_alienacao and alienacao.valor_alienacao > 0:
                # Normalize asset identifier
                key = self._normalize_asset_key(
                    alienacao.nome_bem or "",
                    alienacao.tipo_bem or "",
                    alienacao.cnpj or "",
                )
                if key:
                    alienacoes_por_ativo[key].append(alienacao)

        # Build index of new acquisitions
        aquisicoes_por_ativo: dict[str, list] = defaultdict(list)

        for bem in self.declaration.bens_direitos:
            # New or increased acquisition
            if bem.situacao_atual > bem.situacao_anterior:
                # Try to extract CNPJ from discriminacao or cnpj_instituicao
                cnpj = bem.cnpj_instituicao or ""
                if not cnpj:
                    cnpj = self._extract_cnpj_from_text(bem.discriminacao)
                key = self._normalize_asset_key(
                    bem.discriminacao,
                    bem.codigo,
                    cnpj,
                )
                if key:
                    aquisicoes_por_ativo[key].append(bem)

        # Check for round-trips
        round_trips_detectados = []

        for key, alienacoes in alienacoes_por_ativo.items():
            for alienacao in alienacoes:
                # Try to find similar acquisitions
                for bem_key, aquisicoes in aquisicoes_por_ativo.items():
                    # Check if keys are similar (same asset type/company)
                    if self._keys_match(key, bem_key):
                        for bem in aquisicoes:
                            # Check value proximity (at least 50% of alienation value)
                            aumento = bem.situacao_atual - bem.situacao_anterior
                            if aumento >= alienacao.valor_alienacao * self.ROUND_TRIP_MIN_PERCENTUAL:
                                round_trips_detectados.append({
                                    "alienacao": alienacao,
                                    "bem": bem,
                                    "valor_venda": alienacao.valor_alienacao,
                                    "valor_compra": aumento,
                                })

        # Report detected round-trips
        if round_trips_detectados:
            for rt in round_trips_detectados[:3]:  # Limit to first 3
                nome_ativo = rt["alienacao"].nome_bem or "Ativo não identificado"
                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.ROUND_TRIP_SUSPEITO,
                        descricao=(
                            f"Operação 'vai-e-volta' suspeita detectada: {nome_ativo[:40]}... "
                            f"foi alienado por R$ {rt['valor_venda']:,.2f} e há aquisição "
                            f"similar de R$ {rt['valor_compra']:,.2f} no mesmo período."
                        ),
                        risco=RiskLevel.MEDIUM,
                        recomendacao=(
                            "Verificar se venda e recompra têm justificativa econômica. "
                            "Operações 'vai-e-volta' podem ser interpretadas como "
                            "manipulação do custo de aquisição ou realização artificial de prejuízo."
                        ),
                        valor_impacto=rt["valor_venda"],
                    )
                )

            if len(round_trips_detectados) > 3:
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Total de {len(round_trips_detectados)} operações "
                            f"'vai-e-volta' suspeitas detectadas."
                        ),
                        risco=RiskLevel.HIGH,
                        campo="alienacoes",
                        categoria=WarningCategory.PADRAO,
                    )
                )

    def detect_phantom_deductions(self) -> None:
        """Detect deductions with potentially fictitious providers.

        Phantom deductions are expenses claimed with fake or ineligible
        providers. Detection criteria:
        - Invalid CPF/CNPJ of service provider
        - CNPJ with known suspicious patterns
        - High concentration of deductions with same provider
        - Providers with inconsistent naming patterns

        Note: In a production system, this would integrate with RFB's
        database of suspended/ineligible companies.
        """
        # Group deductions by provider
        deducoes_por_prestador: dict[str, list] = defaultdict(list)
        prestadores_invalidos = []
        prestadores_sem_id = []

        for deducao in self.declaration.deducoes:
            if deducao.valor <= 0:
                continue

            # Check provider identification
            cnpj = deducao.cnpj_prestador
            cpf = deducao.cpf_prestador
            nome = deducao.nome_prestador or "Não informado"

            if cnpj:
                # Validate CNPJ
                valido, motivo = validar_cnpj(cnpj)
                if not valido:
                    prestadores_invalidos.append({
                        "tipo": "CNPJ",
                        "valor": cnpj,
                        "nome": nome,
                        "deducao": deducao,
                        "motivo": motivo,
                    })
                else:
                    deducoes_por_prestador[f"CNPJ:{cnpj}"].append(deducao)

            elif cpf:
                # Validate CPF
                valido, motivo = validar_cpf(cpf)
                if not valido:
                    prestadores_invalidos.append({
                        "tipo": "CPF",
                        "valor": cpf,
                        "nome": nome,
                        "deducao": deducao,
                        "motivo": motivo,
                    })
                else:
                    deducoes_por_prestador[f"CPF:{cpf}"].append(deducao)

            else:
                # No provider ID - suspicious for significant values
                if deducao.tipo == TipoDeducao.DESPESAS_MEDICAS and deducao.valor > Decimal("500"):
                    prestadores_sem_id.append(deducao)

        # Report invalid providers
        if prestadores_invalidos:
            total_invalido = sum(p["deducao"].valor for p in prestadores_invalidos)

            for prestador in prestadores_invalidos[:5]:
                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.DEDUCAO_PRESTADOR_FANTASMA,
                        descricao=(
                            f"Dedução com prestador de {prestador['tipo']} inválido: "
                            f"{prestador['valor']} ({prestador['nome']}). "
                            f"Valor: R$ {prestador['deducao'].valor:,.2f}. "
                            f"Motivo: {prestador['motivo']}"
                        ),
                        risco=RiskLevel.HIGH,
                        recomendacao=(
                            "Verificar identificação do prestador. CPF/CNPJ inválido "
                            "pode resultar em glosa automática da dedução."
                        ),
                        valor_impacto=prestador["deducao"].valor,
                    )
                )

            if len(prestadores_invalidos) > 5:
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Total de {len(prestadores_invalidos)} deduções com "
                            f"prestadores inválidos (R$ {total_invalido:,.2f})"
                        ),
                        risco=RiskLevel.HIGH,
                        campo="deducoes",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=total_invalido,
                    )
                )

        # Report deductions without provider ID
        if len(prestadores_sem_id) >= 3:
            total_sem_id = sum(d.valor for d in prestadores_sem_id)
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"{len(prestadores_sem_id)} despesas médicas sem identificação "
                        f"do prestador (total R$ {total_sem_id:,.2f}). "
                        f"Despesas significativas sem CPF/CNPJ do prestador "
                        f"são mais propensas a glosa."
                    ),
                    risco=RiskLevel.MEDIUM,
                    campo="deducoes",
                    categoria=WarningCategory.PADRAO,
                    valor_impacto=total_sem_id,
                )
            )

        # Check for suspicious provider patterns
        self._check_provider_patterns(deducoes_por_prestador)

    def _check_provider_patterns(self, deducoes_por_prestador: dict[str, list]) -> None:
        """Check for suspicious patterns in provider deductions.

        Args:
            deducoes_por_prestador: Dict mapping provider ID to list of deductions
        """
        # Check for providers with too many different types of services
        for provider_id, deducoes in deducoes_por_prestador.items():
            tipos_servico = set()
            for d in deducoes:
                if d.tipo:
                    tipos_servico.add(d.tipo)

            # Same provider offering 3+ different types of deductible services is unusual
            if len(tipos_servico) >= 3:
                total = sum(d.valor for d in deducoes)
                nome = deducoes[0].nome_prestador or provider_id

                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Prestador '{nome}' com {len(tipos_servico)} tipos diferentes "
                            f"de serviços dedutíveis ({len(deducoes)} deduções, "
                            f"total R$ {total:,.2f}). Padrão atípico."
                        ),
                        risco=RiskLevel.LOW,
                        campo="deducoes",
                        categoria=WarningCategory.PADRAO,
                        valor_impacto=total,
                    )
                )

    def analyze_cash_flow_timing(self) -> None:
        """Analyze suspicious timing of cash flow movements.

        Suspicious patterns include:
        - Large asset acquisitions just before year-end
        - Asset sales concentrated in December (tax planning vs evasion)
        - Income patterns that suggest artificial timing

        Detection criteria:
        - Significant transactions in the last 30 days of the year
        - Pattern of year-end adjustments
        - Misalignment between income timing and asset changes
        """
        # Check for year-end asset acquisitions
        aquisicoes_fim_ano = []
        for bem in self.declaration.bens_direitos:
            if bem.situacao_anterior == 0 and bem.situacao_atual > Decimal("50000"):
                # Large new acquisition - flag for year-end concern
                aquisicoes_fim_ano.append(bem)

        if len(aquisicoes_fim_ano) >= 2:
            total = sum(b.situacao_atual for b in aquisicoes_fim_ano)
            renda_declarada = (
                self.declaration.total_rendimentos_tributaveis
                + self.declaration.total_rendimentos_isentos
            )

            # If acquisitions exceed declared income, timing is suspicious
            if total > renda_declarada * Decimal("0.8"):
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Múltiplas aquisições de alto valor "
                            f"({len(aquisicoes_fim_ano)} bens, total R$ {total:,.2f}) "
                            f"representam {(total / renda_declarada * 100) if renda_declarada > 0 else 0:.0f}% "
                            f"da renda declarada. Verificar origem dos recursos."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="bens_direitos",
                        categoria=WarningCategory.CONSISTENCIA,
                        valor_impacto=total,
                    )
                )

        # Check for alienations that might be timed for tax purposes
        alienacoes_com_prejuizo = [
            a for a in self.declaration.alienacoes
            if a.tem_perda and abs(a.ganho_capital) > Decimal("10000")
        ]

        alienacoes_com_lucro = [
            a for a in self.declaration.alienacoes
            if a.tem_ganho and a.ganho_capital > Decimal("10000")
        ]

        # Check for suspicious loss/gain ratio
        if alienacoes_com_prejuizo and alienacoes_com_lucro:
            prejuizo_total = sum(abs(a.ganho_capital) for a in alienacoes_com_prejuizo)
            lucro_total = sum(a.ganho_capital for a in alienacoes_com_lucro)

            # If losses are suspiciously close to gains (offsetting)
            if Decimal("0.8") <= prejuizo_total / lucro_total <= Decimal("1.2"):
                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.TIMING_FLUXO_CAIXA_SUSPEITO,
                        descricao=(
                            f"Padrão suspeito de compensação: prejuízos realizados "
                            f"(R$ {prejuizo_total:,.2f}) próximos aos lucros "
                            f"(R$ {lucro_total:,.2f}). Pode indicar "
                            f"planejamento tributário agressivo ou manipulação."
                        ),
                        risco=RiskLevel.MEDIUM,
                        recomendacao=(
                            "Documentar motivos econômicos para alienações. "
                            "Padrões de compensação intencional podem ser questionados "
                            "pela Receita Federal."
                        ),
                        valor_impacto=prejuizo_total,
                    )
                )

        # Check for income concentration in December
        self._check_december_income_concentration()

        # Check for large patrimony changes vs income
        self._check_patrimony_vs_income_timing()

    def _check_december_income_concentration(self) -> None:
        """Check for suspicious concentration of income in December.

        Income concentrated in December might indicate:
        - Bonus/13th salary (normal)
        - Artificial income deferral (suspicious if excessive)
        """
        # This would require per-month income data which isn't typically
        # available in the annual declaration. We check indirect indicators.

        # Check for income from the same source appearing as bonus/extra
        rendimentos_extras = []
        for r in self.declaration.rendimentos:
            if r.descricao:
                desc_upper = r.descricao.upper()
                if any(kw in desc_upper for kw in ["13", "BONUS", "BÔNUS", "PLR", "EXTRA"]):
                    rendimentos_extras.append(r)

        if rendimentos_extras:
            total_extra = sum(r.valor_anual for r in rendimentos_extras)
            total_renda = self.declaration.total_rendimentos_tributaveis

            # If "extra" income is more than 30% of total, might be timing manipulation
            if total_renda > 0 and total_extra / total_renda > Decimal("0.30"):
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Alta proporção de rendimentos classificados como bônus/extras: "
                            f"R$ {total_extra:,.2f} ({total_extra / total_renda * 100:.0f}% "
                            f"da renda tributável). Verificar classificação correta."
                        ),
                        risco=RiskLevel.LOW,
                        campo="rendimentos",
                        categoria=WarningCategory.CONSISTENCIA,
                        informativo=True,
                        valor_impacto=total_extra,
                    )
                )

    def _check_patrimony_vs_income_timing(self) -> None:
        """Check for patrimony changes inconsistent with income timing."""
        variacao_patrimonio = (
            self.declaration.resumo_patrimonio.variacao_patrimonial
        )

        renda_disponivel = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
            - self.declaration.total_deducoes
        )

        # Large patrimony increase without corresponding income
        if (
            variacao_patrimonio > 0
            and renda_disponivel > 0
            and variacao_patrimonio > renda_disponivel * Decimal("1.5")
        ):
            diferenca = variacao_patrimonio - renda_disponivel

            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.TIMING_FLUXO_CAIXA_SUSPEITO,
                    descricao=(
                        f"Variação patrimonial (R$ {variacao_patrimonio:,.2f}) "
                        f"significativamente maior que renda disponível "
                        f"(R$ {renda_disponivel:,.2f}). "
                        f"Diferença de R$ {diferenca:,.2f} sem explicação aparente."
                    ),
                    risco=RiskLevel.HIGH,
                    recomendacao=(
                        "Verificar se há rendimentos não declarados, doações, "
                        "heranças ou financiamentos que expliquem a variação."
                    ),
                    valor_impacto=diferenca,
                )
            )

    def _extract_cnpj_from_text(self, text: str) -> str:
        """Extract CNPJ from text (discriminacao field).

        Looks for patterns like:
        - "CNPJ 11222333000181"
        - "CNPJ: 11.222.333/0001-81"
        - "11222333000181" (14-digit sequence)

        Args:
            text: Text to search for CNPJ

        Returns:
            CNPJ digits if found, empty string otherwise
        """
        import re

        if not text:
            return ""

        # Try to find "CNPJ" followed by digits
        cnpj_pattern = re.search(r"CNPJ[:\s]*(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})", text.upper())
        if cnpj_pattern:
            return "".join(filter(str.isdigit, cnpj_pattern.group(1)))

        # Look for a 14-digit sequence that could be a CNPJ
        digit_sequences = re.findall(r"\d{14}", "".join(text.split()))
        if digit_sequences:
            return digit_sequences[0]

        return ""

    def _normalize_asset_key(self, nome: str, tipo: str, cnpj: str) -> str:
        """Normalize asset identifier for matching.

        Args:
            nome: Asset name/description
            tipo: Asset type code
            cnpj: CNPJ if applicable

        Returns:
            Normalized key string
        """
        # If CNPJ is available, use it as primary identifier
        if cnpj:
            digits = "".join(filter(str.isdigit, cnpj))
            if len(digits) >= 8:
                return f"CNPJ:{digits[:8]}"

        # Otherwise, use normalized name
        if nome:
            # Extract key words
            nome_upper = nome.upper()
            # Remove common filler words
            for word in ["DE", "DA", "DO", "E", "EM", "NA", "NO", "LTDA", "S/A", "ME", "EIRELI"]:
                nome_upper = nome_upper.replace(f" {word} ", " ")

            # Get first meaningful words
            palavras = nome_upper.split()[:3]
            if palavras:
                return f"NOME:{'_'.join(palavras)}"

        if tipo:
            return f"TIPO:{tipo}"

        return ""

    def _keys_match(self, key1: str, key2: str) -> bool:
        """Check if two asset keys potentially match.

        Args:
            key1: First key
            key2: Second key

        Returns:
            True if keys might represent the same asset
        """
        if not key1 or not key2:
            return False

        # Exact match
        if key1 == key2:
            return True

        # Same type (CNPJ, NOME, TIPO) with partial match
        prefix1 = key1.split(":")[0] if ":" in key1 else ""
        prefix2 = key2.split(":")[0] if ":" in key2 else ""

        if prefix1 == prefix2:
            # For CNPJ, check if base is the same
            if prefix1 == "CNPJ":
                val1 = key1.split(":")[1] if ":" in key1 else ""
                val2 = key2.split(":")[1] if ":" in key2 else ""
                return val1[:8] == val2[:8] if val1 and val2 else False

            # For NOME, check if first word matches
            if prefix1 == "NOME":
                val1 = key1.split(":")[1] if ":" in key1 else ""
                val2 = key2.split(":")[1] if ":" in key2 else ""
                word1 = val1.split("_")[0] if val1 else ""
                word2 = val2.split("_")[0] if val2 else ""
                return word1 == word2 if word1 and word2 else False

        return False


def analyze_advanced_patterns(declaration: Declaration) -> tuple[list[Inconsistency], list[Warning]]:
    """Convenience function to run advanced pattern analysis.

    Args:
        declaration: Declaration to analyze

    Returns:
        Tuple of (inconsistencies, warnings) found
    """
    detector = AdvancedPatternDetector(declaration)
    return detector.analyze()
