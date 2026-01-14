"""Tests for optimization analyzer."""

from decimal import Decimal

import pytest

from irpf_analyzer.core.analyzers.optimization import (
    OptimizationAnalyzer,
    analyze_optimization,
)
from irpf_analyzer.core.models import (
    Declaration,
    Deducao,
    Rendimento,
    TipoDeclaracao,
    TipoDeducao,
)
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.enums import TipoRendimento
from irpf_analyzer.core.rules.tax_constants import (
    LIMITE_EDUCACAO_PESSOA,
    LIMITE_PGBL_PERCENTUAL,
    LIMITE_SIMPLIFICADA,
)


class TestOptimizationAnalyzer:
    """Tests for OptimizationAnalyzer."""

    def test_suggests_simplified_when_better(self):
        """Test suggestion to use simplified declaration when deductions are low."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("5000"),
                    nome_prestador="Hospital",
                )
            ],
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # With 5k deductions vs 16.7k simplified discount, should suggest simplified
        simplified_suggestions = [s for s in suggestions if "simplificada" in s.titulo.lower()]
        assert len(simplified_suggestions) > 0

    def test_no_simplified_suggestion_when_deductions_high(self):
        """Test no simplified suggestion when deductions exceed simplified discount."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("20000"),
                    nome_prestador="Hospital",
                ),
                Deducao(
                    tipo=TipoDeducao.PREVIDENCIA_PRIVADA,
                    valor=Decimal("10000"),
                    cnpj_prestador="11222333000181",
                    nome_prestador="PGBL Fund",
                ),
            ],
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # With 30k deductions vs 16.7k simplified discount, should NOT suggest simplified
        simplified_suggestions = [s for s in suggestions if "simplificada" in s.titulo.lower()]
        assert len(simplified_suggestions) == 0

    def test_suggests_complete_when_simplified_is_worse(self):
        """Test suggestion to switch to complete when deductions are high."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.SIMPLIFICADA,
            total_rendimentos_tributaveis=Decimal("100000"),
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("25000"),
                    nome_prestador="Hospital",
                )
            ],
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # With 25k deductions vs 16.7k simplified, should suggest complete
        complete_suggestions = [s for s in suggestions if "completa" in s.titulo.lower()]
        assert len(complete_suggestions) > 0

    def test_suggests_pgbl_opportunity(self):
        """Test PGBL suggestion when there's room for contribution."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("200000"),  # High income
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.PREVIDENCIA_PRIVADA,
                    valor=Decimal("5000"),  # Only 5k of 24k possible (12%)
                    cnpj_prestador="11222333000181",
                    nome_prestador="PGBL Fund",
                )
            ],
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # Should suggest PGBL with 19k available space
        pgbl_suggestions = [s for s in suggestions if "pgbl" in s.titulo.lower()]
        assert len(pgbl_suggestions) > 0
        assert pgbl_suggestions[0].economia_potencial > 0

    def test_no_pgbl_suggestion_when_maxed(self):
        """Test no PGBL suggestion when already at limit."""
        income = Decimal("100000")
        pgbl_limit = income * LIMITE_PGBL_PERCENTUAL

        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=income,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.PREVIDENCIA_PRIVADA,
                    valor=pgbl_limit,  # Already at 12%
                    cnpj_prestador="11222333000181",
                    nome_prestador="PGBL Fund",
                )
            ],
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # Should NOT suggest PGBL when already maxed
        pgbl_suggestions = [s for s in suggestions if "pgbl" in s.titulo.lower()]
        assert len(pgbl_suggestions) == 0

    def test_no_pgbl_suggestion_for_low_income(self):
        """Test no PGBL suggestion for low income (simplified likely better)."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("30000"),  # Low income
            deducoes=[],
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # Should NOT suggest PGBL for low income
        pgbl_suggestions = [s for s in suggestions if "pgbl" in s.titulo.lower()]
        assert len(pgbl_suggestions) == 0

    def test_suggests_incentive_donations(self):
        """Test suggestion for incentive donations when tax is owed."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("200000"),
            imposto_devido=Decimal("30000"),  # Owes tax
            deducoes=[],
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # Should suggest donations (6% of 30k = 1.8k available)
        donation_suggestions = [s for s in suggestions if "doações" in s.titulo.lower()]
        assert len(donation_suggestions) > 0

    def test_no_donation_suggestion_when_no_tax(self):
        """Test no donation suggestion when no tax is owed."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("50000"),
            imposto_devido=Decimal("0"),  # No tax owed
            deducoes=[],
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # Should NOT suggest donations when no tax owed
        donation_suggestions = [s for s in suggestions if "doações" in s.titulo.lower()]
        assert len(donation_suggestions) == 0

    def test_suggests_livro_caixa_for_self_employed(self):
        """Test livro-caixa suggestion for self-employed without deductions."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_NAO_ASSALARIADO,
                    valor_anual=Decimal("80000"),
                    fonte_pagadora_cnpj_cpf="",
                    fonte_pagadora_nome="Diversos",
                )
            ],
            deducoes=[],  # No livro-caixa
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # Should suggest livro-caixa
        livro_suggestions = [s for s in suggestions if "livro-caixa" in s.titulo.lower()]
        assert len(livro_suggestions) > 0

    def test_skips_analysis_for_invalid_income(self):
        """Test that analysis is skipped when income is invalid (parsing issues)."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("50000000000"),  # 50 billion - invalid
            deducoes=[],
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # Should return empty list for invalid data
        assert len(suggestions) == 0

    def test_suggestions_sorted_by_priority(self):
        """Test that suggestions are sorted by priority (1 = highest)."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("200000"),
            imposto_devido=Decimal("30000"),
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_NAO_ASSALARIADO,
                    valor_anual=Decimal("50000"),
                    fonte_pagadora_cnpj_cpf="",
                    fonte_pagadora_nome="Diversos",
                )
            ],
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("5000"),
                    nome_prestador="Hospital",
                )
            ],
        )

        analyzer = OptimizationAnalyzer(decl)
        suggestions = analyzer.analyze()

        # Should be sorted by priority (ascending - 1 is highest priority)
        priorities = [s.prioridade for s in suggestions]
        assert priorities == sorted(priorities)


class TestAnalyzeOptimizationFunction:
    """Tests for the convenience function."""

    def test_analyze_optimization_returns_suggestions(self):
        """Test that analyze_optimization returns suggestions list."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            deducoes=[],
        )

        suggestions = analyze_optimization(decl)

        assert isinstance(suggestions, list)
        # With 100k income and 0 deductions, should suggest simplified
        assert any("simplificada" in s.titulo.lower() for s in suggestions)


class TestTaxConstants:
    """Tests for tax constants."""

    def test_simplified_limit_value(self):
        """Test simplified declaration limit is correct."""
        assert LIMITE_SIMPLIFICADA == Decimal("16754.34")

    def test_education_limit_value(self):
        """Test education limit per person is correct."""
        assert LIMITE_EDUCACAO_PESSOA == Decimal("3561.50")

    def test_pgbl_percentage(self):
        """Test PGBL percentage limit is correct."""
        assert LIMITE_PGBL_PERCENTUAL == Decimal("0.12")
