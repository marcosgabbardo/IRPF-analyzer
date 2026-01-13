"""Income models for IRPF declarations."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from irpf_analyzer.core.models.enums import TipoRendimento


class FontePagadora(BaseModel):
    """Payment source (employer, institution, etc.)."""

    cnpj_cpf: str = Field(..., description="CNPJ or CPF of the payment source")
    nome: str = Field(..., description="Name of the payment source")

    model_config = {"frozen": True}


class Rendimento(BaseModel):
    """Income source model."""

    tipo: TipoRendimento = Field(..., description="Type of income")
    fonte_pagadora: Optional[FontePagadora] = Field(
        default=None, description="Payment source information"
    )
    valor_anual: Decimal = Field(..., description="Annual gross value", ge=0)
    imposto_retido: Decimal = Field(
        default=Decimal("0"), description="Withheld income tax", ge=0
    )
    contribuicao_previdenciaria: Decimal = Field(
        default=Decimal("0"), description="Social security contribution", ge=0
    )
    decimo_terceiro: Decimal = Field(
        default=Decimal("0"), description="13th salary (Christmas bonus)", ge=0
    )
    irrf_decimo_terceiro: Decimal = Field(
        default=Decimal("0"), description="Withheld tax on 13th salary", ge=0
    )
    descricao: Optional[str] = Field(default=None, description="Additional description")

    @property
    def valor_liquido(self) -> Decimal:
        """Calculate net income after deductions."""
        return (
            self.valor_anual
            - self.imposto_retido
            - self.contribuicao_previdenciaria
        )

    model_config = {"frozen": True}
