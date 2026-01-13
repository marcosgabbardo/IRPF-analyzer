"""Analysis result models."""

from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk level classification."""

    LOW = "BAIXO"
    MEDIUM = "MÉDIO"
    HIGH = "ALTO"
    CRITICAL = "CRÍTICO"


class InconsistencyType(str, Enum):
    """Types of inconsistencies detected."""

    PATRIMONIO_VS_RENDA = "patrimonio_vs_renda"
    DESPESAS_MEDICAS_ALTAS = "despesas_medicas_altas"
    DESPESAS_EDUCACAO_LIMITE = "despesas_educacao_limite"
    VARIACAO_PATRIMONIO_SUSPEITA = "variacao_patrimonio_suspeita"
    DEDUCAO_SEM_COMPROVANTE = "deducao_sem_comprovante"
    DEPENDENTE_DUPLICADO = "dependente_duplicado"
    VALOR_ZERADO_SUSPEITO = "valor_zerado_suspeito"


class Inconsistency(BaseModel):
    """An inconsistency found in the declaration."""

    tipo: InconsistencyType = Field(..., description="Type of inconsistency")
    descricao: str = Field(..., description="Human-readable description")
    valor_declarado: Optional[Decimal] = Field(default=None)
    valor_esperado: Optional[Decimal] = Field(default=None)
    risco: RiskLevel = Field(default=RiskLevel.MEDIUM)
    recomendacao: Optional[str] = Field(default=None)


class Warning(BaseModel):
    """A warning about potential issues."""

    mensagem: str = Field(..., description="Warning message")
    risco: RiskLevel = Field(default=RiskLevel.LOW)
    campo: Optional[str] = Field(default=None, description="Related field")
    informativo: bool = Field(
        default=False,
        description="If True, shows in output but doesn't count towards risk score",
    )


class Suggestion(BaseModel):
    """An optimization suggestion."""

    titulo: str = Field(..., description="Suggestion title")
    descricao: str = Field(..., description="Detailed description")
    economia_potencial: Optional[Decimal] = Field(
        default=None, description="Potential savings"
    )
    prioridade: int = Field(default=1, ge=1, le=5, description="Priority 1-5")


class RiskScore(BaseModel):
    """Risk score calculation result.

    Score is 0-100 where:
    - 100% = Fully compliant, very low risk of audit
    - 0% = High risk, likely to be flagged for audit
    """

    score: int = Field(..., ge=0, le=100, description="Compliance score 0-100 (higher = safer)")
    level: RiskLevel = Field(..., description="Risk level classification")
    fatores: list[str] = Field(default_factory=list, description="Contributing factors")

    @classmethod
    def from_score(cls, score: int, fatores: list[str] | None = None) -> "RiskScore":
        """Create RiskScore from numeric score (higher = safer)."""
        score = max(0, min(100, score))

        # Higher score = lower risk
        if score >= 80:
            level = RiskLevel.LOW
        elif score >= 50:
            level = RiskLevel.MEDIUM
        elif score >= 25:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        return cls(score=score, level=level, fatores=fatores or [])


class PatrimonyFlowAnalysis(BaseModel):
    """Detailed breakdown of patrimony variation vs available resources.

    This shows how income, sales, and liquidated assets explain patrimony changes.
    """

    # Patrimony variation
    patrimonio_anterior: Decimal = Field(default=Decimal("0"))
    patrimonio_atual: Decimal = Field(default=Decimal("0"))
    variacao_patrimonial: Decimal = Field(default=Decimal("0"))

    # Income sources
    renda_declarada: Decimal = Field(default=Decimal("0"), description="Salary, pro-labore, etc.")
    ganho_capital: Decimal = Field(default=Decimal("0"), description="Capital gains from alienations")
    lucro_acoes_exterior: Decimal = Field(default=Decimal("0"), description="Profit from foreign stocks")
    valor_alienacoes: Decimal = Field(default=Decimal("0"), description="Sale proceeds")
    ativos_liquidados: Decimal = Field(default=Decimal("0"), description="Matured CDB/LCA/LCI")

    # Calculation
    recursos_totais: Decimal = Field(default=Decimal("0"))
    despesas_vida_estimadas: Decimal = Field(default=Decimal("0"))
    recursos_disponiveis: Decimal = Field(default=Decimal("0"))

    # Result
    saldo: Decimal = Field(default=Decimal("0"), description="recursos_disponiveis - variacao")
    explicado: bool = Field(default=True, description="True if resources explain variation")

    @property
    def percentual_despesas(self) -> int:
        """Return the percentage used for living expenses estimate."""
        if self.renda_declarada > Decimal("200000"):
            return 30
        return 50

    @property
    def disclaimer_despesas(self) -> str:
        """Return explanation of how living expenses were calculated."""
        pct = self.percentual_despesas
        return (
            f"Despesas de vida estimadas em {pct}% da renda declarada. "
            f"Este é um valor conservador - contribuintes com renda acima de "
            f"R$ 200.000 usam 30%, demais usam 50%."
        )


class AnalysisResult(BaseModel):
    """Complete analysis result."""

    risk_score: RiskScore = Field(..., description="Overall risk score")
    inconsistencies: list[Inconsistency] = Field(default_factory=list)
    warnings: list[Warning] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    patrimony_flow: Optional[PatrimonyFlowAnalysis] = Field(
        default=None, description="Detailed patrimony flow analysis"
    )

    @property
    def total_inconsistencies(self) -> int:
        """Count total inconsistencies."""
        return len(self.inconsistencies)

    @property
    def critical_count(self) -> int:
        """Count critical issues."""
        return sum(
            1 for i in self.inconsistencies if i.risco == RiskLevel.CRITICAL
        ) + sum(1 for w in self.warnings if w.risco == RiskLevel.CRITICAL)

    @property
    def high_count(self) -> int:
        """Count high risk issues."""
        return sum(
            1 for i in self.inconsistencies if i.risco == RiskLevel.HIGH
        ) + sum(1 for w in self.warnings if w.risco == RiskLevel.HIGH)
