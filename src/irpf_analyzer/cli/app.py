"""Main Typer application for IRPF Analyzer."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.panel import Panel
from rich.table import Table

from irpf_analyzer import __version__
from irpf_analyzer.cli.console import console, print_error, print_success
from irpf_analyzer.core.analyzers import analyze_declaration
from irpf_analyzer.core.models import RiskLevel, WarningCategory
from irpf_analyzer.infrastructure.parsers import parse_file, detect_file_type, FileType
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
def debug_assets(
    arquivo: Annotated[
        Path,
        typer.Argument(
            help="Caminho para arquivo .DEC ou .DBK",
            exists=True,
        ),
    ],
    raw: Annotated[
        bool,
        typer.Option("--raw", "-r", help="Mostra bytes brutos das posições para debug"),
    ] = False,
) -> None:
    """Debug: mostra como os bens estão sendo parseados do arquivo.

    Útil para verificar se o grupo de cada bem está sendo extraído corretamente.
    Use --raw para ver os bytes nas diferentes posições.
    """
    from irpf_analyzer.core.models.enums import GrupoBem

    try:
        # Read raw lines
        with open(arquivo, "r", encoding="latin-1") as f:
            lines = f.readlines()

        console.print(Panel.fit(
            f"[header]Arquivo:[/header] {arquivo.name}\n"
            f"[header]Linhas tipo 27 (Bens):[/header] {sum(1 for l in lines if l.startswith('27'))}",
            title="Debug de Bens e Direitos",
            border_style="blue",
        ))

        if raw:
            # Show raw bytes at different positions
            console.print("\n[bold]Bytes brutos (posições 2-20):[/bold]")
            table = Table(show_header=True, header_style="bold")
            table.add_column("#", width=3)
            table.add_column("2-13 (CPF?)", width=12)
            table.add_column("13-15", width=5)
            table.add_column("15-17", width=5)
            table.add_column("17-19", width=5)
            table.add_column("Discriminação (20+)", overflow="fold")

            for i, line in enumerate(lines):
                if line.startswith("27") and i < 30:
                    table.add_row(
                        str(i+1),
                        line[2:13],
                        f"[yellow]{line[13:15]}[/yellow]",
                        f"[cyan]{line[15:17]}[/cyan]",
                        line[17:19],
                        line[19:70].strip(),
                    )
            console.print(table)
            console.print("\n[dim]Legenda: [yellow]13-15[/yellow]=pos atual grupo, [cyan]15-17[/cyan]=pos atual código[/dim]")
            return

        # Grupo mapping
        grupo_mapping = {
            "01": GrupoBem.IMOVEIS,
            "02": GrupoBem.VEICULOS,
            "03": GrupoBem.PARTICIPACOES_SOCIETARIAS,
            "04": GrupoBem.APLICACOES_FINANCEIRAS,
            "05": GrupoBem.POUPANCA,
            "06": GrupoBem.DEPOSITOS_VISTA,
            "07": GrupoBem.FUNDOS,
            "08": GrupoBem.CRIPTOATIVOS,
            "99": GrupoBem.OUTROS_BENS,
        }

        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=4)
        table.add_column("Grupo", width=6)
        table.add_column("Cód", width=5)
        table.add_column("Grupo Mapeado", width=25)
        table.add_column("Discriminação", overflow="fold")
        table.add_column("Valor Atual", justify="right")

        count = 0
        imoveis_count = 0
        for line in lines:
            if line.startswith("27"):
                count += 1
                # Extract fields - CODIGO at 13-14, GRUPO at 15-16 (confirmed from real file)
                codigo = line[13:15]  # Sub-code (e.g., 11=apartamento)
                grupo_cod = line[15:17]  # Main group (e.g., 01=imóveis)
                discriminacao = line[19:531].strip()[:60]

                # Parse value
                valor_atual = "0"
                if len(line) >= 557:
                    try:
                        raw_val = line[544:557].strip()
                        if raw_val and raw_val != "0" * len(raw_val):
                            # Convert to decimal (2 decimal places)
                            val = int(raw_val.lstrip("0") or "0") / 100
                            valor_atual = f"R$ {val:,.2f}"
                    except ValueError:
                        pass

                grupo_enum = grupo_mapping.get(grupo_cod, GrupoBem.OUTROS_BENS)
                grupo_display = f"[green]{grupo_enum.value}[/green]" if grupo_cod == "01" else grupo_enum.value

                if grupo_cod == "01":
                    imoveis_count += 1

                # Highlight IMOVEIS in green
                grupo_style = "[green]" if grupo_cod == "01" else ""
                grupo_end = "[/green]" if grupo_cod == "01" else ""

                table.add_row(
                    str(count),
                    f"{grupo_style}{grupo_cod}{grupo_end}",
                    codigo,
                    grupo_display,
                    discriminacao,
                    valor_atual,
                )

        console.print(table)
        console.print()
        console.print(f"[bold]Total de bens:[/bold] {count}")
        console.print(f"[bold]Total classificados como IMÓVEIS (grupo 01):[/bold] [green]{imoveis_count}[/green]")

    except Exception as e:
        print_error(f"Erro: {e}")
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
        declaration = parse_file(arquivo)

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

        # Patrimony Flow Analysis section
        if result.patrimony_flow:
            flow = result.patrimony_flow
            console.print()
            console.print("[header]📊 Análise de Fluxo Patrimonial:[/header]")

            # Resources table
            flow_table = Table(show_header=True, header_style="bold", title="Origem dos Recursos")
            flow_table.add_column("Fonte", style="cyan")
            flow_table.add_column("Valor", justify="right", style="green")

            flow_table.add_row("Renda declarada (salário, dividendos, rend. fixa)", format_currency(flow.renda_declarada))
            if flow.ganho_capital > 0:
                flow_table.add_row("Ganho de capital (LUCRO das alienações)", format_currency(flow.ganho_capital))
            if flow.lucro_acoes_exterior > 0:
                flow_table.add_row("Lucro em ações estrangeiras", format_currency(flow.lucro_acoes_exterior))

            flow_table.add_row("", "")  # Empty row
            flow_table.add_row("[bold]TOTAL RECURSOS[/bold]", f"[bold]{format_currency(flow.recursos_totais)}[/bold]")

            # Show informational values that are NOT counted (principal already in patrimony)
            if flow.valor_alienacoes > 0 or flow.ativos_liquidados > 0:
                flow_table.add_row("", "")
                flow_table.add_row("[dim]--- Valores informativos (não contados) ---[/dim]", "")
                if flow.valor_alienacoes > 0:
                    flow_table.add_row("[dim]Valor bruto de vendas[/dim]", f"[dim]{format_currency(flow.valor_alienacoes)}[/dim]")
                if flow.ativos_liquidados > 0:
                    flow_table.add_row("[dim]Ativos liquidados (principal)[/dim]", f"[dim]{format_currency(flow.ativos_liquidados)}[/dim]")

            console.print(flow_table)

            # Calculation panel
            console.print()
            saldo_style = "green" if flow.saldo >= 0 else "red"
            status_explicado = "✅ EXPLICADO" if flow.explicado else "⚠️ NÃO EXPLICADO"
            status_color = "green" if flow.explicado else "yellow"

            console.print(
                Panel.fit(
                    f"[header]Recursos totais:[/header] {format_currency(flow.recursos_totais)}\n"
                    f"[header](-) Despesas de vida estimadas:[/header] {format_currency(flow.despesas_vida_estimadas)}\n"
                    f"[header](=) Recursos disponíveis:[/header] {format_currency(flow.recursos_disponiveis)}\n"
                    f"[header](-) Variação patrimonial:[/header] {format_currency(flow.variacao_patrimonial)}\n"
                    f"[header](=) Saldo:[/header] [{saldo_style}]{format_currency(flow.saldo)}[/{saldo_style}]\n\n"
                    f"[{status_color}]{status_explicado}[/{status_color}]",
                    title="Cálculo de Compatibilidade",
                    border_style="cyan",
                )
            )

            # Disclaimer
            console.print(f"[dim]ℹ️  {flow.disclaimer_despesas}[/dim]")

        # Risk score panel with color based on level (higher = safer)
        score_colors = {
            RiskLevel.LOW: "green",      # 80-100% = safe
            RiskLevel.MEDIUM: "yellow",  # 50-79% = moderate
            RiskLevel.HIGH: "red",       # 25-49% = risky
            RiskLevel.CRITICAL: "bold red",  # 0-24% = critical
        }
        score_color = score_colors.get(result.risk_score.level, "white")

        # Status message based on score
        score = result.risk_score.score
        if score >= 80:
            status = "Excelente - Baixo risco de malha fina"
        elif score >= 50:
            status = "Atenção - Risco moderado"
        elif score >= 25:
            status = "Alerta - Risco elevado"
        else:
            status = "Crítico - Alto risco de malha fina"

        console.print()
        console.print(
            Panel.fit(
                f"[{score_color}]Conformidade: {score}%[/{score_color}]\n"
                f"[{score_color}]{status}[/{score_color}]",
                title="🎯 Índice de Conformidade Fiscal",
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

        # Separate pattern warnings from regular warnings
        pattern_warnings = [w for w in result.warnings if w.categoria == WarningCategory.PADRAO]
        regular_warnings = [w for w in result.warnings if w.categoria != WarningCategory.PADRAO]

        # Regular Warnings
        if regular_warnings:
            console.print()
            console.print("[header]📋 Avisos:[/header]")
            for warning in regular_warnings:
                style = "yellow" if warning.risco == RiskLevel.LOW else "red"
                console.print(f"  [{style}]•[/{style}] {warning.mensagem}")

        # Pattern Detection Warnings (separate section)
        if pattern_warnings:
            console.print()
            console.print("[header]🔍 Padrões Detectados:[/header]")
            for warning in pattern_warnings:
                style = "yellow" if warning.risco == RiskLevel.LOW else "red"
                info_tag = " [dim](informativo)[/dim]" if warning.informativo else ""
                console.print(f"  [{style}]•[/{style}] {warning.mensagem}{info_tag}")

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

        # Final summary (higher score = safer)
        console.print()
        if result.risk_score.score >= 80:
            print_success("✅ Declaração com baixo risco de malha fina!")
        elif result.risk_score.score >= 50:
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
        declaration = parse_file(arquivo)

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
        declaration = parse_file(arquivo)

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


@app.command()
def compare(
    arquivo1: Annotated[
        Path,
        typer.Argument(
            help="Primeiro arquivo .DEC ou .DBK",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    arquivo2: Annotated[
        Path,
        typer.Argument(
            help="Segundo arquivo .DEC ou .DBK",
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
    """Compara duas declarações de anos diferentes mostrando evolução patrimonial."""
    try:
        from irpf_analyzer.core.analyzers.comparison import compare_declarations

        # Parse both files
        console.print()
        console.print(f"[muted]Parseando {arquivo1.name}...[/muted]")
        decl1 = parse_file(arquivo1)

        console.print(f"[muted]Parseando {arquivo2.name}...[/muted]")
        decl2 = parse_file(arquivo2)

        console.print("[muted]Comparando declarações...[/muted]")
        result = compare_declarations(decl1, decl2)

        # JSON output
        if output == "json":
            import json
            print(json.dumps(result.model_dump(), indent=2, default=str))
            return

        # Table output
        _display_comparison(result)

        print_success(f"Comparação {result.periodo_label} concluída!")

    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except ParseError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        raise typer.Exit(1)


@app.command(name="analyze-multi")
def analyze_multi(
    arquivos: Annotated[
        list[Path],
        typer.Argument(
            help="Arquivos .DEC/.DBK de diferentes anos (mínimo 2)",
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
    """Análise de padrões temporais comparando múltiplos anos.

    Detecta padrões suspeitos que só aparecem ao comparar declarações
    de diferentes anos, como:

    - Renda estagnada com patrimônio crescente
    - Quedas súbitas de renda
    - Despesas médicas constantes
    - Padrões de liquidação de ativos
    """
    try:
        from irpf_analyzer.core.analyzers.temporal import (
            TemporalPatternAnalyzer,
            TemporalPattern,
        )

        # Validate minimum files
        if len(arquivos) < 2:
            print_error("Forneça pelo menos 2 arquivos de anos diferentes")
            raise typer.Exit(1)

        # Check all files exist
        for arq in arquivos:
            if not arq.exists():
                print_error(f"Arquivo não encontrado: {arq}")
                raise typer.Exit(1)

        # Parse all declarations
        console.print()
        declarations = []
        for arq in arquivos:
            console.print(f"[muted]Parseando {arq.name}...[/muted]")
            decl = parse_file(arq)
            declarations.append(decl)

        # Run temporal analysis
        console.print("[muted]Analisando padrões temporais...[/muted]")
        try:
            analyzer = TemporalPatternAnalyzer(declarations)
            patterns = analyzer.analyze()
        except ValueError as e:
            print_error(str(e))
            raise typer.Exit(1)

        # JSON output
        if output == "json":
            import json
            output_data = {
                "contribuinte": analyzer.contribuinte_nome,
                "periodo": analyzer.periodo,
                "patterns": [p.model_dump() for p in patterns],
            }
            print(json.dumps(output_data, indent=2, default=str))
            return

        # Display results
        _display_temporal_patterns(analyzer, patterns)

        if patterns:
            console.print()
            console.print(
                f"[yellow]⚠️  {len(patterns)} padrão(ões) temporal(is) detectado(s)[/yellow]"
            )
        else:
            print_success("Nenhum padrão temporal suspeito detectado!")

    except ParseError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        raise typer.Exit(1)


def _display_temporal_patterns(analyzer, patterns: list) -> None:
    """Display temporal pattern analysis results."""
    from irpf_analyzer.core.models import RiskLevel

    # Header
    console.print()
    console.print(
        Panel.fit(
            f"[header]Contribuinte:[/header] {analyzer.contribuinte_nome}\n"
            f"[header]Período:[/header] {analyzer.periodo}\n"
            f"[header]Declarações analisadas:[/header] {len(analyzer.declarations)}",
            title="📊 Análise Temporal Multi-Ano",
            border_style="blue",
        )
    )

    # Show year-over-year summary
    console.print()
    console.print("[header]Evolução Anual:[/header]")
    summary_table = Table(show_header=True, header_style="bold")
    summary_table.add_column("Ano", style="cyan")
    summary_table.add_column("Renda Total", justify="right")
    summary_table.add_column("Patrimônio", justify="right")
    summary_table.add_column("Desp. Médicas", justify="right")

    for decl in analyzer.declarations:
        renda = decl.total_rendimentos_tributaveis + decl.total_rendimentos_isentos
        patrimonio = decl.resumo_patrimonio.total_bens_atual
        desp_medicas = decl.resumo_deducoes.despesas_medicas

        summary_table.add_row(
            str(decl.ano_exercicio),
            format_currency(renda),
            format_currency(patrimonio),
            format_currency(desp_medicas),
        )

    console.print(summary_table)

    # Show detected patterns
    if patterns:
        console.print()
        console.print("[header]⚠️  Padrões Temporais Detectados:[/header]")

        risk_styles = {
            RiskLevel.LOW: "green",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.HIGH: "red",
            RiskLevel.CRITICAL: "bold red",
        }

        for pattern in patterns:
            color = risk_styles.get(pattern.risco, "white")
            anos_str = ", ".join(str(a) for a in pattern.anos_afetados)

            console.print()
            console.print(
                Panel(
                    f"[header]Tipo:[/header] {pattern.tipo.value}\n\n"
                    f"{pattern.descricao}\n\n"
                    f"[header]Anos afetados:[/header] {anos_str}\n"
                    f"[header]Risco:[/header] [{color}]{pattern.risco.value}[/{color}]\n"
                    + (f"[header]Valor impacto:[/header] {format_currency(pattern.valor_impacto)}\n"
                       if pattern.valor_impacto else "")
                    + (f"\n[dim]💡 {pattern.recomendacao}[/dim]"
                       if pattern.recomendacao else ""),
                    border_style=color.replace("bold ", ""),
                )
            )
    else:
        console.print()
        console.print(
            Panel.fit(
                "[green]✅ Nenhum padrão temporal suspeito detectado[/green]\n\n"
                "A evolução da declaração ao longo dos anos está consistente.",
                border_style="green",
            )
        )


def _display_comparison(result) -> None:
    """Display comparison results using Rich tables and panels."""
    from irpf_analyzer.core.models.comparison import ComparisonResult

    result: ComparisonResult = result

    # Header
    console.print()
    console.print(
        Panel.fit(
            f"[header]Contribuinte:[/header] {result.nome_contribuinte}\n"
            f"[header]CPF:[/header] ***.***.***-{result.cpf[-2:]}\n"
            f"[header]Período:[/header] {result.periodo_label}",
            title="📊 Comparativo de Declarações IRPF",
            border_style="blue",
        )
    )

    # Warnings (if any)
    if result.avisos:
        console.print()
        console.print("[yellow]⚠️  Avisos:[/yellow]")
        for aviso in result.avisos:
            console.print(f"  [yellow]•[/yellow] {aviso}")

    # Income comparison
    console.print()
    console.print("[header]💰 Comparativo de Rendimentos:[/header]")
    income_table = Table(show_header=True, header_style="bold")
    income_table.add_column("Tipo", style="cyan")
    income_table.add_column(str(result.ano_anterior), justify="right")
    income_table.add_column(str(result.ano_atual), justify="right")
    income_table.add_column("Variação", justify="right")

    for item in [
        result.rendimentos.total_tributaveis,
        result.rendimentos.total_isentos,
        result.rendimentos.total_exclusivos,
    ]:
        income_table.add_row(
            item.campo,
            format_currency(item.valor_anterior),
            format_currency(item.valor_atual),
            _format_variation(item.variacao_absoluta, item.variacao_percentual),
        )

    # Total row
    total = result.rendimentos.total_geral
    income_table.add_row("", "", "", "")  # Empty row
    income_table.add_row(
        f"[bold]{total.campo}[/bold]",
        f"[bold]{format_currency(total.valor_anterior)}[/bold]",
        f"[bold]{format_currency(total.valor_atual)}[/bold]",
        _format_variation(total.variacao_absoluta, total.variacao_percentual, bold=True),
    )
    console.print(income_table)

    # Deductions comparison
    console.print()
    console.print("[header]💊 Comparativo de Deduções:[/header]")
    ded_table = Table(show_header=True, header_style="bold")
    ded_table.add_column("Categoria", style="cyan")
    ded_table.add_column(str(result.ano_anterior), justify="right")
    ded_table.add_column(str(result.ano_atual), justify="right")
    ded_table.add_column("Variação", justify="right")

    deductions = [
        result.deducoes.previdencia_oficial,
        result.deducoes.previdencia_privada,
        result.deducoes.despesas_medicas,
        result.deducoes.despesas_educacao,
        result.deducoes.pensao_alimenticia,
        result.deducoes.dependentes,
        result.deducoes.outras,
    ]

    for item in deductions:
        # Skip zero values in both years
        if item.valor_anterior == 0 and item.valor_atual == 0:
            continue
        ded_table.add_row(
            item.campo,
            format_currency(item.valor_anterior),
            format_currency(item.valor_atual),
            _format_variation(item.variacao_absoluta, item.variacao_percentual),
        )

    # Total deductions
    total_ded = result.deducoes.total_deducoes
    ded_table.add_row("", "", "", "")
    ded_table.add_row(
        f"[bold]{total_ded.campo}[/bold]",
        f"[bold]{format_currency(total_ded.valor_anterior)}[/bold]",
        f"[bold]{format_currency(total_ded.valor_atual)}[/bold]",
        _format_variation(total_ded.variacao_absoluta, total_ded.variacao_percentual, bold=True),
    )
    console.print(ded_table)

    # Patrimony comparison
    console.print()
    console.print("[header]🏠 Evolução Patrimonial:[/header]")

    pat = result.patrimonio
    console.print(
        Panel.fit(
            f"[header]Patrimônio Líquido {result.ano_anterior}:[/header] {format_currency(pat.patrimonio_liquido_ano_anterior)}\n"
            f"[header]Patrimônio Líquido {result.ano_atual}:[/header] {format_currency(pat.patrimonio_liquido_ano_atual)}\n"
            f"[header]Variação:[/header] {_format_variation(pat.patrimonio_liquido.variacao_absoluta, pat.patrimonio_liquido.variacao_percentual)}",
            title="Patrimônio Líquido",
            border_style="cyan",
        )
    )

    # Patrimony by category
    if pat.por_categoria:
        console.print()
        console.print("[header]Patrimônio por Categoria:[/header]")
        cat_table = Table(show_header=True, header_style="bold")
        cat_table.add_column("Categoria", style="cyan")
        cat_table.add_column(str(result.ano_anterior), justify="right")
        cat_table.add_column(str(result.ano_atual), justify="right")
        cat_table.add_column("Variação", justify="right")

        for cat_name, item in sorted(pat.por_categoria.items(), key=lambda x: -x[1].valor_atual):
            cat_table.add_row(
                cat_name,
                format_currency(item.valor_anterior),
                format_currency(item.valor_atual),
                _format_variation(item.variacao_absoluta, item.variacao_percentual),
            )

        console.print(cat_table)

    # Tax comparison
    console.print()
    console.print("[header]📋 Impacto Tributário:[/header]")
    tax_table = Table(show_header=True, header_style="bold")
    tax_table.add_column("Item", style="cyan")
    tax_table.add_column(str(result.ano_anterior), justify="right")
    tax_table.add_column(str(result.ano_atual), justify="right")
    tax_table.add_column("Variação", justify="right")

    tax_items = [
        result.impostos.base_calculo,
        result.impostos.imposto_devido,
        result.impostos.imposto_pago,
    ]

    for item in tax_items:
        tax_table.add_row(
            item.campo,
            format_currency(item.valor_anterior),
            format_currency(item.valor_atual),
            _format_variation(item.variacao_absoluta, item.variacao_percentual),
        )

    # Net tax (saldo)
    saldo = result.impostos.saldo_imposto
    saldo_ant_label = "restituição" if saldo.valor_anterior < 0 else "a pagar"
    saldo_atu_label = "restituição" if saldo.valor_atual < 0 else "a pagar"

    tax_table.add_row("", "", "", "")
    tax_table.add_row(
        "[bold]Resultado[/bold]",
        f"[bold]{format_currency(abs(saldo.valor_anterior))}[/bold] ({saldo_ant_label})",
        f"[bold]{format_currency(abs(saldo.valor_atual))}[/bold] ({saldo_atu_label})",
        "",
    )
    console.print(tax_table)

    # Asset highlights
    if result.destaques_ativos:
        console.print()
        console.print("[header]🔍 Destaques de Ativos:[/header]")

        gainers = [h for h in result.destaques_ativos if h.tipo == "gainer"]
        losers = [h for h in result.destaques_ativos if h.tipo == "loser"]
        new_assets = [h for h in result.destaques_ativos if h.tipo == "new"]
        redeemed = [h for h in result.destaques_ativos if h.tipo == "redeemed"]
        sold = [h for h in result.destaques_ativos if h.tipo == "sold"]

        if gainers:
            console.print()
            console.print("[green]Maiores Valorizações:[/green]")
            for h in gainers[:3]:
                pct = f" ({h.variacao_percentual:+.1f}%)" if h.variacao_percentual else ""
                console.print(
                    f"  [green]▲[/green] {h.descricao}: {format_currency(h.variacao_absoluta)}{pct}"
                )

        if losers:
            console.print()
            console.print("[red]Maiores Desvalorizações:[/red]")
            for h in losers[:3]:
                pct = f" ({h.variacao_percentual:.1f}%)" if h.variacao_percentual else ""
                console.print(
                    f"  [red]▼[/red] {h.descricao}: {format_currency(h.variacao_absoluta)}{pct}"
                )

        if new_assets:
            console.print()
            console.print("[blue]Novos Ativos:[/blue]")
            for h in new_assets[:3]:
                console.print(
                    f"  [blue]+[/blue] [dim]({h.grupo})[/dim] {h.descricao}: {format_currency(h.valor_ano_atual)}"
                )

        if redeemed:
            console.print()
            console.print("[cyan]Ativos Resgatados/Liquidados:[/cyan]")
            for h in redeemed[:3]:
                console.print(
                    f"  [cyan]↩[/cyan] [dim]({h.grupo})[/dim] {h.descricao}: {format_currency(h.valor_ano_anterior)}"
                )

        if sold:
            console.print()
            console.print("[yellow]Ativos Vendidos/Encerrados:[/yellow]")
            for h in sold[:3]:
                console.print(
                    f"  [yellow]-[/yellow] [dim]({h.grupo})[/dim] {h.descricao}: {format_currency(h.valor_ano_anterior)}"
                )


def _format_variation(absoluta, percentual, bold: bool = False) -> str:
    """Format variation with color and percentage."""
    from decimal import Decimal

    if absoluta == 0:
        return "[dim]-[/dim]"

    color = "green" if absoluta > 0 else "red"
    sign = "+" if absoluta > 0 else ""

    if percentual is not None:
        pct_str = f" ({sign}{percentual:.1f}%)"
    else:
        pct_str = " (novo)" if absoluta > 0 else ""

    value = f"{sign}{format_currency(absoluta)}{pct_str}"

    if bold:
        return f"[bold {color}]{value}[/bold {color}]"
    return f"[{color}]{value}[/{color}]"


if __name__ == "__main__":
    app()
