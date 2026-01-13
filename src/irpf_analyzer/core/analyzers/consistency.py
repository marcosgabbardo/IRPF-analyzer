"""Consistency analyzer for IRPF declarations."""

from decimal import Decimal

from irpf_analyzer.core.models.analysis import (
    Inconsistency,
    InconsistencyType,
    RiskLevel,
    Warning,
)
from irpf_analyzer.core.models.declaration import Declaration


class ConsistencyAnalyzer:
    """Analyzes consistency between declared values."""

    # Threshold for patrimony variation vs income ratio (200% is suspicious)
    PATRIMONY_VARIATION_THRESHOLD = Decimal("2.0")

    # Minimum patrimony variation to consider (ignore small changes)
    MIN_PATRIMONY_VARIATION = Decimal("10000")

    def __init__(self, declaration: Declaration):
        self.declaration = declaration
        self.inconsistencies: list[Inconsistency] = []
        self.warnings: list[Warning] = []

    def analyze(self) -> tuple[list[Inconsistency], list[Warning]]:
        """Run all consistency checks."""
        self._check_patrimony_vs_income()
        self._check_patrimony_variation()
        self._check_zero_values()

        return self.inconsistencies, self.warnings

    def _check_patrimony_vs_income(self) -> None:
        """Check if patrimony growth is compatible with declared income."""
        resumo = self.declaration.resumo_patrimonio
        variacao_patrimonio = resumo.variacao_patrimonial

        # Get total declared income
        renda_total = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
            + self.declaration.total_rendimentos_exclusivos
        )

        # Skip if income is zero or variation is small
        if renda_total <= 0 or abs(variacao_patrimonio) < self.MIN_PATRIMONY_VARIATION:
            return

        # Patrimony increased more than income allows
        if variacao_patrimonio > 0:
            # Estimate maximum reasonable patrimony growth
            # (income - estimated living expenses ~50%)
            renda_disponivel = renda_total * Decimal("0.5")

            if variacao_patrimonio > renda_disponivel * self.PATRIMONY_VARIATION_THRESHOLD:
                ratio = (variacao_patrimonio / renda_disponivel) if renda_disponivel > 0 else Decimal("999")

                if ratio > Decimal("3"):
                    risco = RiskLevel.HIGH
                elif ratio > Decimal("2"):
                    risco = RiskLevel.MEDIUM
                else:
                    risco = RiskLevel.LOW

                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.PATRIMONIO_VS_RENDA,
                        descricao=(
                            f"Variação patrimonial (R$ {variacao_patrimonio:,.2f}) "
                            f"superior à renda disponível estimada (R$ {renda_disponivel:,.2f})"
                        ),
                        valor_declarado=variacao_patrimonio,
                        valor_esperado=renda_disponivel,
                        risco=risco,
                        recomendacao=(
                            "Verifique se há rendimentos não declarados ou "
                            "se valores de bens estão corretos"
                        ),
                    )
                )

    def _check_patrimony_variation(self) -> None:
        """Check for suspicious patrimony variations."""
        for bem in self.declaration.bens_direitos:
            variacao = bem.variacao_absoluta
            percentual = bem.variacao_percentual

            # Skip assets that normally go to zero without concern
            if self._is_exempt_from_variation_warning(bem):
                continue

            # Large decrease in asset value might indicate undeclared sale
            if variacao < -self.MIN_PATRIMONY_VARIATION and percentual < Decimal("-50"):
                # Check if profit/loss was declared within the asset itself
                # (used for foreign stocks like BITFARMS, etc.)
                if bem.tem_lucro_prejuizo_declarado:
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Venda declarada: {bem.discriminacao[:50]}... "
                                f"(lucro/prejuízo informado no bem)"
                            ),
                            risco=RiskLevel.LOW,
                            campo="bens_direitos",
                        )
                    )
                # Check if there's a corresponding alienação (sale) declared
                elif self._has_matching_alienation(bem):
                    # Sale was declared - no warning needed, just info
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Venda declarada: {bem.discriminacao[:50]}... "
                                f"(alienação encontrada)"
                            ),
                            risco=RiskLevel.LOW,
                            campo="bens_direitos",
                        )
                    )
                # For foreign stocks (codigo 12), lucro=0 could mean break-even sale
                # or missing declaration - show warning with both possibilities (informative only)
                elif self._is_foreign_stock(bem):
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Ação estrangeira zerada: {bem.discriminacao[:50]}... "
                                f"Pode ser venda sem lucro/prejuízo ou falta de declaração"
                            ),
                            risco=RiskLevel.MEDIUM,
                            campo="bens_direitos",
                            informativo=True,  # Shows in output but doesn't count in score
                        )
                    )
                else:
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Grande redução em bem ({percentual:.0f}%): {bem.discriminacao[:50]}... "
                                f"Verifique se houve venda não declarada"
                            ),
                            risco=RiskLevel.MEDIUM,
                            campo="bens_direitos",
                        )
                    )

            # Large increase without clear source
            if variacao > Decimal("100000") and percentual > Decimal("100"):
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Grande aumento em bem ({percentual:.0f}%): {bem.discriminacao[:50]}... "
                            f"Verifique origem dos recursos"
                        ),
                        risco=RiskLevel.LOW,
                        campo="bens_direitos",
                    )
                )

    def _has_matching_alienation(self, bem) -> bool:
        """Check if there's a declared alienation matching this asset."""
        if not self.declaration.alienacoes:
            return False

        descricao_upper = bem.discriminacao.upper()

        for alienacao in self.declaration.alienacoes:
            # Match by company name
            if alienacao.nome_bem:
                nome_upper = alienacao.nome_bem.upper()
                # Check if key words from alienação appear in asset description
                palavras_chave = nome_upper.split()[:3]  # First 3 words
                matches = sum(1 for p in palavras_chave if p in descricao_upper)
                if matches >= 2:
                    return True

            # Match by CNPJ
            if alienacao.cnpj and alienacao.cnpj in bem.discriminacao:
                return True

        return False

    def _is_foreign_stock(self, bem) -> bool:
        """Check if asset is a foreign stock (ação estrangeira).

        Foreign stocks use codigo 12 and have profit/loss declared within the asset.
        When sold at break-even, lucro_prejuizo = 0 is legitimate.
        """
        # Codigo 12 = Ações e assemelhados (mercado à vista)
        # For foreign stocks, the description usually contains $ or US$ or similar
        if bem.codigo == "12":
            descricao_upper = bem.discriminacao.upper()
            # Check for foreign indicators
            foreign_indicators = ["$", "US$", "USD", "AVENUE", "INTERACTIVE BROKERS"]
            return any(ind in descricao_upper for ind in foreign_indicators)
        return False

    def _is_exempt_from_variation_warning(self, bem) -> bool:
        """Check if asset type is exempt from variation warnings.

        Some assets normally go to zero without tax implications:
        - CDB/LCA/LCI: taxed at source when they mature
        - Account balances: can be transferred or spent
        - Fixed income in general: taxed at source
        """
        descricao_upper = bem.discriminacao.upper()

        # Fixed income products (taxed at source)
        fixed_income_keywords = [
            "CDB", "LCA", "LCI", "LF ",  # Note space after LF
            "RENDA FIXA", "POUPANCA", "POUPANÇA",
            "TESOURO", "DEBENTURE", "DEBÊNTURE",
        ]
        for keyword in fixed_income_keywords:
            if keyword in descricao_upper:
                return True

        # Account balances (just money, can be moved)
        balance_keywords = [
            "SALDO EM CONTA", "SALDO DE CONTA",
            "CONTA CORRENTE", "CONTA POUPANÇA",
            "SALDO DE R$", "SALDO EM R$",
        ]
        for keyword in balance_keywords:
            if keyword in descricao_upper:
                return True

        # Groups that are typically safe
        # Group 04 = Aplicações financeiras, 05 = Poupança, 06 = Depósitos
        from irpf_analyzer.core.models.enums import GrupoBem
        safe_groups = [
            GrupoBem.APLICACOES_FINANCEIRAS,
            GrupoBem.POUPANCA,
            GrupoBem.DEPOSITOS_VISTA,
        ]
        if bem.grupo in safe_groups:
            return True

        return False

    def _check_zero_values(self) -> None:
        """Check for suspicious zero values that might indicate omissions."""
        # Declaration with no income is suspicious
        total_renda = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
        )

        total_patrimonio = self.declaration.resumo_patrimonio.total_bens_atual

        # Has patrimony but no income
        if total_patrimonio > Decimal("100000") and total_renda == 0:
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.VALOR_ZERADO_SUSPEITO,
                    descricao=(
                        f"Patrimônio de R$ {total_patrimonio:,.2f} declarado "
                        f"mas nenhum rendimento informado"
                    ),
                    valor_declarado=total_renda,
                    valor_esperado=None,
                    risco=RiskLevel.HIGH,
                    recomendacao="Verifique se todos os rendimentos foram declarados",
                )
            )
