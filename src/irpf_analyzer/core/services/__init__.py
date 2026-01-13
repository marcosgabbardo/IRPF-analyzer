"""Domain services for IRPF Analyzer."""

from irpf_analyzer.core.services.checklist_generator import (
    generate_checklist,
    DocumentChecklistGenerator,
)

__all__ = [
    "generate_checklist",
    "DocumentChecklistGenerator",
]
