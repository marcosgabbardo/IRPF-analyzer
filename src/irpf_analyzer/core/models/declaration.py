"""Main declaration model for IRPF."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from irpf_analyzer.core.models.alienation import Alienacao
from irpf_analyzer.core.models.deductions import Deducao, ResumoDeducoes
from irpf_analyzer.core.models.dependents import Dependente
from irpf_analyzer.core.models.enums import TipoDeclaracao
from irpf_analyzer.core.models.income import Rendimento
from irpf_analyzer.core.models.patrimony import BemDireito, Divida, ResumoPatrimonio


class Contribuinte(BaseModel):
    """Taxpayer identification."""

    cpf: str = Field(..., description="CPF do contribuinte")
    nome: str = Field(..., description="Nome completo")
    data_nascimento: Optional[date] = Field(default=None)
    titulo_eleitor: Optional[str] = Field(default=None)
    ocupacao_principal: Optional[str] = Field(default=None)
    natureza_ocupacao: Optional[str] = Field(default=None)

    @field_validator("cpf")
    @classmethod
    def validate_cpf_format(cls, v: str) -> str:
        """Validate CPF format (11 digits)."""
        cpf_digits = "".join(filter(str.isdigit, v))
        if len(cpf_digits) != 11:
            raise ValueError("CPF deve ter 11 dígitos")
        return cpf_digits

    model_config = {"frozen": True}


class Declaration(BaseModel):
    """Main IRPF declaration model."""

    # Identification
    contribuinte: Contribuinte = Field(..., description="Taxpayer data")
    ano_exercicio: int = Field(..., description="Tax year (e.g., 2025)")
    ano_calendario: int = Field(..., description="Calendar year (e.g., 2024)")
    tipo_declaracao: TipoDeclaracao = Field(..., description="Declaration type")

    # Declaration metadata
    numero_recibo: Optional[str] = Field(default=None, description="Receipt number")
    data_transmissao: Optional[datetime] = Field(
        default=None, description="Transmission date"
    )
    retificadora: bool = Field(default=False, description="Is rectifying declaration")
    numero_recibo_original: Optional[str] = Field(
        default=None, description="Original receipt number if rectifying"
    )

    # Financial data
    rendimentos: list[Rendimento] = Field(default_factory=list)
    deducoes: list[Deducao] = Field(default_factory=list)
    bens_direitos: list[BemDireito] = Field(default_factory=list)
    dividas: list[Divida] = Field(default_factory=list)
    dependentes: list[Dependente] = Field(default_factory=list)
    alienacoes: list[Alienacao] = Field(default_factory=list)

    # Calculated totals (populated by parser or calculated)
    total_rendimentos_tributaveis: Decimal = Field(default=Decimal("0"))
    total_rendimentos_isentos: Decimal = Field(default=Decimal("0"))
    total_rendimentos_exclusivos: Decimal = Field(default=Decimal("0"))
    total_deducoes: Decimal = Field(default=Decimal("0"))
    base_calculo: Decimal = Field(default=Decimal("0"))
    imposto_devido: Decimal = Field(default=Decimal("0"))
    imposto_pago: Decimal = Field(default=Decimal("0"))
    saldo_imposto: Decimal = Field(default=Decimal("0"))  # + to pay, - refund

    @property
    def cpf_masked(self) -> str:
        """Return masked CPF for display (***.***.***-XX)."""
        cpf = self.contribuinte.cpf
        return f"***.***.***.{cpf[-2:]}"

    @property
    def resumo_patrimonio(self) -> ResumoPatrimonio:
        """Calculate patrimony summary."""
        total_bens_anterior = sum(b.situacao_anterior for b in self.bens_direitos)
        total_bens_atual = sum(b.situacao_atual for b in self.bens_direitos)
        total_dividas_anterior = sum(d.situacao_anterior for d in self.dividas)
        total_dividas_atual = sum(d.situacao_atual for d in self.dividas)

        return ResumoPatrimonio(
            total_bens_anterior=total_bens_anterior,
            total_bens_atual=total_bens_atual,
            total_dividas_anterior=total_dividas_anterior,
            total_dividas_atual=total_dividas_atual,
        )

    @property
    def resumo_deducoes(self) -> ResumoDeducoes:
        """Calculate deductions summary by type."""
        from irpf_analyzer.core.models.enums import TipoDeducao

        totals: dict[str, Decimal] = {
            "previdencia_oficial": Decimal("0"),
            "previdencia_privada": Decimal("0"),
            "dependentes": Decimal("0"),
            "despesas_medicas": Decimal("0"),
            "despesas_educacao": Decimal("0"),
            "pensao_alimenticia": Decimal("0"),
            "livro_caixa": Decimal("0"),
            "outras": Decimal("0"),
        }

        type_mapping = {
            TipoDeducao.PREVIDENCIA_OFICIAL: "previdencia_oficial",
            TipoDeducao.PREVIDENCIA_PRIVADA: "previdencia_privada",
            TipoDeducao.DEPENDENTES: "dependentes",
            TipoDeducao.DESPESAS_MEDICAS: "despesas_medicas",
            TipoDeducao.DESPESAS_EDUCACAO: "despesas_educacao",
            TipoDeducao.PENSAO_ALIMENTICIA: "pensao_alimenticia",
            TipoDeducao.LIVRO_CAIXA: "livro_caixa",
        }

        for deducao in self.deducoes:
            key = type_mapping.get(deducao.tipo, "outras")
            totals[key] += deducao.valor

        return ResumoDeducoes(**totals)

    @property
    def tem_restituicao(self) -> bool:
        """Check if declaration results in tax refund."""
        return self.saldo_imposto < 0

    @property
    def valor_restituicao(self) -> Decimal:
        """Return refund amount (positive) or 0."""
        return abs(self.saldo_imposto) if self.tem_restituicao else Decimal("0")

    @property
    def valor_a_pagar(self) -> Decimal:
        """Return amount to pay or 0."""
        return self.saldo_imposto if self.saldo_imposto > 0 else Decimal("0")

    model_config = {"frozen": True}
