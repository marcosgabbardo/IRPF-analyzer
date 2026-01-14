"""Consistency analyzer for IRPF declarations."""

from decimal import Decimal
from typing import Optional

from irpf_analyzer.core.models.analysis import (
    Inconsistency,
    InconsistencyType,
    PatrimonyFlowAnalysis,
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
        self.patrimony_flow: Optional[PatrimonyFlowAnalysis] = None

    def analyze(self) -> tuple[list[Inconsistency], list[Warning]]:
        """Run all consistency checks."""
        self._check_patrimony_vs_income()
        self._check_patrimony_variation()
        self._check_zero_values()

        return self.inconsistencies, self.warnings

    def get_patrimony_flow(self) -> Optional[PatrimonyFlowAnalysis]:
        """Return the patrimony flow analysis (calculated during analyze())."""
        return self.patrimony_flow

    def _check_patrimony_vs_income(self) -> None:
        """Check if patrimony growth is compatible with declared income and cash flows.

        The logic is: all income sources + all liquidated assets should explain
        the patrimony variation (plus reasonable living expenses).
        """
        resumo = self.declaration.resumo_patrimonio
        variacao_patrimonio = resumo.variacao_patrimonial

        # === Calculate all sources of available resources ===

        # 1. Declared income (salary, pro-labore, etc.)
        renda_declarada = (
            self.declaration.total_rendimentos_tributaveis
            + self.declaration.total_rendimentos_isentos
            + self.declaration.total_rendimentos_exclusivos
        )

        # 2. Capital gains from alienations (sale of companies, properties, etc.)
        ganho_capital = sum(
            a.ganho_capital for a in self.declaration.alienacoes
            if a.ganho_capital and a.ganho_capital > 0
        )

        # 3. Profit from foreign stocks declared within assets
        lucro_acoes_exterior = sum(
            b.lucro_prejuizo for b in self.declaration.bens_direitos
            if b.lucro_prejuizo and b.lucro_prejuizo > 0
        )

        # 4. Sale proceeds from alienations (for informational purposes only)
        # NOTE: We don't count this in recursos_totais because:
        # - The asset value was already in patrimonio_anterior
        # - Only the ganho_capital (profit) represents new resources
        valor_alienacoes = sum(
            a.valor_alienacao for a in self.declaration.alienacoes
            if a.valor_alienacao and a.valor_alienacao > 0
        )

        # 5. Liquidated assets value (for informational purposes only)
        # NOTE: We don't count this in recursos_totais because:
        # - The principal was already in patrimonio_anterior
        # - The yield is already included in rendimentos_exclusivos (taxed at source)
        ativos_liquidados = self._get_liquidated_assets_value()

        # Total resources available for investment
        # Only count actual NEW money:
        # - renda_declarada: salary, dividends, interest (includes CDB/LCA yields)
        # - ganho_capital: profit from sales (not the sale value itself)
        # - lucro_acoes_exterior: profit from foreign stocks
        recursos_totais = (
            renda_declarada
            + ganho_capital
            + lucro_acoes_exterior
            # NOT valor_alienacoes - principal was already in patrimony
            # NOT ativos_liquidados - principal was already in patrimony
        )

        # === Calculate if resources explain patrimony variation ===

        # Estimate living expenses based on income brackets
        # Higher income = lower percentage spent on living expenses
        if renda_declarada > Decimal("500000"):
            despesas_vida = renda_declarada * Decimal("0.30")
        elif renda_declarada > Decimal("250000"):
            despesas_vida = renda_declarada * Decimal("0.50")
        elif renda_declarada > Decimal("100000"):
            despesas_vida = renda_declarada * Decimal("0.65")
        elif renda_declarada > Decimal("50000"):
            despesas_vida = renda_declarada * Decimal("0.80")
        else:
            despesas_vida = renda_declarada  # 100% - all income goes to expenses

        # Resources available after living expenses
        recursos_disponiveis = recursos_totais - despesas_vida

        # Calculate balance (positive = more resources than needed)
        saldo = recursos_disponiveis - variacao_patrimonio
        explicado = variacao_patrimonio <= recursos_disponiveis * Decimal("1.5")

        # === Store the flow analysis for reporting ===
        self.patrimony_flow = PatrimonyFlowAnalysis(
            patrimonio_anterior=resumo.total_bens_anterior,
            patrimonio_atual=resumo.total_bens_atual,
            variacao_patrimonial=variacao_patrimonio,
            renda_declarada=renda_declarada,
            ganho_capital=ganho_capital,
            lucro_acoes_exterior=lucro_acoes_exterior,
            valor_alienacoes=valor_alienacoes,
            ativos_liquidados=ativos_liquidados,
            recursos_totais=recursos_totais,
            despesas_vida_estimadas=despesas_vida,
            recursos_disponiveis=recursos_disponiveis,
            saldo=saldo,
            explicado=explicado,
        )

        # Skip inconsistency check if variation is small
        if abs(variacao_patrimonio) < self.MIN_PATRIMONY_VARIATION:
            return

        # Skip if no resources declared
        if recursos_totais <= 0:
            return

        # Patrimony variation should be explainable by available resources
        # Allow some margin for timing differences, FX variations, etc. (1.5x threshold)
        if variacao_patrimonio > 0:
            if variacao_patrimonio > recursos_disponiveis * Decimal("1.5"):
                # Calculate how much is unexplained
                diferenca = variacao_patrimonio - recursos_disponiveis

                if variacao_patrimonio > recursos_disponiveis * Decimal("3"):
                    risco = RiskLevel.HIGH
                elif variacao_patrimonio > recursos_disponiveis * Decimal("2"):
                    risco = RiskLevel.MEDIUM
                else:
                    risco = RiskLevel.LOW

                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.PATRIMONIO_VS_RENDA,
                        descricao=(
                            f"Variação patrimonial (R$ {variacao_patrimonio:,.2f}) "
                            f"superior aos recursos disponíveis estimados (R$ {recursos_disponiveis:,.2f})"
                        ),
                        valor_declarado=variacao_patrimonio,
                        valor_esperado=recursos_disponiveis,
                        risco=risco,
                        recomendacao=(
                            "Verifique se há rendimentos não declarados ou "
                            "se valores de bens estão corretos"
                        ),
                        valor_impacto=diferenca,  # Unexplained amount
                    )
                )

    def _get_liquidated_assets_value(self) -> Decimal:
        """Get total value of assets that went to zero (matured/liquidated).

        These represent cash that became available for reinvestment:
        - CDB, LCA, LCI that matured
        - Other fixed income that was redeemed
        - Investment fund quotas that were sold

        Note: Foreign stocks that went to zero are handled separately
        (they have lucro_prejuizo declared).
        """
        total = Decimal("0")

        for bem in self.declaration.bens_direitos:
            # Asset went from positive to zero
            if bem.situacao_anterior > 0 and bem.situacao_atual == 0:
                # Skip foreign stocks (handled via lucro_prejuizo)
                if self._is_foreign_stock(bem):
                    continue

                # Skip if there's a matching alienation (already counted)
                if self._has_matching_alienation(bem):
                    continue

                # Include fixed income and similar assets
                if self._is_liquidatable_asset(bem):
                    total += bem.situacao_anterior

        return total

    def _is_liquidatable_asset(self, bem) -> bool:
        """Check if asset type can be liquidated/matured releasing cash."""
        descricao_upper = bem.discriminacao.upper()

        # Fixed income products
        fixed_income_keywords = [
            "CDB", "LCA", "LCI", "LF ",
            "RENDA FIXA", "TESOURO", "DEBENTURE", "DEBÊNTURE",
            "APLICACAO", "APLICAÇÃO", "FUNDO",
        ]
        for keyword in fixed_income_keywords:
            if keyword in descricao_upper:
                return True

        # Investment groups that can be redeemed
        from irpf_analyzer.core.models.enums import GrupoBem
        redeemable_groups = [
            GrupoBem.APLICACOES_FINANCEIRAS,
            GrupoBem.FUNDOS,
        ]
        if bem.grupo in redeemable_groups:
            return True

        return False

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
                            valor_impacto=abs(variacao),
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
                            valor_impacto=abs(variacao),
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
                            valor_impacto=abs(variacao),
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
                            valor_impacto=abs(variacao),
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
                        valor_impacto=variacao,
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
                    valor_impacto=total_patrimonio,  # Full patrimony at stake
                )
            )
