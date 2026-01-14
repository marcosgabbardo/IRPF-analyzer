"""Risk analyzer and score calculator for IRPF declarations."""

from typing import Optional

from irpf_analyzer.core.analyzers.consistency import ConsistencyAnalyzer
from irpf_analyzer.core.analyzers.deductions import DeductionAnalyzer
from irpf_analyzer.core.analyzers.optimization import OptimizationAnalyzer
from irpf_analyzer.core.models.analysis import (
    AnalysisResult,
    Inconsistency,
    PatrimonyFlowAnalysis,
    RiskLevel,
    RiskScore,
    Warning,
)
from irpf_analyzer.core.models.declaration import Declaration


class RiskAnalyzer:
    """Main analyzer that aggregates all checks and calculates risk score."""

    # Points added to score per risk level
    RISK_POINTS = {
        RiskLevel.LOW: 5,
        RiskLevel.MEDIUM: 15,
        RiskLevel.HIGH: 30,
        RiskLevel.CRITICAL: 50,
    }

    def __init__(self, declaration: Declaration):
        self.declaration = declaration
        self.inconsistencies: list[Inconsistency] = []
        self.warnings: list[Warning] = []
        self.suggestions: list[Suggestion] = []
        self.patrimony_flow: Optional[PatrimonyFlowAnalysis] = None

    def analyze(self) -> AnalysisResult:
        """Run complete analysis and return result."""
        # Run all sub-analyzers
        self._run_consistency_analysis()
        self._run_deduction_analysis()

        # Generate optimization suggestions
        self._run_optimization_analysis()

        # Calculate final risk score
        risk_score = self._calculate_score()

        return AnalysisResult(
            risk_score=risk_score,
            inconsistencies=self.inconsistencies,
            warnings=self.warnings,
            suggestions=self.suggestions,
            patrimony_flow=self.patrimony_flow,
        )

    def _run_consistency_analysis(self) -> None:
        """Run consistency checks."""
        analyzer = ConsistencyAnalyzer(self.declaration)
        inconsistencies, warnings = analyzer.analyze()
        self.inconsistencies.extend(inconsistencies)
        self.warnings.extend(warnings)
        # Capture patrimony flow analysis for reporting
        self.patrimony_flow = analyzer.get_patrimony_flow()

    def _run_deduction_analysis(self) -> None:
        """Run deduction checks."""
        analyzer = DeductionAnalyzer(self.declaration)
        inconsistencies, warnings = analyzer.analyze()
        self.inconsistencies.extend(inconsistencies)
        self.warnings.extend(warnings)

    def _run_optimization_analysis(self) -> None:
        """Run optimization analysis and collect suggestions."""
        analyzer = OptimizationAnalyzer(self.declaration)
        suggestions = analyzer.analyze()
        self.suggestions.extend(suggestions)

    def _calculate_score(self) -> RiskScore:
        """Calculate compliance score from 100 (safe) to 0 (high risk).

        Higher score = lower risk of being flagged for audit.
        """
        score = 100  # Start at maximum (fully compliant)
        fatores: list[str] = []

        # Subtract points for inconsistencies
        for inconsistency in self.inconsistencies:
            points = self.RISK_POINTS.get(inconsistency.risco, 10)
            score -= points
            fatores.append(f"{inconsistency.tipo.value}: -{points} pts")

        # Subtract points for warnings (half weight), skip informative ones
        for warning in self.warnings:
            if warning.informativo:
                continue  # Don't count informative warnings in score
            points = self.RISK_POINTS.get(warning.risco, 5) // 2
            score -= points
            if warning.campo:
                fatores.append(f"Aviso em {warning.campo}: -{points} pts")

        # Perfect score message
        if not self.inconsistencies and not any(
            not w.informativo for w in self.warnings
        ):
            fatores.append("Nenhuma inconsistência detectada - declaração conforme")

        return RiskScore.from_score(score, fatores)


def analyze_declaration(declaration: Declaration) -> AnalysisResult:
    """Convenience function to analyze a declaration."""
    analyzer = RiskAnalyzer(declaration)
    return analyzer.analyze()
