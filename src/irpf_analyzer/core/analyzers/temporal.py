"""Temporal pattern analyzer for multi-year IRPF analysis.

This module provides pattern detection across multiple years of declarations,
identifying suspicious patterns that only become visible when comparing
declarations from different years.
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from irpf_analyzer.core.models.analysis import (
    InconsistencyType,
    RiskLevel,
)
from irpf_analyzer.core.models.declaration import Declaration


class TemporalPattern(BaseModel):
    """Represents a detected temporal pattern.

    Temporal patterns are suspicious patterns that emerge only when
    comparing multiple years of declarations.
    """

    tipo: InconsistencyType = Field(..., description="Type of pattern detected")
    descricao: str = Field(..., description="Human-readable description")
    anos_afetados: list[int] = Field(..., description="Years involved in the pattern")
    risco: RiskLevel = Field(..., description="Risk level")
    valor_impacto: Optional[Decimal] = Field(
        default=None, description="Financial impact value"
    )
    recomendacao: Optional[str] = Field(
        default=None, description="Recommendation for resolution"
    )


class TemporalPatternAnalyzer:
    """Analyzes patterns across multiple years of declarations.

    Requires at least 2 declarations from different years.
    Ideally 3+ years for better pattern detection.

    Detects:
    - Stagnant income with growing patrimony
    - Sudden income drops
    - Constant medical expenses across years
    - Suspicious liquidation patterns
    """

    # Threshold for considering income "stagnant" (variation < 5% per year)
    RENDA_ESTAGNADA_LIMIAR = Decimal("0.05")

    # Threshold for "suspicious" patrimony growth (> 20% per year without explanation)
    PATRIMONIO_CRESCIMENTO_LIMIAR = Decimal("0.20")

    # Threshold for "sudden" income drop (> 30%)
    QUEDA_RENDA_LIMIAR = Decimal("0.30")

    # Maximum variation to consider values "constant" (< 10%)
    VARIACAO_CONSTANTE_LIMIAR = Decimal("0.10")

    def __init__(self, declarations: list[Declaration]):
        """Initialize with list of declarations from different years.

        Args:
            declarations: List of declarations to analyze (min 2)

        Raises:
            ValueError: If less than 2 declarations or different taxpayers
        """
        if len(declarations) < 2:
            raise ValueError(
                "Análise temporal requer pelo menos 2 declarações de anos diferentes"
            )

        # Sort by year
        self.declarations = sorted(declarations, key=lambda d: d.ano_exercicio)

        # Verify same taxpayer
        cpfs = set(d.contribuinte.cpf for d in self.declarations)
        if len(cpfs) > 1:
            raise ValueError("Todas as declarações devem ser do mesmo contribuinte")

        # Verify different years
        anos = set(d.ano_exercicio for d in self.declarations)
        if len(anos) != len(self.declarations):
            raise ValueError("Declarações devem ser de anos diferentes")

        self.patterns: list[TemporalPattern] = []

    @property
    def contribuinte_nome(self) -> str:
        """Return taxpayer name."""
        return self.declarations[0].contribuinte.nome

    @property
    def periodo(self) -> str:
        """Return period covered by analysis."""
        anos = [d.ano_exercicio for d in self.declarations]
        return f"{min(anos)}-{max(anos)}"

    def analyze(self) -> list[TemporalPattern]:
        """Run all temporal pattern checks.

        Returns:
            List of detected temporal patterns
        """
        self._check_renda_estagnada_patrimonio_crescente()
        self._check_queda_subita_renda()
        self._check_despesas_medicas_constantes()
        self._check_padrao_liquidacao()

        return self.patterns

    def _get_renda_total(self, decl: Declaration) -> Decimal:
        """Get total income for a declaration."""
        return (
            decl.total_rendimentos_tributaveis
            + decl.total_rendimentos_isentos
        )

    def _get_patrimonio(self, decl: Declaration) -> Decimal:
        """Get total patrimony for a declaration."""
        return decl.resumo_patrimonio.total_bens_atual

    def _check_renda_estagnada_patrimonio_crescente(self) -> None:
        """Detect stagnant income with growing patrimony.

        Suspicious pattern: Income doesn't grow or grows little, but patrimony
        grows significantly year after year.

        May indicate:
        - Undeclared income
        - Undeclared inheritance/donation
        - Undeclared capital gains
        """
        anos = []
        rendas = []
        patrimonios = []

        for decl in self.declarations:
            anos.append(decl.ano_exercicio)
            rendas.append(self._get_renda_total(decl))
            patrimonios.append(self._get_patrimonio(decl))

        # Calculate annual variations
        variacoes_renda = []
        variacoes_patrimonio = []

        for i in range(1, len(anos)):
            if rendas[i - 1] > 0:
                var_renda = (rendas[i] - rendas[i - 1]) / rendas[i - 1]
            else:
                var_renda = Decimal("0")

            if patrimonios[i - 1] > 0:
                var_patrimonio = (patrimonios[i] - patrimonios[i - 1]) / patrimonios[i - 1]
            else:
                var_patrimonio = Decimal("0")

            variacoes_renda.append(var_renda)
            variacoes_patrimonio.append(var_patrimonio)

        if not variacoes_renda:
            return

        # Check pattern: stagnant income + growing patrimony
        renda_estagnada = all(
            abs(v) < self.RENDA_ESTAGNADA_LIMIAR for v in variacoes_renda
        )

        patrimonio_crescente = all(
            v > self.PATRIMONIO_CRESCIMENTO_LIMIAR for v in variacoes_patrimonio
        )

        if renda_estagnada and patrimonio_crescente:
            crescimento_total = patrimonios[-1] - patrimonios[0]
            var_media_renda = sum(variacoes_renda) / len(variacoes_renda) * 100

            self.patterns.append(
                TemporalPattern(
                    tipo=InconsistencyType.RENDA_ESTAGNADA_PATRIMONIO_CRESCENTE,
                    descricao=(
                        f"Renda estagnada (var. média {var_media_renda:.1f}%/ano) "
                        f"enquanto patrimônio cresceu significativamente "
                        f"(R$ {patrimonios[0]:,.0f} → R$ {patrimonios[-1]:,.0f})"
                    ),
                    anos_afetados=anos,
                    risco=RiskLevel.HIGH,
                    valor_impacto=crescimento_total,
                    recomendacao=(
                        "Verificar se há rendimentos não declarados, heranças, "
                        "doações ou ganhos de capital omitidos"
                    ),
                )
            )

    def _check_queda_subita_renda(self) -> None:
        """Detect sudden income drop followed by patrimony maintenance.

        Suspicious pattern: Income drops drastically but patrimony stays
        the same or even grows.

        May indicate:
        - Undeclared change to company (pejotização)
        - Income transferred to third parties
        - Income omission
        """
        for i in range(1, len(self.declarations)):
            decl_anterior = self.declarations[i - 1]
            decl_atual = self.declarations[i]

            renda_anterior = self._get_renda_total(decl_anterior)
            renda_atual = self._get_renda_total(decl_atual)

            if renda_anterior <= 0:
                continue

            variacao_renda = (renda_atual - renda_anterior) / renda_anterior

            # Drop greater than 30%
            if variacao_renda < -self.QUEDA_RENDA_LIMIAR:
                patrimonio_anterior = self._get_patrimonio(decl_anterior)
                patrimonio_atual = self._get_patrimonio(decl_atual)

                # But patrimony stayed the same or grew
                if patrimonio_atual >= patrimonio_anterior * Decimal("0.9"):
                    self.patterns.append(
                        TemporalPattern(
                            tipo=InconsistencyType.QUEDA_SUBITA_RENDA,
                            descricao=(
                                f"Queda de {abs(variacao_renda) * 100:.0f}% na renda "
                                f"({decl_anterior.ano_exercicio}: R$ {renda_anterior:,.0f} → "
                                f"{decl_atual.ano_exercicio}: R$ {renda_atual:,.0f}) "
                                f"mas patrimônio se manteve (R$ {patrimonio_atual:,.0f})"
                            ),
                            anos_afetados=[
                                decl_anterior.ano_exercicio,
                                decl_atual.ano_exercicio,
                            ],
                            risco=RiskLevel.MEDIUM,
                            valor_impacto=renda_anterior - renda_atual,
                            recomendacao=(
                                "Verificar se houve pejotização, mudança de fonte de renda, "
                                "ou rendimentos não declarados"
                            ),
                        )
                    )

    def _check_despesas_medicas_constantes(self) -> None:
        """Detect suspiciously constant medical expenses.

        Suspicious pattern: Medical expenses practically equal year after year,
        which is statistically unlikely.

        May indicate:
        - "Guessed" or fabricated values
        - Reused receipts
        """
        despesas = []
        anos = []

        for decl in self.declarations:
            despesa = decl.resumo_deducoes.despesas_medicas
            if despesa > 0:
                despesas.append(despesa)
                anos.append(decl.ano_exercicio)

        if len(despesas) < 3:
            return  # Need at least 3 years

        # Calculate variations between consecutive years
        variacoes = []
        for i in range(1, len(despesas)):
            if despesas[i - 1] > 0:
                var = abs(despesas[i] - despesas[i - 1]) / despesas[i - 1]
                variacoes.append(var)

        if not variacoes:
            return

        # If all variations are very small, it's suspicious
        if all(v < self.VARIACAO_CONSTANTE_LIMIAR for v in variacoes):
            valores_str = ", ".join(
                f"{anos[i]}: R$ {despesas[i]:,.0f}" for i in range(len(anos))
            )

            self.patterns.append(
                TemporalPattern(
                    tipo=InconsistencyType.DESPESAS_MEDICAS_CONSTANTES,
                    descricao=(
                        f"Despesas médicas praticamente constantes por {len(despesas)} anos: "
                        f"{valores_str}"
                    ),
                    anos_afetados=anos,
                    risco=RiskLevel.MEDIUM,
                    valor_impacto=sum(despesas),
                    recomendacao=(
                        "Despesas médicas constantes são estatisticamente improváveis. "
                        "Verificar se valores são reais e documentados."
                    ),
                )
            )

    def _check_padrao_liquidacao(self) -> None:
        """Detect suspicious liquidation pattern.

        Suspicious pattern: Taxpayer systematically liquidates assets
        without declaring capital gains or applying to new investments.

        May indicate:
        - Capital gains tax evasion
        - Money leaving the country
        - Financing undeclared activities
        """
        # Track assets that disappeared over the years
        ativos_liquidados_por_ano: dict[int, list[tuple[str, Decimal]]] = {}

        for i in range(1, len(self.declarations)):
            decl_anterior = self.declarations[i - 1]
            decl_atual = self.declarations[i]
            ano = decl_atual.ano_exercicio

            ativos_liquidados_por_ano[ano] = []

            # Compare assets between years
            bens_anteriores = {
                b.discriminacao[:50]: b
                for b in decl_anterior.bens_direitos
                if b.situacao_atual > 0
            }

            bens_atuais = {
                b.discriminacao[:50]: b for b in decl_atual.bens_direitos
            }

            for desc, bem_ant in bens_anteriores.items():
                if desc not in bens_atuais or bens_atuais[desc].situacao_atual == 0:
                    ativos_liquidados_por_ano[ano].append((desc, bem_ant.situacao_atual))

        # Check if there's a liquidation pattern (multiple years with liquidations)
        anos_com_liquidacao = [
            ano
            for ano, liquidacoes in ativos_liquidados_por_ano.items()
            if len(liquidacoes) >= 2
            and sum(v for _, v in liquidacoes) > Decimal("50000")
        ]

        if len(anos_com_liquidacao) >= 2:
            total_liquidado = sum(
                sum(v for _, v in ativos_liquidados_por_ano[ano])
                for ano in anos_com_liquidacao
            )

            self.patterns.append(
                TemporalPattern(
                    tipo=InconsistencyType.PADRAO_LIQUIDACAO_SUSPEITO,
                    descricao=(
                        f"Padrão de liquidação sistemática detectado em "
                        f"{len(anos_com_liquidacao)} anos: "
                        f"Total liquidado R$ {total_liquidado:,.0f}"
                    ),
                    anos_afetados=anos_com_liquidacao,
                    risco=RiskLevel.MEDIUM,
                    valor_impacto=total_liquidado,
                    recomendacao=(
                        "Verificar se ganhos de capital foram declarados "
                        "e destino dos recursos liquidados."
                    ),
                )
            )


def analyze_temporal_patterns(declarations: list[Declaration]) -> list[TemporalPattern]:
    """Convenience function for temporal analysis.

    Args:
        declarations: List of declarations from different years (min 2)

    Returns:
        List of detected temporal patterns

    Raises:
        ValueError: If less than 2 declarations or different taxpayers
    """
    analyzer = TemporalPatternAnalyzer(declarations)
    return analyzer.analyze()
