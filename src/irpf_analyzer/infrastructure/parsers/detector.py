"""File format detector for IRPF declaration files."""

from enum import Enum
from pathlib import Path

from irpf_analyzer.shared.exceptions import UnsupportedFileError


class FileType(str, Enum):
    """Supported file types."""

    DEC = "DEC (Declaração Transmitida)"
    DBK = "DBK (Backup)"
    UNKNOWN = "Desconhecido"


def detect_file_type(file_path: Path) -> FileType:
    """
    Detect the type of IRPF declaration file.

    Args:
        file_path: Path to the file

    Returns:
        FileType enum value

    Raises:
        UnsupportedFileError: If file type is not supported
    """
    suffix = file_path.suffix.lower()

    if suffix == ".dec":
        return FileType.DEC
    elif suffix == ".dbk":
        return FileType.DBK
    else:
        raise UnsupportedFileError(
            f"Formato de arquivo não suportado: {suffix}. "
            "Use arquivos .DEC ou .DBK exportados do programa IRPF."
        )


def detect_declaration_year(file_path: Path) -> int | None:
    """
    Try to detect the declaration year from file content or name.

    Args:
        file_path: Path to the file

    Returns:
        Year as integer or None if not detected
    """
    # Try to detect from filename (common pattern: XXXXXXXXXXX2025.dec)
    name = file_path.stem
    for year in range(2010, 2030):
        if str(year) in name:
            return year

    # Try to detect from file content
    try:
        with open(file_path, "r", encoding="latin-1") as f:
            header = f.read(200)

        # Look for year pattern in header
        import re

        match = re.search(r"IRPF(\d{4})", header)
        if match:
            return int(match.group(1))

        # Look for exercise year pattern
        match = re.search(r"EXERCICIO[:\s]*(\d{4})", header, re.IGNORECASE)
        if match:
            return int(match.group(1))

    except Exception:
        pass

    return None


def get_file_info(file_path: Path) -> dict:
    """
    Get basic information about a declaration file.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary with file information
    """
    file_type = detect_file_type(file_path)
    year = detect_declaration_year(file_path)

    return {
        "path": str(file_path),
        "name": file_path.name,
        "type": file_type.value,
        "size_bytes": file_path.stat().st_size,
        "detected_year": year,
    }
