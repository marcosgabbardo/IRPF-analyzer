"""Rich console configuration for CLI output."""

from rich.console import Console
from rich.theme import Theme

# Custom theme for IRPF Analyzer
THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "critical": "red bold reverse",
        "success": "green",
        "highlight": "magenta",
        "muted": "dim",
        "header": "bold blue",
        "value": "bold",
        "currency": "green",
        "currency_negative": "red",
        "risk_low": "green",
        "risk_medium": "yellow",
        "risk_high": "red",
        "risk_critical": "red bold reverse",
    }
)

# Global console instance
console = Console(theme=THEME)


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[error]Erro:[/error] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[warning]Aviso:[/warning] {message}")


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[success]{message}[/success]")


def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[info]{message}[/info]")
