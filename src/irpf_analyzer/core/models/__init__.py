"""Domain models for IRPF declarations."""

from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import TipoDeclaracao, TipoRendimento, TipoDeducao, GrupoBem
from irpf_analyzer.core.models.income import Rendimento, FontePagadora
from irpf_analyzer.core.models.deductions import Deducao
from irpf_analyzer.core.models.patrimony import BemDireito
from irpf_analyzer.core.models.dependents import Dependente
from irpf_analyzer.core.models.analysis import (
    AnalysisResult,
    RiskScore,
    RiskLevel,
    Inconsistency,
    Warning,
    WarningCategory,
    Suggestion,
)
from irpf_analyzer.core.models.checklist import (
    Document,
    DocumentCategory,
    DocumentChecklist,
    DocumentPriority,
)

__all__ = [
    "Declaration",
    "TipoDeclaracao",
    "TipoRendimento",
    "TipoDeducao",
    "GrupoBem",
    "Rendimento",
    "FontePagadora",
    "Deducao",
    "BemDireito",
    "Dependente",
    "AnalysisResult",
    "RiskScore",
    "RiskLevel",
    "Inconsistency",
    "Warning",
    "WarningCategory",
    "Suggestion",
    "Document",
    "DocumentCategory",
    "DocumentChecklist",
    "DocumentPriority",
]
