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
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
        KeepTogether,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

if TYPE_CHECKING:
    from irpf_analyzer.core.models.analysis import AnalysisResult
    from irpf_analyzer.core.models.declaration import Declaration
    from irpf_analyzer.core.models.checklist import DocumentChecklist


def check_reportlab_available() -> None:
    """Check if reportlab is available, raise if not."""
    if not REPORTLAB_AVAILABLE:
        raise ImportError(
            "ReportLab não está instalado. "
            "Instale com: uv sync --extra pdf ou pip install reportlab"
        )


class PDFReportGenerator:
    """Generates comprehensive PDF reports from IRPF analysis results."""

    # Page dimensions (A4 with margins)
    PAGE_WIDTH = A4[0] - 4 * cm  # ~17cm usable

    def __init__(
        self,
        declaration: "Declaration",
        analysis: "AnalysisResult",
        checklist: "DocumentChecklist | None" = None,
    ):
        check_reportlab_available()
        self.declaration = declaration
        self.analysis = analysis
        self.checklist = checklist
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles."""
        # Title style
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Heading1"],
                fontSize=20,
                spaceAfter=20,
                textColor=colors.HexColor("#1a365d"),
                alignment=1,  # Center
            )
        )
        # Section header style
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=13,
                spaceBefore=20,
                spaceAfter=10,
                textColor=colors.HexColor("#2c5282"),
                borderPadding=5,
            )
        )
        # Subsection header
        self.styles.add(
            ParagraphStyle(
                name="SubsectionHeader",
                parent=self.styles["Heading3"],
                fontSize=11,
                spaceBefore=12,
                spaceAfter=6,
                textColor=colors.HexColor("#4a5568"),
            )
        )
        # Table cell style
        self.styles.add(
            ParagraphStyle(
                name="TableCell",
                parent=self.styles["Normal"],
                fontSize=8,
                leading=11,
            )
        )
        # Table cell bold
        self.styles.add(
            ParagraphStyle(
                name="TableCellBold",
                parent=self.styles["Normal"],
                fontSize=8,
                leading=11,
                fontName="Helvetica-Bold",
            )
        )
        # Table header style
        self.styles.add(
            ParagraphStyle(
                name="TableHeader",
                parent=self.styles["Normal"],
                fontSize=8,
                leading=11,
                fontName="Helvetica-Bold",
                textColor=colors.white,
            )
        )
        # Small text for footer
        self.styles.add(
            ParagraphStyle(
                name="SmallText",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.gray,
                alignment=1,
            )
        )
        # Bullet point style
        self.styles.add(
            ParagraphStyle(
                name="BulletText",
                parent=self.styles["Normal"],
                fontSize=9,
                leading=14,
                leftIndent=15,
                bulletIndent=5,
            )
        )
        # Category header style
        self.styles.add(
            ParagraphStyle(
                name="CategoryHeader",
                parent=self.styles["Normal"],
                fontSize=10,
                spaceBefore=10,
                spaceAfter=5,
                fontName="Helvetica-Bold",
                textColor=colors.HexColor("#2d3748"),
            )
        )

    def _fmt_currency(self, v: Decimal) -> str:
        """Format decimal as Brazilian currency."""
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _fmt_cpf(self, cpf: str) -> str:
        """Format CPF for display."""
        cpf = "".join(filter(str.isdigit, cpf))
        if len(cpf) == 11:
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf

    def _fmt_cnpj(self, cnpj: str) -> str:
        """Format CNPJ for display."""
        cnpj = "".join(filter(str.isdigit, cnpj))
        if len(cnpj) == 14:
            return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
        return cnpj

    def generate(self, output_path: Path) -> Path:
        """Generate PDF report and save to output_path."""
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        elements = []

        # === PAGE 1: Summary ===
        elements.extend(self._build_header())
        elements.extend(self._build_declaration_info())
        elements.extend(self._build_risk_score())
        elements.extend(self._build_financial_summary())
        elements.extend(self._build_patrimony_summary())
        elements.extend(self._build_patrimony_flow())

        # === PAGE 2: Inconsistencies, Warnings, Suggestions ===
        if self.analysis.inconsistencies or self.analysis.warnings or self.analysis.suggestions:
            elements.append(PageBreak())
            elements.extend(self._build_analysis_header())
            if self.analysis.inconsistencies:
                elements.extend(self._build_inconsistencies())
            if self.analysis.warnings:
                elements.extend(self._build_warnings())
            if self.analysis.suggestions:
                elements.extend(self._build_suggestions())

        # === PAGE 3+: Detailed Data ===
        elements.append(PageBreak())
        elements.extend(self._build_details_header())

        # Dependents
        if self.declaration.dependentes:
            elements.extend(self._build_dependents())

        # Income sources
        if self.declaration.rendimentos:
            elements.extend(self._build_income())

        # Deductions
        if self.declaration.deducoes:
            elements.extend(self._build_deductions())

        # Assets
        if self.declaration.bens_direitos:
            elements.extend(self._build_assets())

        # Alienations
        if self.declaration.alienacoes:
            elements.extend(self._build_alienations())

        # === Checklist ===
        if self.checklist:
            elements.append(PageBreak())
            elements.extend(self._build_checklist())

        # Footer
        elements.extend(self._build_footer())

        doc.build(elements)
        return output_path

    def _build_header(self) -> list:
        """Build report header."""
        elements = []
        elements.append(
            Paragraph("IRPF Analyzer", self.styles["ReportTitle"])
        )
        elements.append(
            Paragraph(
                "Relatório Completo de Análise de Declaração",
                ParagraphStyle(
                    "Subtitle",
                    parent=self.styles["Normal"],
                    fontSize=12,
                    textColor=colors.HexColor("#4a5568"),
                    alignment=1,
                    spaceAfter=15,
                )
            )
        )
        return elements

    def _build_declaration_info(self) -> list:
        """Build declaration information section."""
        elements = []
        elements.append(Paragraph("Dados da Declaração", self.styles["SectionHeader"]))

        cpf_masked = self.declaration.cpf_masked
        retificadora = "Sim" if self.declaration.retificadora else "Não"

        data = [
            [
                Paragraph("<b>Contribuinte:</b>", self.styles["TableCell"]),
                Paragraph(self.declaration.contribuinte.nome, self.styles["TableCell"]),
                Paragraph("<b>CPF:</b>", self.styles["TableCell"]),
                Paragraph(cpf_masked, self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Exercício:</b>", self.styles["TableCell"]),
                Paragraph(
                    f"{self.declaration.ano_exercicio} (Ano-calendário {self.declaration.ano_calendario})",
                    self.styles["TableCell"]
                ),
                Paragraph("<b>Tipo:</b>", self.styles["TableCell"]),
                Paragraph(self.declaration.tipo_declaracao.value.upper(), self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Retificadora:</b>", self.styles["TableCell"]),
                Paragraph(retificadora, self.styles["TableCell"]),
                Paragraph("<b>Nº Recibo:</b>", self.styles["TableCell"]),
                Paragraph(self.declaration.numero_recibo or "-", self.styles["TableCell"]),
            ],
        ]

        table = Table(data, colWidths=[3 * cm, 6 * cm, 3 * cm, 6 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(table)
        return elements

    def _build_risk_score(self) -> list:
        """Build risk score section."""
        elements = []
        elements.append(Paragraph("Índice de Conformidade Fiscal", self.styles["SectionHeader"]))

        score = self.analysis.risk_score.score

        if score >= 80:
            bg_color = colors.HexColor("#c6f6d5")
            text_color = colors.HexColor("#22543d")
            status_text = "Excelente - Baixo risco de malha fina"
        elif score >= 50:
            bg_color = colors.HexColor("#fefcbf")
            text_color = colors.HexColor("#744210")
            status_text = "Atenção - Risco moderado"
        elif score >= 25:
            bg_color = colors.HexColor("#fed7d7")
            text_color = colors.HexColor("#742a2a")
            status_text = "Alerta - Risco elevado de malha fina"
        else:
            bg_color = colors.HexColor("#feb2b2")
            text_color = colors.HexColor("#63171b")
            status_text = "Crítico - Alto risco de malha fina"

        score_text = f"<font size='20'><b>{score}%</b></font>"
        level_text = f"<font size='10'>{status_text}</font>"

        data = [[
            Paragraph(score_text, ParagraphStyle("ScoreNum", alignment=1)),
            Paragraph(level_text, ParagraphStyle("ScoreLevel", alignment=0, leftIndent=10)),
        ]]

        table = Table(data, colWidths=[4 * cm, 14 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), bg_color),
                ("BOX", (0, 0), (-1, -1), 2, text_color),
                ("TEXTCOLOR", (0, 0), (-1, -1), text_color),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(table)
        return elements

    def _build_financial_summary(self) -> list:
        """Build financial summary section."""
        elements = []
        elements.append(Paragraph("Resumo Financeiro", self.styles["SectionHeader"]))

        fmt = self._fmt_currency
        decl = self.declaration

        # Income summary
        data = [
            [
                Paragraph("<b>RENDIMENTOS</b>", self.styles["TableCellBold"]),
                Paragraph("", self.styles["TableCell"]),
                Paragraph("<b>IMPOSTOS</b>", self.styles["TableCellBold"]),
                Paragraph("", self.styles["TableCell"]),
            ],
            [
                Paragraph("Tributáveis:", self.styles["TableCell"]),
                Paragraph(fmt(decl.total_rendimentos_tributaveis), self.styles["TableCell"]),
                Paragraph("Imposto Devido:", self.styles["TableCell"]),
                Paragraph(fmt(decl.imposto_devido), self.styles["TableCell"]),
            ],
            [
                Paragraph("Isentos:", self.styles["TableCell"]),
                Paragraph(fmt(decl.total_rendimentos_isentos), self.styles["TableCell"]),
                Paragraph("Imposto Pago:", self.styles["TableCell"]),
                Paragraph(fmt(decl.imposto_pago), self.styles["TableCell"]),
            ],
            [
                Paragraph("Exclusivos:", self.styles["TableCell"]),
                Paragraph(fmt(decl.total_rendimentos_exclusivos), self.styles["TableCell"]),
                Paragraph("<b>Saldo:</b>", self.styles["TableCellBold"]),
                Paragraph(
                    f"<b>{fmt(decl.saldo_imposto)}</b>",
                    self.styles["TableCell"]
                ),
            ],
            [
                Paragraph("<b>DEDUÇÕES</b>", self.styles["TableCellBold"]),
                Paragraph("", self.styles["TableCell"]),
                Paragraph("<b>RESULTADO</b>", self.styles["TableCellBold"]),
                Paragraph("", self.styles["TableCell"]),
            ],
            [
                Paragraph("Total Deduções:", self.styles["TableCell"]),
                Paragraph(fmt(decl.total_deducoes), self.styles["TableCell"]),
                Paragraph("Base de Cálculo:", self.styles["TableCell"]),
                Paragraph(fmt(decl.base_calculo), self.styles["TableCell"]),
            ],
        ]

        # Add refund/payment row
        if decl.tem_restituicao:
            data.append([
                Paragraph("", self.styles["TableCell"]),
                Paragraph("", self.styles["TableCell"]),
                Paragraph("<b>A Restituir:</b>", self.styles["TableCellBold"]),
                Paragraph(
                    f"<font color='#22543d'><b>{fmt(decl.valor_restituicao)}</b></font>",
                    self.styles["TableCell"]
                ),
            ])
        elif decl.valor_a_pagar > 0:
            data.append([
                Paragraph("", self.styles["TableCell"]),
                Paragraph("", self.styles["TableCell"]),
                Paragraph("<b>A Pagar:</b>", self.styles["TableCellBold"]),
                Paragraph(
                    f"<font color='#c53030'><b>{fmt(decl.valor_a_pagar)}</b></font>",
                    self.styles["TableCell"]
                ),
            ])

        table = Table(data, colWidths=[4 * cm, 5 * cm, 4 * cm, 5 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f7")),
                ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#edf2f7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ])
        )
        elements.append(table)
        return elements

    def _build_patrimony_summary(self) -> list:
        """Build patrimony summary section."""
        elements = []
        elements.append(Paragraph("Resumo Patrimonial", self.styles["SectionHeader"]))

        resumo = self.declaration.resumo_patrimonio
        fmt = self._fmt_currency

        header = [
            Paragraph("", self.styles["TableHeader"]),
            Paragraph("31/12 Anterior", self.styles["TableHeader"]),
            Paragraph("31/12 Atual", self.styles["TableHeader"]),
            Paragraph("Variação", self.styles["TableHeader"]),
        ]

        variacao_bens = resumo.total_bens_atual - resumo.total_bens_anterior
        variacao_dividas = resumo.total_dividas_atual - resumo.total_dividas_anterior

        data = [
            header,
            [
                Paragraph("Total de Bens", self.styles["TableCellBold"]),
                Paragraph(fmt(resumo.total_bens_anterior), self.styles["TableCell"]),
                Paragraph(fmt(resumo.total_bens_atual), self.styles["TableCell"]),
                Paragraph(fmt(variacao_bens), self.styles["TableCell"]),
            ],
            [
                Paragraph("Total de Dívidas", self.styles["TableCellBold"]),
                Paragraph(fmt(resumo.total_dividas_anterior), self.styles["TableCell"]),
                Paragraph(fmt(resumo.total_dividas_atual), self.styles["TableCell"]),
                Paragraph(fmt(variacao_dividas), self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Patrimônio Líquido</b>", self.styles["TableCell"]),
                Paragraph(f"<b>{fmt(resumo.patrimonio_liquido_anterior)}</b>", self.styles["TableCell"]),
                Paragraph(f"<b>{fmt(resumo.patrimonio_liquido_atual)}</b>", self.styles["TableCell"]),
                Paragraph(f"<b>{fmt(resumo.variacao_patrimonial)}</b>", self.styles["TableCell"]),
            ],
        ]

        table = Table(data, colWidths=[5 * cm, 4.3 * cm, 4.3 * cm, 4.4 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f7fafc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(table)
        return elements

    def _build_patrimony_flow(self) -> list:
        """Build patrimony flow analysis section."""
        elements = []

        flow = self.analysis.patrimony_flow
        if not flow:
            return elements

        elements.append(Paragraph("Análise de Fluxo Patrimonial", self.styles["SectionHeader"]))

        fmt = self._fmt_currency

        # Resources table
        elements.append(Paragraph("Origem dos Recursos", self.styles["SubsectionHeader"]))

        resources_data = [
            [
                Paragraph("<b>Fonte</b>", self.styles["TableCellBold"]),
                Paragraph("<b>Valor</b>", self.styles["TableCellBold"]),
            ],
            [
                Paragraph("Renda declarada (salário, dividendos, rend. fixa)", self.styles["TableCell"]),
                Paragraph(fmt(flow.renda_declarada), self.styles["TableCell"]),
            ],
        ]

        if flow.ganho_capital > 0:
            resources_data.append([
                Paragraph("Ganho de capital (LUCRO das alienações)", self.styles["TableCell"]),
                Paragraph(fmt(flow.ganho_capital), self.styles["TableCell"]),
            ])

        if flow.lucro_acoes_exterior > 0:
            resources_data.append([
                Paragraph("Lucro em ações estrangeiras", self.styles["TableCell"]),
                Paragraph(fmt(flow.lucro_acoes_exterior), self.styles["TableCell"]),
            ])

        # Total row
        resources_data.append([
            Paragraph("<b>TOTAL DE RECURSOS</b>", self.styles["TableCellBold"]),
            Paragraph(f"<b>{fmt(flow.recursos_totais)}</b>", self.styles["TableCellBold"]),
        ])

        # Informational values (NOT counted - principal already in patrimony)
        if flow.valor_alienacoes > 0 or flow.ativos_liquidados > 0:
            resources_data.append([
                Paragraph("<i>--- Valores informativos (não contados) ---</i>", self.styles["TableCell"]),
                Paragraph("", self.styles["TableCell"]),
            ])
            if flow.valor_alienacoes > 0:
                resources_data.append([
                    Paragraph("<i>Valor bruto de vendas</i>", self.styles["TableCell"]),
                    Paragraph(f"<i>{fmt(flow.valor_alienacoes)}</i>", self.styles["TableCell"]),
                ])
            if flow.ativos_liquidados > 0:
                resources_data.append([
                    Paragraph("<i>Ativos liquidados (principal)</i>", self.styles["TableCell"]),
                    Paragraph(f"<i>{fmt(flow.ativos_liquidados)}</i>", self.styles["TableCell"]),
                ])

        resources_table = Table(resources_data, colWidths=[12 * cm, 6 * cm])
        resources_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#edf2f7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(resources_table)
        elements.append(Spacer(1, 0.3 * cm))

        # Calculation section
        elements.append(Paragraph("Cálculo de Compatibilidade", self.styles["SubsectionHeader"]))

        # Determine status
        if flow.explicado:
            status_text = "EXPLICADO"
            status_color = "#22543d"
            status_bg = "#c6f6d5"
        else:
            status_text = "NÃO EXPLICADO"
            status_color = "#c53030"
            status_bg = "#fed7d7"

        saldo_color = "#22543d" if flow.saldo >= 0 else "#c53030"

        calc_data = [
            [
                Paragraph("Recursos totais", self.styles["TableCell"]),
                Paragraph(fmt(flow.recursos_totais), self.styles["TableCell"]),
            ],
            [
                Paragraph("(-) Despesas de vida estimadas", self.styles["TableCell"]),
                Paragraph(fmt(flow.despesas_vida_estimadas), self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>(=) Recursos disponíveis</b>", self.styles["TableCellBold"]),
                Paragraph(f"<b>{fmt(flow.recursos_disponiveis)}</b>", self.styles["TableCellBold"]),
            ],
            [
                Paragraph("(-) Variação patrimonial", self.styles["TableCell"]),
                Paragraph(fmt(flow.variacao_patrimonial), self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>(=) Saldo</b>", self.styles["TableCellBold"]),
                Paragraph(f"<font color='{saldo_color}'><b>{fmt(flow.saldo)}</b></font>", self.styles["TableCell"]),
            ],
        ]

        calc_table = Table(calc_data, colWidths=[12 * cm, 6 * cm])
        calc_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#f7fafc")),
                ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#f7fafc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(calc_table)

        # Status box
        status_data = [[
            Paragraph(
                f"<font color='{status_color}'><b>Variação patrimonial: {status_text}</b></font>",
                ParagraphStyle("StatusText", alignment=1, fontSize=10)
            )
        ]]
        status_table = Table(status_data, colWidths=[18 * cm])
        status_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(status_bg)),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(status_color)),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(Spacer(1, 0.2 * cm))
        elements.append(status_table)

        # Disclaimer
        elements.append(Spacer(1, 0.2 * cm))
        elements.append(
            Paragraph(
                f"<i><font color='#718096' size='8'>ℹ️ {flow.disclaimer_despesas}</font></i>",
                self.styles["Normal"]
            )
        )

        return elements

    def _build_analysis_header(self) -> list:
        """Build header for analysis page."""
        elements = []
        elements.append(
            Paragraph(
                "Análise de Risco e Sugestões",
                ParagraphStyle(
                    "PageHeader",
                    parent=self.styles["Heading1"],
                    fontSize=16,
                    textColor=colors.HexColor("#2c5282"),
                    spaceAfter=10,
                )
            )
        )
        return elements

    def _build_inconsistencies(self) -> list:
        """Build inconsistencies section."""
        elements = []
        elements.append(
            Paragraph("Inconsistências Detectadas", self.styles["SectionHeader"])
        )

        header = [
            Paragraph("Tipo", self.styles["TableHeader"]),
            Paragraph("Descrição", self.styles["TableHeader"]),
            Paragraph("Risco", self.styles["TableHeader"]),
            Paragraph("Recomendação", self.styles["TableHeader"]),
        ]

        data = [header]

        risk_colors = {
            "BAIXO": "#38a169",
            "MÉDIO": "#d69e2e",
            "ALTO": "#e53e3e",
            "CRÍTICO": "#9b2c2c",
        }

        for inc in self.analysis.inconsistencies:
            risk_color = risk_colors.get(inc.risco.value, "#000000")
            data.append([
                Paragraph(inc.tipo.value.replace("_", " ").title(), self.styles["TableCell"]),
                Paragraph(inc.descricao, self.styles["TableCell"]),
                Paragraph(f"<font color='{risk_color}'><b>{inc.risco.value}</b></font>", self.styles["TableCell"]),
                Paragraph(inc.recomendacao or "-", self.styles["TableCell"]),
            ])

        table = Table(data, colWidths=[3 * cm, 5.5 * cm, 2 * cm, 7.5 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c53030")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#feb2b2")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ])
        )
        elements.append(table)
        return elements

    def _build_warnings(self) -> list:
        """Build warnings section."""
        elements = []
        elements.append(Paragraph("Avisos", self.styles["SectionHeader"]))

        for warning in self.analysis.warnings:
            info_tag = " <i>(informativo)</i>" if warning.informativo else ""
            bullet_color = "#d69e2e" if warning.risco.value == "BAIXO" else "#e53e3e"

            elements.append(
                Paragraph(
                    f"<font color='{bullet_color}'>●</font> {warning.mensagem}{info_tag}",
                    self.styles["BulletText"],
                )
            )
            elements.append(Spacer(1, 0.1 * cm))

        return elements

    def _build_suggestions(self) -> list:
        """Build suggestions section."""
        elements = []
        elements.append(Paragraph("Sugestões de Otimização", self.styles["SectionHeader"]))

        fmt = self._fmt_currency

        for sug in sorted(self.analysis.suggestions, key=lambda x: x.prioridade):
            economia = fmt(sug.economia_potencial) if sug.economia_potencial else None

            title_data = [[
                Paragraph(f"<b>{sug.titulo}</b>", self.styles["TableCell"]),
                Paragraph(
                    f"<font color='#22543d'><b>{economia}</b></font>" if economia else "",
                    ParagraphStyle("EconStyle", alignment=2, fontSize=9)
                ),
            ]]

            title_table = Table(title_data, colWidths=[13 * cm, 5 * cm])
            title_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#c6f6d5")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ])
            )

            desc_data = [[Paragraph(sug.descricao, self.styles["TableCell"])]]
            desc_table = Table(desc_data, colWidths=[18 * cm])
            desc_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fff4")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#9ae6b4")),
                ])
            )

            elements.append(KeepTogether([title_table, desc_table]))
            elements.append(Spacer(1, 0.2 * cm))

        return elements

    def _build_details_header(self) -> list:
        """Build header for details page."""
        elements = []
        elements.append(
            Paragraph(
                "Detalhes da Declaração",
                ParagraphStyle(
                    "PageHeader",
                    parent=self.styles["Heading1"],
                    fontSize=16,
                    textColor=colors.HexColor("#2c5282"),
                    spaceAfter=10,
                )
            )
        )
        return elements

    def _build_dependents(self) -> list:
        """Build dependents section."""
        elements = []
        elements.append(Paragraph("Dependentes", self.styles["SectionHeader"]))

        header = [
            Paragraph("Nome", self.styles["TableHeader"]),
            Paragraph("CPF", self.styles["TableHeader"]),
            Paragraph("Nascimento", self.styles["TableHeader"]),
            Paragraph("Tipo", self.styles["TableHeader"]),
        ]

        data = [header]

        for dep in self.declaration.dependentes:
            nasc = dep.data_nascimento.strftime("%d/%m/%Y") if dep.data_nascimento else "-"
            data.append([
                Paragraph(dep.nome or "-", self.styles["TableCell"]),
                Paragraph(self._fmt_cpf(dep.cpf) if dep.cpf else "-", self.styles["TableCell"]),
                Paragraph(nasc, self.styles["TableCell"]),
                Paragraph(dep.tipo.value.replace("_", " ").title(), self.styles["TableCell"]),
            ])

        table = Table(data, colWidths=[6 * cm, 4 * cm, 3 * cm, 5 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#805ad5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6bcfa")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(table)
        return elements

    def _build_income(self) -> list:
        """Build income section."""
        elements = []
        elements.append(Paragraph("Rendimentos", self.styles["SectionHeader"]))

        fmt = self._fmt_currency

        header = [
            Paragraph("Fonte Pagadora", self.styles["TableHeader"]),
            Paragraph("CNPJ", self.styles["TableHeader"]),
            Paragraph("Tipo", self.styles["TableHeader"]),
            Paragraph("Valor", self.styles["TableHeader"]),
        ]

        data = [header]

        for rend in self.declaration.rendimentos:
            fonte = rend.fonte_pagadora
            nome = fonte.nome if fonte else "-"
            cnpj = self._fmt_cnpj(fonte.cnpj) if fonte and fonte.cnpj else "-"

            data.append([
                Paragraph(nome[:35] + "..." if len(nome) > 35 else nome, self.styles["TableCell"]),
                Paragraph(cnpj, self.styles["TableCell"]),
                Paragraph(rend.tipo.value.replace("_", " ").title()[:20], self.styles["TableCell"]),
                Paragraph(fmt(rend.valor), self.styles["TableCell"]),
            ])

        table = Table(data, colWidths=[6 * cm, 4.5 * cm, 4 * cm, 3.5 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#38a169")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ae6b4")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(table)

        # Total
        total = sum(r.valor for r in self.declaration.rendimentos)
        elements.append(
            Paragraph(
                f"<b>Total de Rendimentos: {fmt(total)}</b>",
                ParagraphStyle("Total", fontSize=9, spaceBefore=5)
            )
        )
        return elements

    def _build_deductions(self) -> list:
        """Build deductions section."""
        elements = []
        elements.append(Paragraph("Deduções", self.styles["SectionHeader"]))

        fmt = self._fmt_currency

        header = [
            Paragraph("Prestador", self.styles["TableHeader"]),
            Paragraph("CNPJ/CPF", self.styles["TableHeader"]),
            Paragraph("Tipo", self.styles["TableHeader"]),
            Paragraph("Valor", self.styles["TableHeader"]),
        ]

        data = [header]

        for ded in self.declaration.deducoes:
            doc = self._fmt_cnpj(ded.cnpj_prestador) if ded.cnpj_prestador else (
                self._fmt_cpf(ded.cpf_prestador) if ded.cpf_prestador else "-"
            )
            nome = ded.nome_prestador or "-"

            data.append([
                Paragraph(nome[:35] + "..." if len(nome) > 35 else nome, self.styles["TableCell"]),
                Paragraph(doc, self.styles["TableCell"]),
                Paragraph(ded.tipo.value.replace("_", " ").title()[:20], self.styles["TableCell"]),
                Paragraph(fmt(ded.valor), self.styles["TableCell"]),
            ])

        table = Table(data, colWidths=[6 * cm, 4.5 * cm, 4 * cm, 3.5 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00b5d8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#76e4f7")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(table)

        total = sum(d.valor for d in self.declaration.deducoes)
        elements.append(
            Paragraph(
                f"<b>Total de Deduções: {fmt(total)}</b>",
                ParagraphStyle("Total", fontSize=9, spaceBefore=5)
            )
        )
        return elements

    def _build_assets(self) -> list:
        """Build assets section."""
        elements = []
        elements.append(Paragraph("Bens e Direitos", self.styles["SectionHeader"]))

        fmt = self._fmt_currency

        header = [
            Paragraph("Grp", self.styles["TableHeader"]),
            Paragraph("Descrição", self.styles["TableHeader"]),
            Paragraph("31/12 Anterior", self.styles["TableHeader"]),
            Paragraph("31/12 Atual", self.styles["TableHeader"]),
        ]

        data = [header]

        for bem in self.declaration.bens_direitos:
            desc = bem.discriminacao
            if len(desc) > 50:
                desc = desc[:47] + "..."

            data.append([
                Paragraph(bem.grupo.value[:2], self.styles["TableCell"]),
                Paragraph(desc, self.styles["TableCell"]),
                Paragraph(fmt(bem.situacao_anterior), self.styles["TableCell"]),
                Paragraph(fmt(bem.situacao_atual), self.styles["TableCell"]),
            ])

        table = Table(data, colWidths=[1.5 * cm, 9 * cm, 3.75 * cm, 3.75 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d69e2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f6e05e")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(table)

        total_atual = sum(b.situacao_atual for b in self.declaration.bens_direitos)
        elements.append(
            Paragraph(
                f"<b>Total Atual: {fmt(total_atual)}</b>",
                ParagraphStyle("Total", fontSize=9, spaceBefore=5)
            )
        )
        return elements

    def _build_alienations(self) -> list:
        """Build alienations/sales section."""
        elements = []
        elements.append(Paragraph("Alienações e Vendas", self.styles["SectionHeader"]))

        fmt = self._fmt_currency

        header = [
            Paragraph("Bem", self.styles["TableHeader"]),
            Paragraph("Custo Aquisição", self.styles["TableHeader"]),
            Paragraph("Valor Venda", self.styles["TableHeader"]),
            Paragraph("Ganho/Perda", self.styles["TableHeader"]),
        ]

        data = [header]

        for alien in self.declaration.alienacoes:
            nome = alien.nome_bem or "-"
            if len(nome) > 40:
                nome = nome[:37] + "..."

            ganho = alien.valor_alienacao - alien.custo_aquisicao
            ganho_color = "#22543d" if ganho >= 0 else "#c53030"

            data.append([
                Paragraph(nome, self.styles["TableCell"]),
                Paragraph(fmt(alien.custo_aquisicao), self.styles["TableCell"]),
                Paragraph(fmt(alien.valor_alienacao), self.styles["TableCell"]),
                Paragraph(f"<font color='{ganho_color}'>{fmt(ganho)}</font>", self.styles["TableCell"]),
            ])

        table = Table(data, colWidths=[7 * cm, 3.7 * cm, 3.7 * cm, 3.6 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c53030")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#feb2b2")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (1, 0), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        elements.append(table)
        return elements

    def _build_checklist(self) -> list:
        """Build document checklist section."""
        from irpf_analyzer.core.models.checklist import DocumentCategory, DocumentPriority

        elements = []
        elements.append(
            Paragraph(
                "Checklist de Documentos",
                ParagraphStyle(
                    "PageHeader",
                    parent=self.styles["Heading1"],
                    fontSize=16,
                    textColor=colors.HexColor("#2c5282"),
                    spaceAfter=10,
                )
            )
        )

        elements.append(
            Paragraph(
                f"<i>Total de documentos necessários: {self.checklist.total_documentos}</i>",
                ParagraphStyle("ChecklistInfo", fontSize=9, spaceAfter=10)
            )
        )

        categories = [
            (DocumentCategory.RENDIMENTOS, "Rendimentos", "#38a169"),
            (DocumentCategory.DEDUCOES, "Deduções", "#00b5d8"),
            (DocumentCategory.BENS_DIREITOS, "Bens e Direitos", "#d69e2e"),
            (DocumentCategory.DEPENDENTES, "Dependentes", "#805ad5"),
            (DocumentCategory.ALIENACOES, "Alienações/Vendas", "#c53030"),
        ]

        priority_labels = {
            DocumentPriority.OBRIGATORIO: ("OBRIGATÓRIO", "#c53030"),
            DocumentPriority.RECOMENDADO: ("RECOMENDADO", "#d69e2e"),
            DocumentPriority.OPCIONAL: ("OPCIONAL", "#718096"),
        }

        for category, cat_name, cat_color in categories:
            docs = self.checklist.by_category(category)
            if not docs:
                continue

            elements.append(
                Paragraph(
                    f"<font color='{cat_color}'><b>{cat_name}</b></font>",
                    self.styles["CategoryHeader"]
                )
            )

            header = [
                Paragraph("Documento", self.styles["TableHeader"]),
                Paragraph("Descrição", self.styles["TableHeader"]),
                Paragraph("Prioridade", self.styles["TableHeader"]),
            ]

            data = [header]

            for doc in docs:
                prio_label, prio_color = priority_labels.get(
                    doc.prioridade, ("", "#000000")
                )
                data.append([
                    Paragraph(doc.nome, self.styles["TableCell"]),
                    Paragraph(doc.descricao, self.styles["TableCell"]),
                    Paragraph(
                        f"<font color='{prio_color}'><b>{prio_label}</b></font>",
                        self.styles["TableCell"]
                    ),
                ])

            table = Table(data, colWidths=[5 * cm, 9.5 * cm, 3.5 * cm])
            table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(cat_color)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("ALIGN", (2, 0), (2, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ])
            )
            elements.append(table)
            elements.append(Spacer(1, 0.3 * cm))

        # Summary
        obrig = len(self.checklist.obrigatorios)
        recom = len(self.checklist.recomendados)
        opc = len(self.checklist.opcionais)

        elements.append(
            Paragraph(
                f"<b>Resumo:</b> {obrig} obrigatórios | {recom} recomendados | {opc} opcionais",
                ParagraphStyle("ChecklistSummary", fontSize=9, spaceBefore=10)
            )
        )

        return elements

    def _build_footer(self) -> list:
        """Build report footer."""
        elements = []
        elements.append(Spacer(1, 1 * cm))

        line_data = [["" * 100]]
        line_table = Table(line_data, colWidths=[18 * cm])
        line_table.setStyle(
            TableStyle([
                ("LINEABOVE", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ])
        )
        elements.append(line_table)
        elements.append(Spacer(1, 0.2 * cm))

        elements.append(
            Paragraph(
                f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} "
                f"pelo IRPF Analyzer v0.1.0",
                self.styles["SmallText"],
            )
        )
        elements.append(Spacer(1, 0.1 * cm))
        elements.append(
            Paragraph(
                "Este relatório é apenas para fins informativos e educacionais. "
                "Consulte um contador para decisões fiscais.",
                self.styles["SmallText"],
            )
        )
        return elements


def generate_pdf_report(
    declaration: "Declaration",
    analysis: "AnalysisResult",
    output_path: Path,
    include_checklist: bool = True,
) -> Path:
    """Generate a PDF report from declaration and analysis."""
    checklist = None
    if include_checklist:
        from irpf_analyzer.core.services import generate_checklist
        checklist = generate_checklist(declaration)

    generator = PDFReportGenerator(declaration, analysis, checklist)
    return generator.generate(output_path)
