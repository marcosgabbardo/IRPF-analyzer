"""Comparison models for year-over-year analysis."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class ValueComparison(BaseModel):
    """Comparison of a single value between two years."""

    campo: str = Field(..., description="Field name for display")
    ano_anterior: int = Field(..., description="Older year")
    ano_atual: int = Field(..., description="Newer year")
    valor_anterior: Decimal = Field(default=Decimal("0"))
    valor_atual: Decimal = Field(default=Decimal("0"))

    @computed_field
    @property
    def variacao_absoluta(self) -> Decimal:
        """Calculate absolute variation."""
        return self.valor_atual - self.valor_anterior

    @computed_field
    @property
    def variacao_percentual(self) -> Optional[Decimal]:
        """Calculate percentage variation.

        Returns None if previous value is zero and current is also zero.
        Returns 100 if previous is zero but current is positive.
        """
        if self.valor_anterior == 0:
            if self.valor_atual == 0:
                return Decimal("0")
            return None  # Infinite growth (new value from zero)
        return ((self.valor_atual - self.valor_anterior) / abs(self.valor_anterior)) * 100


class IncomeComparison(BaseModel):
    """Income comparison between years."""

    total_tributaveis: ValueComparison = Field(..., description="Taxable income")
    total_isentos: ValueComparison = Field(..., description="Tax-exempt income")
    total_exclusivos: ValueComparison = Field(..., description="Exclusive taxation income")
    total_geral: ValueComparison = Field(..., description="Total income")


class DeductionComparison(BaseModel):
    """Deduction comparison between years."""

    total_deducoes: ValueComparison = Field(..., description="Total deductions")
    previdencia_oficial: ValueComparison = Field(..., description="Official pension")
    previdencia_privada: ValueComparison = Field(..., description="Private pension (PGBL)")
    despesas_medicas: ValueComparison = Field(..., description="Medical expenses")
    despesas_educacao: ValueComparison = Field(..., description="Education expenses")
    pensao_alimenticia: ValueComparison = Field(..., description="Alimony")
    dependentes: ValueComparison = Field(..., description="Dependent deductions")
    outras: ValueComparison = Field(..., description="Other deductions")


class PatrimonyComparison(BaseModel):
    """Patrimony evolution between years."""

    # Net worth at end of each year
    patrimonio_liquido_ano_anterior: Decimal = Field(
        default=Decimal("0"), description="Net worth at end of older year"
    )
    patrimonio_liquido_ano_atual: Decimal = Field(
        default=Decimal("0"), description="Net worth at end of newer year"
    )

    # Comparisons
    total_bens: ValueComparison = Field(..., description="Total assets")
    total_dividas: ValueComparison = Field(..., description="Total debts")
    patrimonio_liquido: ValueComparison = Field(..., description="Net worth")

    # Breakdown by asset category
    por_categoria: dict[str, ValueComparison] = Field(
        default_factory=dict, description="Comparison by asset category"
    )


class TaxComparison(BaseModel):
    """Tax impact comparison between years."""

    base_calculo: ValueComparison = Field(..., description="Taxable base")
    imposto_devido: ValueComparison = Field(..., description="Tax owed")
    imposto_pago: ValueComparison = Field(..., description="Tax paid (withholdings)")
    saldo_imposto: ValueComparison = Field(..., description="Net tax (+ pay, - refund)")

    @property
    def resultado_anterior(self) -> str:
        """Describe tax result for older year."""
        if self.saldo_imposto.valor_anterior < 0:
            return "restituicao"
        elif self.saldo_imposto.valor_anterior > 0:
            return "a_pagar"
        return "zero"

    @property
    def resultado_atual(self) -> str:
        """Describe tax result for newer year."""
        if self.saldo_imposto.valor_atual < 0:
            return "restituicao"
        elif self.saldo_imposto.valor_atual > 0:
            return "a_pagar"
        return "zero"


class AssetHighlight(BaseModel):
    """Highlight of significant asset changes between years."""

    descricao: str = Field(..., description="Asset description (truncated)")
    grupo: str = Field(..., description="Asset group/category")
    valor_ano_anterior: Decimal = Field(default=Decimal("0"))
    valor_ano_atual: Decimal = Field(default=Decimal("0"))
    variacao_absoluta: Decimal = Field(default=Decimal("0"))
    variacao_percentual: Optional[Decimal] = Field(default=None)
    tipo: str = Field(
        ..., description="Type: 'gainer', 'loser', 'new', 'sold'"
    )


class ComparisonResult(BaseModel):
    """Complete comparison result between two declarations."""

    # Metadata
    cpf: str = Field(..., description="Taxpayer CPF")
    nome_contribuinte: str = Field(..., description="Taxpayer name")
    ano_anterior: int = Field(..., description="Older year")
    ano_atual: int = Field(..., description="Newer year")

    # Comparison sections
    rendimentos: IncomeComparison = Field(..., description="Income comparison")
    deducoes: DeductionComparison = Field(..., description="Deduction comparison")
    patrimonio: PatrimonyComparison = Field(..., description="Patrimony comparison")
    impostos: TaxComparison = Field(..., description="Tax comparison")

    # Highlights
    destaques_ativos: list[AssetHighlight] = Field(
        default_factory=list, description="Asset change highlights"
    )

    # Warnings
    avisos: list[str] = Field(
        default_factory=list, description="Comparison warnings"
    )

    @property
    def periodo_label(self) -> str:
        """Return formatted period label."""
        return f"{self.ano_anterior} → {self.ano_atual}"
