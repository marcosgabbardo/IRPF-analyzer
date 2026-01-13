"""Risk analyzer and score calculator for IRPF declarations."""

from irpf_analyzer.core.analyzers.consistency import ConsistencyAnalyzer
from irpf_analyzer.core.analyzers.deductions import DeductionAnalyzer
from irpf_analyzer.core.models.analysis import (
    AnalysisResult,
    Inconsistency,
    RiskLevel,
    RiskScore,
    Suggestion,
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

    def analyze(self) -> AnalysisResult:
        """Run complete analysis and return result."""
        # Run all sub-analyzers
        self._run_consistency_analysis()
        self._run_deduction_analysis()

        # Generate optimization suggestions
        self._generate_suggestions()

        # Calculate final risk score
        risk_score = self._calculate_score()

        return AnalysisResult(
            risk_score=risk_score,
            inconsistencies=self.inconsistencies,
            warnings=self.warnings,
            suggestions=self.suggestions,
        )

    def _run_consistency_analysis(self) -> None:
        """Run consistency checks."""
        analyzer = ConsistencyAnalyzer(self.declaration)
        inconsistencies, warnings = analyzer.analyze()
        self.inconsistencies.extend(inconsistencies)
        self.warnings.extend(warnings)

    def _run_deduction_analysis(self) -> None:
        """Run deduction checks."""
        analyzer = DeductionAnalyzer(self.declaration)
        inconsistencies, warnings = analyzer.analyze()
        self.inconsistencies.extend(inconsistencies)
        self.warnings.extend(warnings)

    def _generate_suggestions(self) -> None:
        """Generate optimization suggestions based on declaration data."""
        from decimal import Decimal
        from irpf_analyzer.core.models.enums import TipoDeclaracao

        renda_tributavel = self.declaration.total_rendimentos_tributaveis

        # Calculate actual deductions from itemized list (more reliable than total_deducoes)
        total_deducoes_real = sum(d.valor for d in self.declaration.deducoes)

        # Sanity check: skip suggestions if income data looks unreliable
        # (very high values indicate parsing issues)
        income_looks_valid = Decimal("0") < renda_tributavel < Decimal("10000000")

        # Suggestion: Compare simplified vs complete declaration
        if self.declaration.tipo_declaracao == TipoDeclaracao.COMPLETA:
            if income_looks_valid:
                # Simplified uses 20% discount, capped at ~16,754.34 (2024)
                desconto_simplificado = min(
                    renda_tributavel * Decimal("0.20"),
                    Decimal("16754.34")
                )

                if desconto_simplificado > total_deducoes_real:
                    economia = desconto_simplificado - total_deducoes_real
                    self.suggestions.append(
                        Suggestion(
                            titulo="Considere declaração simplificada",
                            descricao=(
                                f"Desconto simplificado (R$ {desconto_simplificado:,.2f}) "
                                f"é maior que suas deduções (R$ {total_deducoes_real:,.2f})"
                            ),
                            economia_potencial=economia,
                            prioridade=1,
                        )
                    )
            else:
                # Income not parsed - suggest based on deductions alone
                if total_deducoes_real < Decimal("16754.34"):
                    self.suggestions.append(
                        Suggestion(
                            titulo="Considere declaração simplificada",
                            descricao=(
                                f"Suas deduções (R$ {total_deducoes_real:,.2f}) são menores que "
                                f"o desconto máximo simplificado (R$ 16.754,34)"
                            ),
                            economia_potencial=None,
                            prioridade=1,
                        )
                    )

        # Suggestion: PGBL contribution (only if income looks valid)
        if income_looks_valid and renda_tributavel > Decimal("50000"):
            limite_pgbl = renda_tributavel * Decimal("0.12")
            resumo = self.declaration.resumo_deducoes
            pgbl_usado = resumo.previdencia_privada

            if pgbl_usado < limite_pgbl:
                disponivel = limite_pgbl - pgbl_usado
                economia_estimada = disponivel * Decimal("0.275")  # Max bracket

                self.suggestions.append(
                    Suggestion(
                        titulo="Oportunidade: PGBL",
                        descricao=(
                            f"Você pode deduzir até R$ {limite_pgbl:,.2f} em PGBL "
                            f"(12% da renda bruta). Espaço disponível: R$ {disponivel:,.2f}"
                        ),
                        economia_potencial=economia_estimada,
                        prioridade=2,
                    )
                )

    def _calculate_score(self) -> RiskScore:
        """Calculate risk score from 0 (safe) to 100 (high risk)."""
        score = 0
        fatores: list[str] = []

        # Add points for inconsistencies
        for inconsistency in self.inconsistencies:
            points = self.RISK_POINTS.get(inconsistency.risco, 10)
            score += points
            fatores.append(f"{inconsistency.tipo.value}: +{points} pts")

        # Add points for warnings (half weight), skip informative ones
        for warning in self.warnings:
            if warning.informativo:
                continue  # Don't count informative warnings in score
            points = self.RISK_POINTS.get(warning.risco, 5) // 2
            score += points
            if warning.campo:
                fatores.append(f"Aviso em {warning.campo}: +{points} pts")

        # Base score adjustments
        if not self.inconsistencies and not self.warnings:
            fatores.append("Nenhuma inconsistência detectada")

        return RiskScore.from_score(score, fatores)


def analyze_declaration(declaration: Declaration) -> AnalysisResult:
    """Convenience function to analyze a declaration."""
    analyzer = RiskAnalyzer(declaration)
    return analyzer.analyze()
