"""Tests for IncomeAnalyzer."""

import pytest
from datetime import date
from decimal import Decimal

from irpf_analyzer.core.analyzers.income import IncomeAnalyzer
from irpf_analyzer.core.models.declaration import Declaration, Contribuinte
from irpf_analyzer.core.models.income import Rendimento, FontePagadora
from irpf_analyzer.core.models.deductions import Deducao
from irpf_analyzer.core.models.enums import TipoDeclaracao, TipoRendimento, TipoDeducao
from irpf_analyzer.core.models.analysis import RiskLevel


def create_minimal_declaration(
    rendimentos=None,
    deducoes=None,
    total_rendimentos_tributaveis=Decimal("0"),
    total_rendimentos_isentos=Decimal("0"),
):
    """Create a minimal declaration for testing."""
    return Declaration(
        contribuinte=Contribuinte(
            cpf="12345678909",
            nome="Teste",
        ),
        ano_exercicio=2025,
        ano_calendario=2024,
        tipo_declaracao=TipoDeclaracao.COMPLETA,
        rendimentos=rendimentos or [],
        deducoes=deducoes or [],
        total_rendimentos_tributaveis=total_rendimentos_tributaveis,
        total_rendimentos_isentos=total_rendimentos_isentos,
    )


class TestIRRFRatioCheck:
    """Tests for IRRF ratio validation."""

    def test_normal_irrf_no_warning(self):
        """Normal IRRF ratio should not trigger warning."""
        rendimentos = [
            Rendimento(
                tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                fonte_pagadora=FontePagadora(cnpj_cpf="12345678000190", nome="Empresa X"),
                valor_anual=Decimal("100000"),
                imposto_retido=Decimal("12000"),  # 12% - within expected
            )
        ]
        decl = create_minimal_declaration(
            rendimentos=rendimentos,
            total_rendimentos_tributaveis=Decimal("100000"),
        )

        analyzer = IncomeAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not have IRRF-related warnings
        irrf_warnings = [w for w in warnings if "IRRF" in w.mensagem]
        assert len(irrf_warnings) == 0

    def test_low_irrf_warning(self):
        """Low IRRF for high income should trigger warning."""
        rendimentos = [
            Rendimento(
                tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                fonte_pagadora=FontePagadora(cnpj_cpf="12345678000190", nome="Empresa X"),
                valor_anual=Decimal("200000"),  # High income
                imposto_retido=Decimal("2000"),  # Only 1% - too low
            )
        ]
        decl = create_minimal_declaration(
            rendimentos=rendimentos,
            total_rendimentos_tributaveis=Decimal("200000"),
        )

        analyzer = IncomeAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should have IRRF-related warning
        irrf_warnings = [w for w in warnings if "IRRF" in w.mensagem.upper()]
        assert len(irrf_warnings) >= 1


class TestIncomeConcentrationCheck:
    """Tests for income concentration analysis."""

    def test_diversified_income_no_warning(self):
        """Diversified income should not trigger concentration warning."""
        rendimentos = [
            Rendimento(
                tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                fonte_pagadora=FontePagadora(cnpj_cpf="11111111000111", nome="Empresa A"),
                valor_anual=Decimal("50000"),
            ),
            Rendimento(
                tipo=TipoRendimento.ALUGUEIS,
                fonte_pagadora=FontePagadora(cnpj_cpf="22222222000122", nome="Inquilino"),
                valor_anual=Decimal("40000"),
            ),
            Rendimento(
                tipo=TipoRendimento.LUCROS_DIVIDENDOS,
                fonte_pagadora=FontePagadora(cnpj_cpf="33333333000133", nome="Empresa X"),
                valor_anual=Decimal("30000"),
            ),
        ]
        decl = create_minimal_declaration(
            rendimentos=rendimentos,
            total_rendimentos_tributaveis=Decimal("120000"),
        )

        analyzer = IncomeAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not have concentration warning with high Gini
        concentration_warnings = [
            w for w in warnings
            if "concentrad" in w.mensagem.lower() and "Gini" in w.mensagem
        ]
        assert len(concentration_warnings) == 0


class TestPrevidenciaVsCLT:
    """Tests for previdência vs CLT income validation."""

    def test_clt_without_previdencia(self):
        """CLT income without previdência should trigger inconsistency."""
        rendimentos = [
            Rendimento(
                tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                fonte_pagadora=FontePagadora(cnpj_cpf="12345678000190", nome="Empresa X"),
                valor_anual=Decimal("100000"),
                contribuicao_previdenciaria=Decimal("0"),  # No INSS
            )
        ]
        decl = create_minimal_declaration(
            rendimentos=rendimentos,
            total_rendimentos_tributaveis=Decimal("100000"),
        )

        analyzer = IncomeAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should have previdência inconsistency
        prev_issues = [
            i for i in inconsistencies
            if "previdenciária" in i.descricao.lower() or "INSS" in i.descricao
        ]
        assert len(prev_issues) >= 1

    def test_clt_with_previdencia(self):
        """CLT income with proper previdência should not trigger warning."""
        rendimentos = [
            Rendimento(
                tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                fonte_pagadora=FontePagadora(cnpj_cpf="12345678000190", nome="Empresa X"),
                valor_anual=Decimal("100000"),
                contribuicao_previdenciaria=Decimal("10000"),  # 10% - reasonable
            )
        ]
        decl = create_minimal_declaration(
            rendimentos=rendimentos,
            total_rendimentos_tributaveis=Decimal("100000"),
        )

        analyzer = IncomeAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not have previdência inconsistency
        prev_issues = [
            i for i in inconsistencies
            if "previdenciária" in i.descricao.lower() or "INSS" in i.descricao
        ]
        assert len(prev_issues) == 0


class TestPensaoProporcionalidade:
    """Tests for alimony proportionality validation."""

    def test_normal_pensao(self):
        """Normal alimony proportion should not trigger inconsistency."""
        deducoes = [
            Deducao(
                tipo=TipoDeducao.PENSAO_ALIMENTICIA,
                valor=Decimal("20000"),  # 20% of income
            )
        ]
        decl = create_minimal_declaration(
            deducoes=deducoes,
            total_rendimentos_tributaveis=Decimal("100000"),
        )

        analyzer = IncomeAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not have pensão inconsistency
        pensao_issues = [
            i for i in inconsistencies
            if "pensão" in i.descricao.lower()
        ]
        assert len(pensao_issues) == 0

    def test_high_pensao(self):
        """Very high alimony should trigger inconsistency."""
        deducoes = [
            Deducao(
                tipo=TipoDeducao.PENSAO_ALIMENTICIA,
                valor=Decimal("60000"),  # 60% of income - too high
            )
        ]
        decl = create_minimal_declaration(
            deducoes=deducoes,
            total_rendimentos_tributaveis=Decimal("100000"),
        )

        analyzer = IncomeAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should have pensão inconsistency
        pensao_issues = [
            i for i in inconsistencies
            if "pensão" in i.descricao.lower()
        ]
        assert len(pensao_issues) >= 1


class TestLivroCaixaValidation:
    """Tests for livro-caixa validation."""

    def test_livro_caixa_without_autonomo(self):
        """Livro-caixa without autonomous income should trigger inconsistency."""
        deducoes = [
            Deducao(
                tipo=TipoDeducao.LIVRO_CAIXA,
                valor=Decimal("30000"),
            )
        ]
        rendimentos = [
            Rendimento(
                tipo=TipoRendimento.TRABALHO_ASSALARIADO,  # CLT, not autonomous
                fonte_pagadora=FontePagadora(cnpj_cpf="12345678000190", nome="Empresa"),
                valor_anual=Decimal("100000"),
            )
        ]
        decl = create_minimal_declaration(
            rendimentos=rendimentos,
            deducoes=deducoes,
            total_rendimentos_tributaveis=Decimal("100000"),
        )

        analyzer = IncomeAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should have livro-caixa inconsistency
        lc_issues = [
            i for i in inconsistencies
            if "livro-caixa" in i.descricao.lower() or "autônomo" in i.descricao.lower()
        ]
        assert len(lc_issues) >= 1

    def test_livro_caixa_with_autonomo(self):
        """Livro-caixa with proper autonomous income should not trigger error."""
        deducoes = [
            Deducao(
                tipo=TipoDeducao.LIVRO_CAIXA,
                valor=Decimal("30000"),
            )
        ]
        rendimentos = [
            Rendimento(
                tipo=TipoRendimento.TRABALHO_NAO_ASSALARIADO,  # Autonomous
                fonte_pagadora=FontePagadora(cnpj_cpf="12345678000190", nome="Cliente"),
                valor_anual=Decimal("100000"),
            )
        ]
        decl = create_minimal_declaration(
            rendimentos=rendimentos,
            deducoes=deducoes,
            total_rendimentos_tributaveis=Decimal("100000"),
        )

        analyzer = IncomeAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not have livro-caixa inconsistency
        lc_issues = [
            i for i in inconsistencies
            if "livro-caixa" in i.descricao.lower() and "sem rendimentos" in i.descricao.lower()
        ]
        assert len(lc_issues) == 0


class TestDecimoTerceiroConsistency:
    """Tests for 13th salary consistency."""

    def test_normal_decimo_terceiro(self):
        """Normal 13th salary should not trigger warning."""
        rendimentos = [
            Rendimento(
                tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                fonte_pagadora=FontePagadora(cnpj_cpf="12345678000190", nome="Empresa"),
                valor_anual=Decimal("120000"),
                decimo_terceiro=Decimal("10000"),  # ~8.3% - expected
            )
        ]
        decl = create_minimal_declaration(
            rendimentos=rendimentos,
            total_rendimentos_tributaveis=Decimal("120000"),
        )

        analyzer = IncomeAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should not have 13th salary warning
        dt_warnings = [
            w for w in warnings
            if "13" in w.mensagem or "terceiro" in w.mensagem.lower()
        ]
        assert len(dt_warnings) == 0
