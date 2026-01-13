"""Dependent models for IRPF declarations."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from irpf_analyzer.core.models.enums import TipoDependente


class Dependente(BaseModel):
    """Dependent model."""

    tipo: TipoDependente = Field(..., description="Type of dependent")
    cpf: str = Field(..., description="CPF of dependent")
    nome: str = Field(..., description="Full name of dependent")
    data_nascimento: Optional[date] = Field(
        default=None, description="Date of birth"
    )
    possui_rendimentos: bool = Field(
        default=False, description="Whether dependent has own income"
    )

    @property
    def idade(self) -> Optional[int]:
        """Calculate age based on birth date."""
        if self.data_nascimento is None:
            return None
        today = date.today()
        age = today.year - self.data_nascimento.year
        if (today.month, today.day) < (
            self.data_nascimento.month,
            self.data_nascimento.day,
        ):
            age -= 1
        return age

    model_config = {"frozen": True}
