"""Alienation (sales/disposals) models for IRPF declarations."""

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class Alienacao(BaseModel):
    """Sale/disposal of assets (participações societárias, imóveis, etc.)."""

    nome_bem: str = Field(..., description="Name of the asset sold")
    cnpj: Optional[str] = Field(default=None, description="CNPJ if company shares")
    tipo_operacao: str = Field(default="", description="Type of operation")
    tipo_bem: str = Field(default="", description="Type of asset (QUOTAS, etc.)")
    data_alienacao: Optional[date] = Field(default=None, description="Sale date")
    valor_alienacao: Decimal = Field(default=Decimal("0"), description="Sale value")
    custo_aquisicao: Decimal = Field(default=Decimal("0"), description="Acquisition cost")
    ganho_capital: Decimal = Field(default=Decimal("0"), description="Capital gain")
    imposto_devido: Decimal = Field(default=Decimal("0"), description="Tax due")

    @property
    def tem_ganho(self) -> bool:
        """Check if there was a capital gain."""
        return self.ganho_capital > 0

    @property
    def tem_perda(self) -> bool:
        """Check if there was a capital loss."""
        return self.ganho_capital < 0

    model_config = {"frozen": True}
