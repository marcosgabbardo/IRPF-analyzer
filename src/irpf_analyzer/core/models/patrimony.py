"""Patrimony (assets) models for IRPF declarations."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from irpf_analyzer.core.models.enums import GrupoBem


class Localizacao(BaseModel):
    """Location information for assets."""

    pais: str = Field(default="105", description="Country code (105 = Brazil)")
    uf: Optional[str] = Field(default=None, description="State code")
    municipio: Optional[str] = Field(default=None, description="Municipality code")

    model_config = {"frozen": True}


class BemDireito(BaseModel):
    """Asset/property model (Bens e Direitos)."""

    grupo: GrupoBem = Field(..., description="Asset group")
    codigo: str = Field(..., description="Asset code within group")
    discriminacao: str = Field(..., description="Asset description")
    situacao_anterior: Decimal = Field(
        ..., description="Value on Dec 31 of previous year", ge=0
    )
    situacao_atual: Decimal = Field(
        ..., description="Value on Dec 31 of current year", ge=0
    )
    lucro_prejuizo: Decimal = Field(
        default=Decimal("0"),
        description="Profit/loss from financial application (used for foreign stocks)",
    )
    localizacao: Optional[Localizacao] = Field(
        default=None, description="Asset location"
    )
    cnpj_instituicao: Optional[str] = Field(
        default=None, description="CNPJ of financial institution"
    )

    @property
    def variacao_absoluta(self) -> Decimal:
        """Calculate absolute year-over-year variation."""
        return self.situacao_atual - self.situacao_anterior

    @property
    def variacao_percentual(self) -> Decimal:
        """Calculate percentage year-over-year variation."""
        if self.situacao_anterior == 0:
            return Decimal("100") if self.situacao_atual > 0 else Decimal("0")
        return ((self.situacao_atual - self.situacao_anterior) / self.situacao_anterior) * 100

    @property
    def tem_lucro_prejuizo_declarado(self) -> bool:
        """Check if profit/loss was declared for this asset."""
        return self.lucro_prejuizo != Decimal("0")

    model_config = {"frozen": True}


class Divida(BaseModel):
    """Debt model (Dívidas e Ônus Reais)."""

    codigo: str = Field(..., description="Debt type code")
    discriminacao: str = Field(..., description="Debt description")
    situacao_anterior: Decimal = Field(
        ..., description="Balance on Dec 31 of previous year", ge=0
    )
    situacao_atual: Decimal = Field(
        ..., description="Balance on Dec 31 of current year", ge=0
    )
    valor_pago_ano: Decimal = Field(
        default=Decimal("0"), description="Amount paid during the year", ge=0
    )
    cnpj_cpf_credor: Optional[str] = Field(
        default=None, description="CNPJ/CPF of creditor"
    )
    nome_credor: Optional[str] = Field(default=None, description="Name of creditor")

    @property
    def variacao(self) -> Decimal:
        """Calculate year-over-year variation."""
        return self.situacao_atual - self.situacao_anterior

    model_config = {"frozen": True}


class ResumoPatrimonio(BaseModel):
    """Summary of patrimony."""

    total_bens_anterior: Decimal = Field(default=Decimal("0"))
    total_bens_atual: Decimal = Field(default=Decimal("0"))
    total_dividas_anterior: Decimal = Field(default=Decimal("0"))
    total_dividas_atual: Decimal = Field(default=Decimal("0"))

    @property
    def patrimonio_liquido_anterior(self) -> Decimal:
        """Net worth at end of previous year."""
        return self.total_bens_anterior - self.total_dividas_anterior

    @property
    def patrimonio_liquido_atual(self) -> Decimal:
        """Net worth at end of current year."""
        return self.total_bens_atual - self.total_dividas_atual

    @property
    def variacao_patrimonial(self) -> Decimal:
        """Patrimony variation during the year."""
        return self.patrimonio_liquido_atual - self.patrimonio_liquido_anterior

    model_config = {"frozen": True}
