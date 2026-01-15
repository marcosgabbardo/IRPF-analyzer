"""Analysis engines for IRPF declarations."""

from irpf_analyzer.core.analyzers.advanced_patterns import (
    AdvancedPatternDetector,
    analyze_advanced_patterns,
)
from irpf_analyzer.core.analyzers.autonomous_professional import (
    AutonomousProfessionalAnalyzer,
    analyze_autonomous_professional,
)
from irpf_analyzer.core.analyzers.consistency import ConsistencyAnalyzer
from irpf_analyzer.core.analyzers.cryptocurrency import (
    CryptocurrencyAnalyzer,
    analyze_cryptocurrency,
)
from irpf_analyzer.core.analyzers.deductions import DeductionAnalyzer
from irpf_analyzer.core.analyzers.estate_planning import (
    BrazilianState,
    EstatePlanningAnalyzer,
    analyze_estate_planning,
    get_itcmd_rate,
    list_states_by_lowest_rate,
)
from irpf_analyzer.core.analyzers.expatriate import (
    ExpatriateAnalyzer,
    analyze_expatriate,
)
from irpf_analyzer.core.analyzers.investment_optimization import (
    InvestmentOptimizationAnalyzer,
    analyze_investment_optimization,
)
from irpf_analyzer.core.analyzers.legislation_alerts import (
    LegislationAlertsAnalyzer,
    analyze_legislation,
)
from irpf_analyzer.core.analyzers.optimization import (
    OptimizationAnalyzer,
    analyze_optimization,
)
from irpf_analyzer.core.analyzers.patterns import PatternAnalyzer, analyze_patterns
from irpf_analyzer.core.analyzers.risk import RiskAnalyzer, analyze_declaration
from irpf_analyzer.core.analyzers.specific_cross_validations import (
    SpecificCrossValidationAnalyzer,
    analyze_specific_cross_validations,
)
from irpf_analyzer.core.analyzers.temporal import (
    TemporalPattern,
    TemporalPatternAnalyzer,
    analyze_temporal_patterns,
)

__all__ = [
    "AdvancedPatternDetector",
    "AutonomousProfessionalAnalyzer",
    "BrazilianState",
    "ConsistencyAnalyzer",
    "CryptocurrencyAnalyzer",
    "DeductionAnalyzer",
    "EstatePlanningAnalyzer",
    "ExpatriateAnalyzer",
    "InvestmentOptimizationAnalyzer",
    "LegislationAlertsAnalyzer",
    "OptimizationAnalyzer",
    "PatternAnalyzer",
    "RiskAnalyzer",
    "SpecificCrossValidationAnalyzer",
    "TemporalPatternAnalyzer",
    "TemporalPattern",
    "analyze_advanced_patterns",
    "analyze_autonomous_professional",
    "analyze_cryptocurrency",
    "analyze_declaration",
    "analyze_estate_planning",
    "analyze_expatriate",
    "analyze_investment_optimization",
    "analyze_legislation",
    "analyze_optimization",
    "analyze_patterns",
    "analyze_specific_cross_validations",
    "analyze_temporal_patterns",
    "get_itcmd_rate",
    "list_states_by_lowest_rate",
]
