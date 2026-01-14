"""Analysis engines for IRPF declarations."""

from irpf_analyzer.core.analyzers.consistency import ConsistencyAnalyzer
from irpf_analyzer.core.analyzers.deductions import DeductionAnalyzer
from irpf_analyzer.core.analyzers.optimization import (
    OptimizationAnalyzer,
    analyze_optimization,
)
from irpf_analyzer.core.analyzers.risk import RiskAnalyzer, analyze_declaration

__all__ = [
    "ConsistencyAnalyzer",
    "DeductionAnalyzer",
    "OptimizationAnalyzer",
    "RiskAnalyzer",
    "analyze_declaration",
    "analyze_optimization",
]
