"""Deduction models for IRPF declarations."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from irpf_analyzer.core.models.enums import TipoDeducao


class Deducao(BaseModel):
    """Deduction model."""

    tipo: TipoDeducao = Field(..., description="Type of deduction")
    valor: Decimal = Field(..., description="Deduction value", ge=0)
    beneficiario_cpf: Optional[str] = Field(
        default=None, description="CPF of beneficiary (for dependents)"
    )
    beneficiario_nome: Optional[str] = Field(
        default=None, description="Name of beneficiary"
    )
    cnpj_prestador: Optional[str] = Field(
        default=None, description="CNPJ of service provider"
    )
    nome_prestador: Optional[str] = Field(
        default=None, description="Name of service provider"
    )
    descricao: Optional[str] = Field(default=None, description="Additional description")
    parcela: Optional[int] = Field(
        default=None, description="Installment number if applicable"
    )

    model_config = {"frozen": True}


class ResumoDeducoes(BaseModel):
    """Summary of deductions by type."""

    previdencia_oficial: Decimal = Field(default=Decimal("0"))
    previdencia_privada: Decimal = Field(default=Decimal("0"))
    dependentes: Decimal = Field(default=Decimal("0"))
    despesas_medicas: Decimal = Field(default=Decimal("0"))
    despesas_educacao: Decimal = Field(default=Decimal("0"))
    pensao_alimenticia: Decimal = Field(default=Decimal("0"))
    livro_caixa: Decimal = Field(default=Decimal("0"))
    outras: Decimal = Field(default=Decimal("0"))

    @property
    def total(self) -> Decimal:
        """Calculate total deductions."""
        return (
            self.previdencia_oficial
            + self.previdencia_privada
            + self.dependentes
            + self.despesas_medicas
            + self.despesas_educacao
            + self.pensao_alimenticia
            + self.livro_caixa
            + self.outras
        )

    model_config = {"frozen": True}
