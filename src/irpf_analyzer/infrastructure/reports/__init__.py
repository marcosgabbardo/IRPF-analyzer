"""Report generators for IRPF Analyzer."""

from irpf_analyzer.infrastructure.reports.pdf_generator import (
    generate_pdf_report,
    PDFReportGenerator,
    REPORTLAB_AVAILABLE,
)

__all__ = [
    "generate_pdf_report",
    "PDFReportGenerator",
    "REPORTLAB_AVAILABLE",
]
