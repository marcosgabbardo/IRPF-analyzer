"""Tests for cross-validation analyzer."""

from decimal import Decimal

import pytest

from irpf_analyzer.core.analyzers.cross_validation import (
    CrossValidationAnalyzer,
    analyze_cross_validation,
)
from irpf_analyzer.core.models import (
    Declaration,
    BemDireito,
    Deducao,
    TipoDeclaracao,
    TipoDeducao,
    GrupoBem,
    RiskLevel,
)
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.enums import TipoRendimento
from irpf_analyzer.core.models.income import Rendimento, FontePagadora


class TestDIRFCrossing:
    """Tests for DIRF (employer income) crossing simulation."""

    def test_warns_high_income_no_irrf(self):
        """Test warning for high income without IRRF withheld."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                    fonte_pagadora=FontePagadora(
                        cnpj_cpf="11222333000181",
                        nome="Empresa XYZ",
                    ),
                    valor_anual=Decimal("100000"),
                    imposto_retido=Decimal("0"),  # No IRRF on high income
                )
            ],
        )

        analyzer = CrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        irrf_warnings = [w for w in warnings if "IRRF" in w.mensagem]
        assert len(irrf_warnings) > 0
        assert "DIRF" in irrf_warnings[0].mensagem


class TestDIMOBCrossing:
    """Tests for DIMOB (real estate) crossing simulation."""

    def test_warns_property_above_income(self):
        """Test warning for property acquisition above declared income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("100000"),
            total_rendimentos_isentos=Decimal("0"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="11",  # Apartment
                    discriminacao="Apartamento novo",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("500000"),  # New purchase > income
                )
            ],
        )

        analyzer = CrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        dimob_warnings = [w for w in warnings if "DIMOB" in w.mensagem]
        assert len(dimob_warnings) > 0

    def test_warns_multiple_properties_no_rental(self):
        """Test warning for multiple properties without rental income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="11",
                    discriminacao="Apartamento 1",
                    situacao_anterior=Decimal("300000"),
                    situacao_atual=Decimal("300000"),
                ),
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="12",
                    discriminacao="Casa",
                    situacao_anterior=Decimal("400000"),
                    situacao_atual=Decimal("400000"),
                ),
            ],
            rendimentos=[],  # No rental income
        )

        analyzer = CrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        rental_warnings = [w for w in warnings if "aluguel" in w.mensagem.lower()]
        assert len(rental_warnings) > 0


class TestEFinanceiraCrossing:
    """Tests for e-Financeira (bank reports) crossing simulation."""

    def test_warns_high_financial_vs_income(self):
        """Test warning for high financial assets vs income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("50000"),
            total_rendimentos_isentos=Decimal("0"),
            total_rendimentos_exclusivos=Decimal("0"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.APLICACOES_FINANCEIRAS,
                    codigo="45",
                    discriminacao="Aplicacao CDB",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("500000"),  # 10x income
                ),
            ],
        )

        analyzer = CrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        fin_warnings = [w for w in warnings if "e-Financeira" in w.mensagem]
        assert len(fin_warnings) > 0


class TestDMEDCrossing:
    """Tests for DMED (medical provider) crossing simulation."""

    def test_warns_high_medical_no_provider(self):
        """Test warning for high medical expenses without provider ID."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("10000"),
                    # No cnpj_prestador or cpf_prestador
                ),
            ],
        )

        analyzer = CrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        dmed_warnings = [w for w in warnings if "DMED" in w.mensagem]
        assert len(dmed_warnings) > 0
        # Should warn about missing provider ID
        assert "sem identificação" in dmed_warnings[0].mensagem

    def test_info_warning_high_medical_with_provider(self):
        """Test informative warning for high medical with provider."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            deducoes=[
                Deducao(
                    tipo=TipoDeducao.DESPESAS_MEDICAS,
                    valor=Decimal("8000"),
                    cnpj_prestador="11222333000181",
                ),
            ],
        )

        analyzer = CrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        # Should be informative warning only
        dmed_warnings = [w for w in warnings if "DMED" in w.mensagem]
        assert len(dmed_warnings) > 0
        assert dmed_warnings[0].informativo is True


class TestDECREDExposure:
    """Tests for DECRED (credit card) exposure check."""

    def test_warns_high_patrimony_low_income(self):
        """Test warning for high patrimony with low income."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("80000"),  # Low income
            total_rendimentos_isentos=Decimal("0"),
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.IMOVEIS,
                    codigo="11",
                    discriminacao="Imovel",
                    situacao_anterior=Decimal("1500000"),
                    situacao_atual=Decimal("1500000"),  # High patrimony
                ),
            ],
        )

        analyzer = CrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        decred_warnings = [w for w in warnings if "DECRED" in w.mensagem]
        assert len(decred_warnings) > 0
        assert decred_warnings[0].informativo is True


class TestEmployerConsistency:
    """Tests for employer consistency checks."""

    def test_warns_duplicate_employer_entries(self):
        """Test warning for duplicate income from same employer."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            rendimentos=[
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                    fonte_pagadora=FontePagadora(
                        cnpj_cpf="11222333000181",
                        nome="Empresa XYZ",
                    ),
                    valor_anual=Decimal("50000"),
                ),
                Rendimento(
                    tipo=TipoRendimento.TRABALHO_ASSALARIADO,
                    fonte_pagadora=FontePagadora(
                        cnpj_cpf="11222333000181",  # Same employer
                        nome="Empresa XYZ",
                    ),
                    valor_anual=Decimal("30000"),  # Different value
                ),
            ],
        )

        analyzer = CrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        dup_warnings = [w for w in warnings if "Múltiplas entradas" in w.mensagem]
        assert len(dup_warnings) > 0


class TestAssetAcquisitionDOC:
    """Tests for DOC/TED crossing on asset acquisitions."""

    def test_warns_high_acquisition(self):
        """Test warning for high-value asset acquisition."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            bens_direitos=[
                BemDireito(
                    grupo=GrupoBem.VEICULOS,
                    codigo="21",
                    discriminacao="Carro novo",
                    situacao_anterior=Decimal("0"),
                    situacao_atual=Decimal("100000"),
                ),
            ],
        )

        analyzer = CrossValidationAnalyzer(decl)
        inconsistencies, warnings = analyzer.analyze()

        doc_warnings = [w for w in warnings if "DOC/TED" in w.mensagem]
        assert len(doc_warnings) > 0
        assert doc_warnings[0].informativo is True


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_analyze_cross_validation_returns_tuple(self):
        """Test that analyze_cross_validation returns correct tuple."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="Test"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )

        result = analyze_cross_validation(decl)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)  # inconsistencies
        assert isinstance(result[1], list)  # warnings
