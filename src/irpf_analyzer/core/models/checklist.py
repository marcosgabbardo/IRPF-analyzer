"""Document checklist models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocumentCategory(str, Enum):
    """Categories of supporting documents."""

    RENDIMENTOS = "Rendimentos"
    DEDUCOES = "Deduções"
    BENS_DIREITOS = "Bens e Direitos"
    DIVIDAS = "Dívidas"
    DEPENDENTES = "Dependentes"
    PAGAMENTOS = "Pagamentos"
    ALIENACOES = "Alienações"


class DocumentPriority(str, Enum):
    """Priority level for document collection."""

    OBRIGATORIO = "Obrigatório"
    RECOMENDADO = "Recomendado"
    OPCIONAL = "Opcional"


class Document(BaseModel):
    """A document required to support a declaration entry."""

    nome: str = Field(..., description="Document name")
    descricao: str = Field(..., description="What this document proves")
    categoria: DocumentCategory = Field(..., description="Document category")
    prioridade: DocumentPriority = Field(
        default=DocumentPriority.OBRIGATORIO,
        description="How important this document is",
    )
    fonte: Optional[str] = Field(
        default=None,
        description="Where to obtain this document (e.g., employer, bank)",
    )
    referencia: Optional[str] = Field(
        default=None,
        description="Reference to the declaration entry (e.g., asset description)",
    )
    valor: Optional[str] = Field(
        default=None,
        description="Value associated with this entry",
    )

    model_config = {"frozen": True}


class DocumentChecklist(BaseModel):
    """Complete checklist of documents for a declaration."""

    ano_exercicio: int = Field(..., description="Tax year")
    documentos: list[Document] = Field(default_factory=list)

    @property
    def total_documentos(self) -> int:
        """Total number of documents."""
        return len(self.documentos)

    @property
    def obrigatorios(self) -> list[Document]:
        """Get mandatory documents."""
        return [d for d in self.documentos if d.prioridade == DocumentPriority.OBRIGATORIO]

    @property
    def recomendados(self) -> list[Document]:
        """Get recommended documents."""
        return [d for d in self.documentos if d.prioridade == DocumentPriority.RECOMENDADO]

    @property
    def opcionais(self) -> list[Document]:
        """Get optional documents."""
        return [d for d in self.documentos if d.prioridade == DocumentPriority.OPCIONAL]

    def by_category(self, category: DocumentCategory) -> list[Document]:
        """Get documents by category."""
        return [d for d in self.documentos if d.categoria == category]
