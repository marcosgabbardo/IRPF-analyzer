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

    # Core consistency checks
    PATRIMONIO_VS_RENDA = "patrimonio_vs_renda"
    DESPESAS_MEDICAS_ALTAS = "despesas_medicas_altas"
    DESPESAS_EDUCACAO_LIMITE = "despesas_educacao_limite"
    VARIACAO_PATRIMONIO_SUSPEITA = "variacao_patrimonio_suspeita"
    DEDUCAO_SEM_COMPROVANTE = "deducao_sem_comprovante"
    DEPENDENTE_DUPLICADO = "dependente_duplicado"
    VALOR_ZERADO_SUSPEITO = "valor_zerado_suspeito"

    # Structural patterns (single declaration)
    VALORES_REDONDOS_DEDUCOES = "valores_redondos_deducoes"
    DEPRECIACAO_VEICULO_IRREGULAR = "depreciacao_veiculo_irregular"
    DESPESAS_MEDICAS_CONCENTRADAS = "despesas_medicas_concentradas"
    IMOVEL_SEM_RENDA_ALUGUEL = "imovel_sem_renda_aluguel"

    # Fraud patterns
    CPF_INVALIDO = "cpf_invalido"
    CNPJ_INVALIDO = "cnpj_invalido"
    DESPESA_MEDICA_FICTICIA = "despesa_medica_ficticia"
    ALUGUEL_NAO_DECLARADO = "aluguel_nao_declarado"

    # Financial inconsistency patterns
    SALDO_BANCARIO_INCOMPATIVEL = "saldo_bancario_incompativel"
    COMPRA_SEM_LASTRO = "compra_sem_lastro"
    DIVIDENDOS_VS_PARTICIPACAO = "dividendos_vs_participacao"

    # Statistical patterns
    VALOR_OUTLIER = "valor_outlier"
    DISTRIBUICAO_BENFORD_ANOMALA = "distribuicao_benford_anomala"

    # Temporal patterns (multi-year)
    RENDA_ESTAGNADA_PATRIMONIO_CRESCENTE = "renda_estagnada_patrimonio_crescente"
    QUEDA_SUBITA_RENDA = "queda_subita_renda"
    DESPESAS_MEDICAS_CONSTANTES = "despesas_medicas_constantes"
    PADRAO_LIQUIDACAO_SUSPEITO = "padrao_liquidacao_suspeito"

    # Phase 2 detections (v2.0)
    DESPESA_MEDICA_PF_ALTA = "despesa_medica_pf_alta"
    DEPENDENTE_IDADE_INCOMPATIVEL = "dependente_idade_incompativel"
    YIELD_ALUGUEL_INCOMPATIVEL = "yield_aluguel_incompativel"
    VEICULO_VALOR_IDADE_INCOMPATIVEL = "veiculo_valor_idade"
    IMOVEL_SUBAVALIADO = "imovel_subavaliado"
    RENDA_CONCENTRADA_DEZEMBRO = "renda_concentrada_dezembro"

    # Cross-validation patterns (simulated checks)
    CRUZAMENTO_DIRF_DIVERGENTE = "cruzamento_dirf"
    CRUZAMENTO_DIMOB_DIVERGENTE = "cruzamento_dimob"
    CRUZAMENTO_DOC_DIVERGENTE = "cruzamento_doc"
    CRUZAMENTO_EFINANCEIRA_DIVERGENTE = "cruzamento_efinanceira"


class Inconsistency(BaseModel):
    """An inconsistency found in the declaration."""

    tipo: InconsistencyType = Field(..., description="Type of inconsistency")
    descricao: str = Field(..., description="Human-readable description")
    valor_declarado: Optional[Decimal] = Field(default=None)
    valor_esperado: Optional[Decimal] = Field(default=None)
    risco: RiskLevel = Field(default=RiskLevel.MEDIUM)
    recomendacao: Optional[str] = Field(default=None)
    valor_impacto: Optional[Decimal] = Field(
        default=None,
        description="Value at stake for weighted score calculation",
    )


class WarningCategory(str, Enum):
    """Category of warning for grouping in output."""

    PADRAO = "padrao"  # Pattern detection (statistical, structural, fraud)
    CONSISTENCIA = "consistencia"  # Consistency checks
    DEDUCAO = "deducao"  # Deduction-related
    GERAL = "geral"  # General warnings


class Warning(BaseModel):
    """A warning about potential issues."""

    mensagem: str = Field(..., description="Warning message")
    risco: RiskLevel = Field(default=RiskLevel.LOW)
    campo: Optional[str] = Field(default=None, description="Related field")
    categoria: WarningCategory = Field(
        default=WarningCategory.GERAL,
        description="Category for grouping (padrao, consistencia, etc.)",
    )
    informativo: bool = Field(
        default=False,
        description="If True, shows in output but doesn't count towards risk score",
    )
    valor_impacto: Optional[Decimal] = Field(
        default=None,
        description="Value at stake for weighted score calculation",
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

    Only NEW money counts as resources:
    - renda_declarada: salary, dividends, interest (yields from CDB/LCA already included)
    - ganho_capital: PROFIT from sales (not the sale value - principal was already in patrimony)
    - lucro_acoes_exterior: PROFIT from foreign stocks

    NOT counted (informational only):
    - valor_alienacoes: sale proceeds - principal was already in patrimonio_anterior
    - ativos_liquidados: matured CDB/LCA - principal was already in patrimonio_anterior
    """

    # Patrimony variation
    patrimonio_anterior: Decimal = Field(default=Decimal("0"))
    patrimonio_atual: Decimal = Field(default=Decimal("0"))
    variacao_patrimonial: Decimal = Field(default=Decimal("0"))

    # Income sources (counted in recursos_totais)
    renda_declarada: Decimal = Field(default=Decimal("0"), description="Salary, dividends, interest (incl. CDB/LCA yields)")
    ganho_capital: Decimal = Field(default=Decimal("0"), description="Capital gains from alienations (profit only)")
    lucro_acoes_exterior: Decimal = Field(default=Decimal("0"), description="Profit from foreign stocks")

    # Informational only (NOT counted in recursos_totais - principal already in patrimony)
    valor_alienacoes: Decimal = Field(default=Decimal("0"), description="Sale proceeds (info only, not in recursos)")
    ativos_liquidados: Decimal = Field(default=Decimal("0"), description="Matured CDB/LCA/LCI (info only, not in recursos)")

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
        if self.renda_declarada > Decimal("500000"):
            return 30
        elif self.renda_declarada > Decimal("250000"):
            return 50
        elif self.renda_declarada > Decimal("100000"):
            return 65
        elif self.renda_declarada > Decimal("50000"):
            return 80
        return 100

    @property
    def disclaimer_despesas(self) -> str:
        """Return explanation of how living expenses were calculated."""
        pct = self.percentual_despesas
        return (
            f"Despesas de vida estimadas em {pct}% da renda declarada. "
            f"Faixas: <50k=100%, 50-100k=80%, 100-250k=65%, 250-500k=50%, >500k=30%."
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
