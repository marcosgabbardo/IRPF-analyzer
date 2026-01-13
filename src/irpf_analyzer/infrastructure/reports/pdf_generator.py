"""PDF report generator for IRPF analysis."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

if TYPE_CHECKING:
    from irpf_analyzer.core.models.analysis import AnalysisResult
    from irpf_analyzer.core.models.declaration import Declaration


def check_reportlab_available() -> None:
    """Check if reportlab is available, raise if not."""
    if not REPORTLAB_AVAILABLE:
        raise ImportError(
            "ReportLab não está instalado. "
            "Instale com: uv sync --extra pdf ou pip install reportlab"
        )


class PDFReportGenerator:
    """Generates PDF reports from IRPF analysis results."""

    def __init__(self, declaration: "Declaration", analysis: "AnalysisResult"):
        check_reportlab_available()
        self.declaration = declaration
        self.analysis = analysis
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles."""
        self.styles.add(
            ParagraphStyle(
                name="Title2",
                parent=self.styles["Heading1"],
                fontSize=18,
                spaceAfter=12,
                textColor=colors.HexColor("#1a365d"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=14,
                spaceBefore=16,
                spaceAfter=8,
                textColor=colors.HexColor("#2c5282"),
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="BodyText2",
                parent=self.styles["BodyText"],
                fontSize=10,
                spaceBefore=4,
                spaceAfter=4,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SmallText",
                parent=self.styles["BodyText"],
                fontSize=8,
                textColor=colors.gray,
            )
        )

    def generate(self, output_path: Path) -> Path:
        """Generate PDF report and save to output_path."""
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []

        # Header
        elements.extend(self._build_header())

        # Declaration info
        elements.extend(self._build_declaration_info())

        # Risk score
        elements.extend(self._build_risk_score())

        # Patrimony summary
        elements.extend(self._build_patrimony_summary())

        # Inconsistencies
        if self.analysis.inconsistencies:
            elements.extend(self._build_inconsistencies())

        # Warnings
        if self.analysis.warnings:
            elements.extend(self._build_warnings())

        # Suggestions
        if self.analysis.suggestions:
            elements.extend(self._build_suggestions())

        # Footer
        elements.extend(self._build_footer())

        doc.build(elements)
        return output_path

    def _build_header(self) -> list:
        """Build report header."""
        elements = []
        elements.append(
            Paragraph("IRPF Analyzer - Relatório de Análise", self.styles["Title2"])
        )
        elements.append(Spacer(1, 0.5 * cm))
        return elements

    def _build_declaration_info(self) -> list:
        """Build declaration information section."""
        elements = []
        elements.append(Paragraph("Dados da Declaração", self.styles["SectionHeader"]))

        # Use cpf_masked property
        cpf_masked = self.declaration.cpf_masked

        data = [
            ["Contribuinte:", self.declaration.contribuinte.nome],
            ["CPF:", cpf_masked],
            ["Exercício:", str(self.declaration.ano_exercicio)],
            ["Ano-calendário:", str(self.declaration.ano_exercicio - 1)],
            ["Tipo:", self.declaration.tipo_declaracao.value],
        ]

        table = Table(data, colWidths=[4 * cm, 12 * cm])
        table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )
        elements.append(table)
        elements.append(Spacer(1, 0.3 * cm))
        return elements

    def _build_risk_score(self) -> list:
        """Build risk score section."""
        elements = []
        elements.append(Paragraph("Score de Risco - Malha Fina", self.styles["SectionHeader"]))

        score = self.analysis.risk_score.score
        level = self.analysis.risk_score.level.value

        # Color based on risk level
        if score <= 20:
            color = colors.HexColor("#38a169")  # Green
        elif score <= 50:
            color = colors.HexColor("#d69e2e")  # Yellow
        elif score <= 75:
            color = colors.HexColor("#e53e3e")  # Red
        else:
            color = colors.HexColor("#9b2c2c")  # Dark red

        data = [
            ["Score:", f"{score}/100"],
            ["Nível:", level],
        ]

        table = Table(data, colWidths=[3 * cm, 5 * cm])
        table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("TEXTCOLOR", (1, 0), (1, -1), color),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 1, color),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7fafc")),
            ])
        )
        elements.append(table)
        elements.append(Spacer(1, 0.3 * cm))
        return elements

    def _build_patrimony_summary(self) -> list:
        """Build patrimony summary section."""
        elements = []
        elements.append(Paragraph("Resumo Patrimonial", self.styles["SectionHeader"]))

        resumo = self.declaration.resumo_patrimonio

        def fmt(v: Decimal) -> str:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        data = [
            ["", "Ano Anterior", "Ano Atual"],
            ["Total Bens", fmt(resumo.total_bens_anterior), fmt(resumo.total_bens_atual)],
            ["Total Dívidas", fmt(resumo.total_dividas_anterior), fmt(resumo.total_dividas_atual)],
            [
                "Patrimônio Líquido",
                fmt(resumo.patrimonio_liquido_anterior),
                fmt(resumo.patrimonio_liquido_atual),
            ],
        ]

        table = Table(data, colWidths=[5 * cm, 5 * cm, 5 * cm])
        table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ])
        )
        elements.append(table)

        # Variation
        variacao = resumo.variacao_patrimonial
        variacao_str = fmt(variacao)
        if variacao >= 0:
            variacao_str = f"+{variacao_str}"

        elements.append(Spacer(1, 0.2 * cm))
        elements.append(
            Paragraph(f"<b>Variação Patrimonial:</b> {variacao_str}", self.styles["BodyText2"])
        )
        elements.append(Spacer(1, 0.3 * cm))
        return elements

    def _build_inconsistencies(self) -> list:
        """Build inconsistencies section."""
        elements = []
        elements.append(
            Paragraph("Inconsistências Detectadas", self.styles["SectionHeader"])
        )

        data = [["Tipo", "Descrição", "Risco", "Recomendação"]]

        for inc in self.analysis.inconsistencies:
            data.append([
                inc.tipo.value,
                inc.descricao[:80] + "..." if len(inc.descricao) > 80 else inc.descricao,
                inc.risco.value,
                inc.recomendacao or "-",
            ])

        table = Table(data, colWidths=[3 * cm, 6 * cm, 2 * cm, 5 * cm])
        table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (2, 0), (2, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fed7d7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )
        elements.append(table)
        elements.append(Spacer(1, 0.3 * cm))
        return elements

    def _build_warnings(self) -> list:
        """Build warnings section."""
        elements = []
        elements.append(Paragraph("Avisos", self.styles["SectionHeader"]))

        for warning in self.analysis.warnings:
            bullet = "• "
            info_tag = " (informativo)" if warning.informativo else ""
            elements.append(
                Paragraph(
                    f"{bullet}{warning.mensagem}{info_tag}",
                    self.styles["BodyText2"],
                )
            )

        elements.append(Spacer(1, 0.3 * cm))
        return elements

    def _build_suggestions(self) -> list:
        """Build suggestions section."""
        elements = []
        elements.append(
            Paragraph("Sugestões de Otimização", self.styles["SectionHeader"])
        )

        def fmt(v: Decimal) -> str:
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        data = [["Sugestão", "Descrição", "Economia Potencial"]]

        for sug in sorted(self.analysis.suggestions, key=lambda x: x.prioridade):
            economia = fmt(sug.economia_potencial) if sug.economia_potencial else "-"
            data.append([
                sug.titulo,
                sug.descricao[:60] + "..." if len(sug.descricao) > 60 else sug.descricao,
                economia,
            ])

        table = Table(data, colWidths=[4 * cm, 7 * cm, 4 * cm])
        table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c6f6d5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )
        elements.append(table)
        elements.append(Spacer(1, 0.3 * cm))
        return elements

    def _build_footer(self) -> list:
        """Build report footer."""
        elements = []
        elements.append(Spacer(1, 1 * cm))
        elements.append(
            Paragraph(
                f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} "
                f"pelo IRPF Analyzer v0.1.0",
                self.styles["SmallText"],
            )
        )
        elements.append(
            Paragraph(
                "Este relatório é apenas para fins informativos. "
                "Consulte um contador para decisões fiscais.",
                self.styles["SmallText"],
            )
        )
        return elements


def generate_pdf_report(
    declaration: "Declaration",
    analysis: "AnalysisResult",
    output_path: Path,
) -> Path:
    """Generate a PDF report from declaration and analysis."""
    generator = PDFReportGenerator(declaration, analysis)
    return generator.generate(output_path)
