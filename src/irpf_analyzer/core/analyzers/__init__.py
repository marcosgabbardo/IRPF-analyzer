"""Analysis engines for IRPF declarations."""

from irpf_analyzer.core.analyzers.advanced_patterns import (
    AdvancedPatternDetector,
    analyze_advanced_patterns,
)
from irpf_analyzer.core.analyzers.consistency import ConsistencyAnalyzer
from irpf_analyzer.core.analyzers.cryptocurrency import (
    CryptocurrencyAnalyzer,
    analyze_cryptocurrency,
)
from irpf_analyzer.core.analyzers.deductions import DeductionAnalyzer
from irpf_analyzer.core.analyzers.investment_optimization import (
    InvestmentOptimizationAnalyzer,
    analyze_investment_optimization,
)
from irpf_analyzer.core.analyzers.optimization import (
    OptimizationAnalyzer,
    analyze_optimization,
)
from irpf_analyzer.core.analyzers.patterns import PatternAnalyzer, analyze_patterns
from irpf_analyzer.core.analyzers.risk import RiskAnalyzer, analyze_declaration
from irpf_analyzer.core.analyzers.temporal import (
    TemporalPatternAnalyzer,
    TemporalPattern,
    analyze_temporal_patterns,
)

__all__ = [
    "AdvancedPatternDetector",
    "ConsistencyAnalyzer",
    "CryptocurrencyAnalyzer",
    "DeductionAnalyzer",
    "InvestmentOptimizationAnalyzer",
    "OptimizationAnalyzer",
    "PatternAnalyzer",
    "RiskAnalyzer",
    "TemporalPatternAnalyzer",
    "TemporalPattern",
    "analyze_advanced_patterns",
    "analyze_cryptocurrency",
    "analyze_declaration",
    "analyze_investment_optimization",
    "analyze_optimization",
    "analyze_patterns",
    "analyze_temporal_patterns",
]
