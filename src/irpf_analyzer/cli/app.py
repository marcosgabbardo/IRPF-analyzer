"""Main Typer application for IRPF Analyzer."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.panel import Panel
from rich.table import Table

from irpf_analyzer import __version__
from irpf_analyzer.cli.console import console, print_error, print_success
from irpf_analyzer.core.analyzers import analyze_declaration
from irpf_analyzer.core.models import RiskLevel
from irpf_analyzer.infrastructure.parsers.detector import detect_file_type, FileType
from irpf_analyzer.infrastructure.parsers.dec_parser import parse_dec_file
from irpf_analyzer.shared.exceptions import ParseError
from irpf_analyzer.shared.formatters import format_currency

app = typer.Typer(
    name="irpf-analyzer",
    help="Analisador de riscos e otimização de declaração IRPF",
    add_completion=True,
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"IRPF Analyzer v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Mostra a versão e sai",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """IRPF Analyzer - Analisador de riscos e otimização de declaração."""
    pass


@app.command()
def info(
    arquivo: Annotated[
        Path,
        typer.Argument(
            help="Caminho para arquivo .DEC ou .DBK",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
) -> None:
    """Exibe informações básicas da declaração sem análise completa."""
    try:
        # Detect file type
        file_type = detect_file_type(arquivo)

        console.print()
        console.print(
            Panel.fit(
                f"[header]Arquivo:[/header] {arquivo.name}\n"
                f"[header]Tipo:[/header] {file_type.value}\n"
                f"[header]Tamanho:[/header] {arquivo.stat().st_size:,} bytes",
                title="Informações do Arquivo",
                border_style="blue",
            )
        )

        # Show file preview (first few lines)
        console.print()
        console.print("[header]Preview do conteúdo:[/header]")

        with open(arquivo, "r", encoding="latin-1") as f:
            lines = f.readlines()[:10]

        table = Table(show_header=True, header_style="bold")
        table.add_column("Linha", style="dim", width=6)
        table.add_column("Conteúdo", overflow="fold")

        for i, line in enumerate(lines, 1):
            # Truncate long lines for display
            content = line.strip()[:100]
            if len(line.strip()) > 100:
                content += "..."
            table.add_row(str(i), content)

        console.print(table)

        if len(lines) == 10:
            console.print(f"[muted]... mostrando 10 de {len(open(arquivo, 'r', encoding='latin-1').readlines())} linhas[/muted]")

    except ParseError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        raise typer.Exit(1)


@app.command()
def analyze(
    arquivo: Annotated[
        Path,
        typer.Argument(
            help="Caminho para arquivo .DEC ou .DBK",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Formato de saída: table, json, plain",
        ),
    ] = "table",
) -> None:
    """Executa análise completa da declaração."""
    try:
        file_type = detect_file_type(arquivo)
        console.print()
        console.print(f"[muted]Parseando {arquivo.name}...[/muted]")

        # Parse the declaration
        declaration = parse_dec_file(arquivo)

        # Display header
        console.print()
        console.print(
            Panel.fit(
                f"[header]Contribuinte:[/header] {declaration.contribuinte.nome}\n"
                f"[header]CPF:[/header] {declaration.cpf_masked}\n"
                f"[header]Exercício:[/header] {declaration.ano_exercicio} (Ano-calendário {declaration.ano_calendario})\n"
                f"[header]Tipo:[/header] {declaration.tipo_declaracao.value.upper()}",
                title="IRPF Analyzer - Declaração",
                border_style="blue",
            )
        )

        # Dependents section
        if declaration.dependentes:
            console.print()
            console.print("[header]Dependentes:[/header]")
            dep_table = Table(show_header=True, header_style="bold")
            dep_table.add_column("Nome", style="cyan")
            dep_table.add_column("CPF")
            dep_table.add_column("Nascimento")
            dep_table.add_column("Tipo")

            for dep in declaration.dependentes:
                nasc = dep.data_nascimento.strftime("%d/%m/%Y") if dep.data_nascimento else "-"
                dep_table.add_row(dep.nome, dep.cpf, nasc, dep.tipo.value)

            console.print(dep_table)

        # Deductions section (medical expenses)
        if declaration.deducoes:
            console.print()
            console.print("[header]Despesas Médicas Declaradas:[/header]")
            ded_table = Table(show_header=True, header_style="bold")
            ded_table.add_column("Prestador", style="cyan")
            ded_table.add_column("CNPJ")
            ded_table.add_column("Valor", justify="right", style="green")

            total_medicas = sum(d.valor for d in declaration.deducoes)
            for ded in declaration.deducoes:
                ded_table.add_row(
                    ded.nome_prestador or "-",
                    ded.cnpj_prestador or "-",
                    format_currency(ded.valor)
                )

            console.print(ded_table)
            console.print(f"[bold]Total despesas médicas: {format_currency(total_medicas)}[/bold]")

        # Assets section
        if declaration.bens_direitos:
            console.print()
            console.print("[header]Bens e Direitos:[/header]")
            bens_table = Table(show_header=True, header_style="bold")
            bens_table.add_column("Grupo")
            bens_table.add_column("Descrição", max_width=50)
            bens_table.add_column("31/12 Anterior", justify="right")
            bens_table.add_column("31/12 Atual", justify="right")
            bens_table.add_column("Variação", justify="right")

            for bem in declaration.bens_direitos[:15]:  # Limit to first 15
                var = bem.variacao_absoluta
                var_style = "green" if var >= 0 else "red"
                var_str = f"[{var_style}]{format_currency(var)}[/{var_style}]"

                bens_table.add_row(
                    bem.grupo.value,
                    bem.discriminacao[:50] + "..." if len(bem.discriminacao) > 50 else bem.discriminacao,
                    format_currency(bem.situacao_anterior),
                    format_currency(bem.situacao_atual),
                    var_str,
                )

            console.print(bens_table)

            if len(declaration.bens_direitos) > 15:
                console.print(f"[muted]... e mais {len(declaration.bens_direitos) - 15} bens[/muted]")

            # Patrimony summary
            resumo = declaration.resumo_patrimonio
            console.print()
            console.print(
                Panel.fit(
                    f"[header]Total Bens (anterior):[/header] {format_currency(resumo.total_bens_anterior)}\n"
                    f"[header]Total Bens (atual):[/header] {format_currency(resumo.total_bens_atual)}\n"
                    f"[header]Variação Patrimonial:[/header] {format_currency(resumo.variacao_patrimonial)}",
                    title="Resumo Patrimonial",
                    border_style="cyan",
                )
            )

        # Run risk analysis
        console.print()
        console.print("[muted]Executando análise de risco...[/muted]")
        result = analyze_declaration(declaration)

        # Risk score panel with color based on level
        score_colors = {
            RiskLevel.LOW: "green",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.HIGH: "red",
            RiskLevel.CRITICAL: "bold red",
        }
        score_color = score_colors.get(result.risk_score.level, "white")

        console.print()
        console.print(
            Panel.fit(
                f"[{score_color}]Score: {result.risk_score.score}/100[/{score_color}]\n"
                f"[{score_color}]Nível: {result.risk_score.level.value}[/{score_color}]",
                title="🎯 Score de Risco - Malha Fina",
                border_style=score_color.replace("bold ", ""),
            )
        )

        # Inconsistencies
        if result.inconsistencies:
            console.print()
            console.print("[header]⚠️  Inconsistências Detectadas:[/header]")
            inc_table = Table(show_header=True, header_style="bold")
            inc_table.add_column("Tipo", style="cyan")
            inc_table.add_column("Descrição")
            inc_table.add_column("Risco", justify="center")
            inc_table.add_column("Recomendação", max_width=40)

            risk_styles = {
                RiskLevel.LOW: "[green]BAIXO[/green]",
                RiskLevel.MEDIUM: "[yellow]MÉDIO[/yellow]",
                RiskLevel.HIGH: "[red]ALTO[/red]",
                RiskLevel.CRITICAL: "[bold red]CRÍTICO[/bold red]",
            }

            for inc in result.inconsistencies:
                inc_table.add_row(
                    inc.tipo.value,
                    inc.descricao,
                    risk_styles.get(inc.risco, inc.risco.value),
                    inc.recomendacao or "-",
                )

            console.print(inc_table)

        # Warnings
        if result.warnings:
            console.print()
            console.print("[header]📋 Avisos:[/header]")
            for warning in result.warnings:
                style = "yellow" if warning.risco == RiskLevel.LOW else "red"
                console.print(f"  [{style}]•[/{style}] {warning.mensagem}")

        # Suggestions
        if result.suggestions:
            console.print()
            console.print("[header]💡 Sugestões de Otimização:[/header]")
            sug_table = Table(show_header=True, header_style="bold")
            sug_table.add_column("Sugestão", style="cyan")
            sug_table.add_column("Descrição")
            sug_table.add_column("Economia Potencial", justify="right", style="green")

            for sug in sorted(result.suggestions, key=lambda x: x.prioridade):
                economia = format_currency(sug.economia_potencial) if sug.economia_potencial else "-"
                sug_table.add_row(sug.titulo, sug.descricao, economia)

            console.print(sug_table)

        # Final summary
        console.print()
        if result.risk_score.score <= 20:
            print_success("✅ Declaração com baixo risco de malha fina!")
        elif result.risk_score.score <= 50:
            console.print("[yellow]⚠️  Declaração com risco moderado. Revise os pontos destacados.[/yellow]")
        else:
            console.print("[red]🚨 Declaração com alto risco! Atenção aos pontos críticos.[/red]")

    except ParseError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        raise typer.Exit(1)


@app.command()
def report(
    arquivo: Annotated[
        Path,
        typer.Argument(
            help="Caminho para arquivo .DEC ou .DBK",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Caminho para arquivo PDF de saída",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Formato de saída: pdf",
        ),
    ] = "pdf",
) -> None:
    """Gera relatório em PDF da análise da declaração."""
    try:
        from irpf_analyzer.infrastructure.reports import generate_pdf_report, REPORTLAB_AVAILABLE

        if not REPORTLAB_AVAILABLE:
            print_error(
                "ReportLab não está instalado. "
                "Instale com: uv sync --extra pdf ou pip install reportlab"
            )
            raise typer.Exit(1)

        # Parse and analyze
        console.print()
        console.print(f"[muted]Parseando {arquivo.name}...[/muted]")
        declaration = parse_dec_file(arquivo)

        console.print("[muted]Executando análise de risco...[/muted]")
        result = analyze_declaration(declaration)

        # Determine output path
        if output is None:
            output = arquivo.with_suffix(".pdf")

        console.print(f"[muted]Gerando relatório PDF...[/muted]")
        generate_pdf_report(declaration, result, output)

        print_success(f"Relatório gerado: {output}")

    except ParseError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except ImportError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        raise typer.Exit(1)


@app.command()
def checklist(
    arquivo: Annotated[
        Path,
        typer.Argument(
            help="Caminho para arquivo .DEC ou .DBK",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Formato de saída: table, json",
        ),
    ] = "table",
) -> None:
    """Gera checklist de documentos necessários baseado nos lançamentos."""
    try:
        from irpf_analyzer.core.services import generate_checklist
        from irpf_analyzer.core.models import DocumentCategory, DocumentPriority

        # Parse
        console.print()
        console.print(f"[muted]Parseando {arquivo.name}...[/muted]")
        declaration = parse_dec_file(arquivo)

        console.print("[muted]Gerando checklist de documentos...[/muted]")
        checklist_result = generate_checklist(declaration)

        # Display header
        console.print()
        console.print(
            Panel.fit(
                f"[header]Contribuinte:[/header] {declaration.contribuinte.nome}\n"
                f"[header]Exercício:[/header] {declaration.ano_exercicio}\n"
                f"[header]Total de documentos:[/header] {checklist_result.total_documentos}",
                title="📋 Checklist de Documentos",
                border_style="blue",
            )
        )

        if output == "json":
            import json
            print(json.dumps(
                [d.model_dump() for d in checklist_result.documentos],
                indent=2,
                default=str,
            ))
            return

        # Group by category
        categories = [
            (DocumentCategory.RENDIMENTOS, "💰 Rendimentos", "green"),
            (DocumentCategory.DEDUCOES, "💊 Deduções", "cyan"),
            (DocumentCategory.BENS_DIREITOS, "🏠 Bens e Direitos", "yellow"),
            (DocumentCategory.DEPENDENTES, "👥 Dependentes", "magenta"),
            (DocumentCategory.ALIENACOES, "📈 Alienações/Vendas", "red"),
        ]

        for category, title, color in categories:
            docs = checklist_result.by_category(category)
            if not docs:
                continue

            console.print()
            console.print(f"[bold {color}]{title}[/bold {color}]")

            cat_table = Table(show_header=True, header_style="bold", expand=True)
            cat_table.add_column("Documento", style="cyan", width=30)
            cat_table.add_column("Descrição", width=40)
            cat_table.add_column("Prioridade", justify="center", width=12)
            cat_table.add_column("Referência", width=30)

            priority_styles = {
                DocumentPriority.OBRIGATORIO: "[bold red]OBRIGATÓRIO[/bold red]",
                DocumentPriority.RECOMENDADO: "[yellow]RECOMENDADO[/yellow]",
                DocumentPriority.OPCIONAL: "[dim]OPCIONAL[/dim]",
            }

            for doc in docs:
                ref = doc.referencia or "-"
                if doc.valor:
                    ref = f"{ref}\n{doc.valor}" if ref != "-" else doc.valor

                cat_table.add_row(
                    doc.nome,
                    doc.descricao,
                    priority_styles.get(doc.prioridade, doc.prioridade.value),
                    ref[:50] if ref else "-",
                )

            console.print(cat_table)

        # Summary
        console.print()
        obrig = len(checklist_result.obrigatorios)
        recom = len(checklist_result.recomendados)
        opc = len(checklist_result.opcionais)

        console.print(
            Panel.fit(
                f"[bold red]Obrigatórios:[/bold red] {obrig}\n"
                f"[yellow]Recomendados:[/yellow] {recom}\n"
                f"[dim]Opcionais:[/dim] {opc}",
                title="Resumo",
                border_style="blue",
            )
        )

        print_success("Checklist gerado com base nos lançamentos da declaração!")

    except ParseError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
