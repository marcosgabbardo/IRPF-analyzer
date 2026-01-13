"""Tests for domain models."""

from decimal import Decimal

import pytest

from irpf_analyzer.core.models import (
    Declaration,
    Rendimento,
    Deducao,
    BemDireito,
    Dependente,
    TipoDeclaracao,
    TipoRendimento,
    TipoDeducao,
    GrupoBem,
)
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.income import FontePagadora
from irpf_analyzer.core.models.enums import TipoDependente


class TestContribuinte:
    """Tests for Contribuinte model."""

    def test_valid_contribuinte(self):
        """Test creating a valid contribuinte."""
        contrib = Contribuinte(
            cpf="52998224725",
            nome="João da Silva",
        )
        assert contrib.cpf == "52998224725"
        assert contrib.nome == "João da Silva"

    def test_cpf_strips_formatting(self):
        """Test that CPF formatting is stripped."""
        contrib = Contribuinte(
            cpf="529.982.247-25",
            nome="João",
        )
        assert contrib.cpf == "52998224725"

    def test_invalid_cpf_raises(self):
        """Test that invalid CPF raises validation error."""
        with pytest.raises(ValueError, match="11 dígitos"):
            Contribuinte(cpf="123", nome="João")


class TestRendimento:
    """Tests for Rendimento model."""

    def test_rendimento_creation(self):
        """Test creating a rendimento."""
        rend = Rendimento(
            tipo=TipoRendimento.TRABALHO_ASSALARIADO,
            valor_anual=Decimal("120000.00"),
            imposto_retido=Decimal("15000.00"),
        )
        assert rend.valor_anual == Decimal("120000.00")
        assert rend.tipo == TipoRendimento.TRABALHO_ASSALARIADO

    def test_valor_liquido_calculation(self):
        """Test net value calculation."""
        rend = Rendimento(
            tipo=TipoRendimento.TRABALHO_ASSALARIADO,
            valor_anual=Decimal("100000"),
            imposto_retido=Decimal("10000"),
            contribuicao_previdenciaria=Decimal("5000"),
        )
        assert rend.valor_liquido == Decimal("85000")

    def test_rendimento_with_fonte_pagadora(self):
        """Test rendimento with payment source."""
        fonte = FontePagadora(cnpj_cpf="11222333000181", nome="Empresa XPTO")
        rend = Rendimento(
            tipo=TipoRendimento.TRABALHO_ASSALARIADO,
            valor_anual=Decimal("100000"),
            fonte_pagadora=fonte,
        )
        assert rend.fonte_pagadora.nome == "Empresa XPTO"


class TestBemDireito:
    """Tests for BemDireito model."""

    def test_variacao_absoluta(self):
        """Test absolute variation calculation."""
        bem = BemDireito(
            grupo=GrupoBem.IMOVEIS,
            codigo="01",
            discriminacao="Apartamento",
            situacao_anterior=Decimal("300000"),
            situacao_atual=Decimal("350000"),
        )
        assert bem.variacao_absoluta == Decimal("50000")

    def test_variacao_percentual(self):
        """Test percentage variation calculation."""
        bem = BemDireito(
            grupo=GrupoBem.VEICULOS,
            codigo="01",
            discriminacao="Carro",
            situacao_anterior=Decimal("100000"),
            situacao_atual=Decimal("120000"),
        )
        assert bem.variacao_percentual == Decimal("20")

    def test_variacao_percentual_from_zero(self):
        """Test percentage variation when starting from zero."""
        bem = BemDireito(
            grupo=GrupoBem.APLICACOES_FINANCEIRAS,
            codigo="01",
            discriminacao="CDB",
            situacao_anterior=Decimal("0"),
            situacao_atual=Decimal("10000"),
        )
        assert bem.variacao_percentual == Decimal("100")


class TestDeclaration:
    """Tests for Declaration model."""

    def test_declaration_creation(self):
        """Test creating a full declaration."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="João"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
            total_rendimentos_tributaveis=Decimal("150000"),
            imposto_devido=Decimal("20000"),
            imposto_pago=Decimal("22000"),
            saldo_imposto=Decimal("-2000"),
        )
        assert decl.tem_restituicao is True
        assert decl.valor_restituicao == Decimal("2000")
        assert decl.valor_a_pagar == Decimal("0")

    def test_declaration_to_pay(self):
        """Test declaration with amount to pay."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="João"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.SIMPLIFICADA,
            saldo_imposto=Decimal("5000"),
        )
        assert decl.tem_restituicao is False
        assert decl.valor_restituicao == Decimal("0")
        assert decl.valor_a_pagar == Decimal("5000")

    def test_cpf_masked(self):
        """Test CPF masking for display."""
        decl = Declaration(
            contribuinte=Contribuinte(cpf="52998224725", nome="João"),
            ano_exercicio=2025,
            ano_calendario=2024,
            tipo_declaracao=TipoDeclaracao.COMPLETA,
        )
        assert decl.cpf_masked == "***.***.***.25"
