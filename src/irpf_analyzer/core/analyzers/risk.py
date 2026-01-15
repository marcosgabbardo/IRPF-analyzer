"""Risk analyzer and score calculator for IRPF declarations."""

from decimal import Decimal
from typing import Optional

from irpf_analyzer.core.analyzers.consistency import ConsistencyAnalyzer
from irpf_analyzer.core.analyzers.cross_validation import CrossValidationAnalyzer
from irpf_analyzer.core.analyzers.cryptocurrency import CryptocurrencyAnalyzer
from irpf_analyzer.core.analyzers.deductions import DeductionAnalyzer
from irpf_analyzer.core.analyzers.dependent_fraud import DependentFraudAnalyzer
from irpf_analyzer.core.analyzers.income import IncomeAnalyzer
from irpf_analyzer.core.analyzers.optimization import OptimizationAnalyzer
from irpf_analyzer.core.analyzers.patterns import PatternAnalyzer
from irpf_analyzer.core.models.analysis import (
    AnalysisResult,
    Inconsistency,
    PatrimonyFlowAnalysis,
    RiskLevel,
    RiskScore,
    Suggestion,
    Warning,
)
from irpf_analyzer.core.models.declaration import Declaration


class RiskAnalyzer:
    """Main analyzer that aggregates all checks and calculates risk score.

    Score weighting: Issues are weighted by their financial impact relative
    to total patrimony. A R$ 100 error has less impact than a R$ 1,000,000 error.
    """

    # Base points per risk level (before weighting)
    RISK_POINTS = {
        RiskLevel.LOW: 5,
        RiskLevel.MEDIUM: 15,
        RiskLevel.HIGH: 30,
        RiskLevel.CRITICAL: 50,
    }

    # Weight factors based on percentage of patrimony affected
    # percentual = valor_impacto / patrimonio_total
    WEIGHT_THRESHOLDS = [
        (Decimal("0.01"), Decimal("0.2")),   # <= 1%: minimal weight (0.2x)
        (Decimal("0.05"), Decimal("0.5")),   # <= 5%: low weight (0.5x)
        (Decimal("0.10"), Decimal("0.8")),   # <= 10%: medium-low weight (0.8x)
        (Decimal("0.25"), Decimal("1.0")),   # <= 25%: baseline weight (1.0x)
        (Decimal("0.50"), Decimal("1.5")),   # <= 50%: high weight (1.5x)
        (Decimal("1.00"), Decimal("2.0")),   # > 50%: maximum weight (2.0x)
    ]

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
        self._run_income_analysis()
        self._run_pattern_analysis()
        self._run_dependent_fraud_analysis()
        self._run_cross_validation_analysis()
        self._run_cryptocurrency_analysis()

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

    def _run_income_analysis(self) -> None:
        """Run income analysis checks."""
        analyzer = IncomeAnalyzer(self.declaration)
        inconsistencies, warnings = analyzer.analyze()
        self.inconsistencies.extend(inconsistencies)
        self.warnings.extend(warnings)

    def _run_pattern_analysis(self) -> None:
        """Run pattern analysis for suspicious patterns."""
        analyzer = PatternAnalyzer(self.declaration)
        inconsistencies, warnings = analyzer.analyze()
        self.inconsistencies.extend(inconsistencies)
        self.warnings.extend(warnings)

    def _run_dependent_fraud_analysis(self) -> None:
        """Run dependent fraud analysis."""
        analyzer = DependentFraudAnalyzer(self.declaration)
        inconsistencies, warnings = analyzer.analyze()
        self.inconsistencies.extend(inconsistencies)
        self.warnings.extend(warnings)

    def _run_cross_validation_analysis(self) -> None:
        """Run cross-validation analysis simulating Receita Federal crossings."""
        analyzer = CrossValidationAnalyzer(self.declaration)
        inconsistencies, warnings = analyzer.analyze()
        self.inconsistencies.extend(inconsistencies)
        self.warnings.extend(warnings)

    def _run_cryptocurrency_analysis(self) -> None:
        """Run cryptocurrency analysis per IN RFB 1888/2019."""
        analyzer = CryptocurrencyAnalyzer(self.declaration)
        inconsistencies, warnings = analyzer.analyze()
        self.inconsistencies.extend(inconsistencies)
        self.warnings.extend(warnings)

    def _run_optimization_analysis(self) -> None:
        """Run optimization analysis and collect suggestions."""
        analyzer = OptimizationAnalyzer(self.declaration)
        suggestions = analyzer.analyze()
        self.suggestions.extend(suggestions)

    def _get_weight_factor(self, valor_impacto: Optional[Decimal]) -> Decimal:
        """Calculate weight factor based on valor_impacto / patrimonio.

        Higher impact relative to patrimony = higher weight factor.
        Returns 1.0 (baseline) if valor_impacto is not set.
        """
        if not valor_impacto or valor_impacto <= 0:
            return Decimal("1.0")  # Baseline weight if no value specified

        patrimonio = self.declaration.resumo_patrimonio.total_bens_atual
        if patrimonio <= 0:
            return Decimal("1.0")  # Baseline if no patrimony

        percentual = abs(valor_impacto) / patrimonio

        # Find the appropriate weight factor
        for threshold, weight in self.WEIGHT_THRESHOLDS:
            if percentual <= threshold:
                return weight

        return Decimal("2.0")  # Maximum weight for > 100%

    def _calculate_score(self) -> RiskScore:
        """Calculate compliance score from 100 (safe) to 0 (high risk).

        Higher score = lower risk of being flagged for audit.
        Points are weighted by financial impact relative to total patrimony.
        """
        score = Decimal("100")  # Start at maximum (fully compliant)
        fatores: list[str] = []

        # Subtract points for inconsistencies (weighted by impact)
        for inconsistency in self.inconsistencies:
            base_points = self.RISK_POINTS.get(inconsistency.risco, 10)
            weight = self._get_weight_factor(inconsistency.valor_impacto)
            weighted_points = Decimal(str(base_points)) * weight
            score -= weighted_points

            # Format factor description
            if inconsistency.valor_impacto:
                pct = (inconsistency.valor_impacto / self.declaration.resumo_patrimonio.total_bens_atual * 100
                       if self.declaration.resumo_patrimonio.total_bens_atual > 0 else Decimal("0"))
                fatores.append(
                    f"{inconsistency.tipo.value}: -{weighted_points:.1f} pts "
                    f"(R$ {inconsistency.valor_impacto:,.0f} = {pct:.1f}% do patrimônio)"
                )
            else:
                fatores.append(f"{inconsistency.tipo.value}: -{weighted_points:.0f} pts")

        # Subtract points for warnings (half base weight), skip informative ones
        for warning in self.warnings:
            if warning.informativo:
                continue  # Don't count informative warnings in score
            base_points = self.RISK_POINTS.get(warning.risco, 5) // 2
            weight = self._get_weight_factor(warning.valor_impacto)
            weighted_points = Decimal(str(base_points)) * weight
            score -= weighted_points

            if warning.campo:
                if warning.valor_impacto:
                    fatores.append(f"Aviso em {warning.campo}: -{weighted_points:.1f} pts")
                else:
                    fatores.append(f"Aviso em {warning.campo}: -{weighted_points:.0f} pts")

        # Perfect score message
        if not self.inconsistencies and not any(
            not w.informativo for w in self.warnings
        ):
            fatores.append("Nenhuma inconsistência detectada - declaração conforme")

        return RiskScore.from_score(int(score), fatores)


def analyze_declaration(declaration: Declaration) -> AnalysisResult:
    """Convenience function to analyze a declaration."""
    analyzer = RiskAnalyzer(declaration)
    return analyzer.analyze()
