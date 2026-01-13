"""File parsers for IRPF declaration formats."""

from pathlib import Path

from irpf_analyzer.core.models import Declaration
from irpf_analyzer.infrastructure.parsers.dec_parser import DECParser, parse_dec_file
from irpf_analyzer.infrastructure.parsers.dbk_parser import DBKParser, parse_dbk_file
from irpf_analyzer.infrastructure.parsers.detector import (
    FileType,
    detect_file_type,
    detect_declaration_year,
    get_file_info,
)
from irpf_analyzer.shared.exceptions import UnsupportedFileError


def parse_file(file_path: Path) -> Declaration:
    """Parse an IRPF declaration file (DEC or DBK).

    Auto-detects the file format and uses the appropriate parser.

    Args:
        file_path: Path to the .DEC or .DBK file

    Returns:
        Declaration object with parsed data

    Raises:
        UnsupportedFileError: If file format is not supported
        ParseError: If file cannot be parsed
    """
    file_type = detect_file_type(file_path)

    if file_type == FileType.DEC:
        return parse_dec_file(file_path)
    elif file_type == FileType.DBK:
        return parse_dbk_file(file_path)
    else:
        raise UnsupportedFileError(
            f"Formato de arquivo não suportado: {file_path.suffix}. "
            "Use arquivos .DEC ou .DBK exportados do programa IRPF."
        )


__all__ = [
    "DECParser",
    "DBKParser",
    "parse_dec_file",
    "parse_dbk_file",
    "parse_file",
    "FileType",
    "detect_file_type",
    "detect_declaration_year",
    "get_file_info",
]
