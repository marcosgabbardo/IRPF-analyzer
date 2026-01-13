"""Parser for .DBK files (backup IRPF declarations - before transmission)."""

from pathlib import Path

from irpf_analyzer.core.models import Declaration
from irpf_analyzer.infrastructure.parsers.dec_parser import DECParser


class DBKParser(DECParser):
    """Parser for .DBK files.

    DBK files are backup files created during declaration editing,
    before transmission to Receita Federal. They have the same
    structure as DEC files but may lack transmission-specific data
    like receipt numbers.

    This is useful for validating declarations before submission.
    """

    def parse(self) -> Declaration:
        """Parse the .DBK file and return a Declaration object.

        DBK files have the same structure as DEC files,
        just without transmission receipt data.
        """
        declaration = super().parse()

        # DBK files are not transmitted yet, so clear any receipt data
        # that might have been parsed (shouldn't exist, but for safety)
        if declaration.numero_recibo:
            # Create a new declaration without the receipt
            return Declaration(
                contribuinte=declaration.contribuinte,
                ano_exercicio=declaration.ano_exercicio,
                ano_calendario=declaration.ano_calendario,
                tipo_declaracao=declaration.tipo_declaracao,
                retificadora=declaration.retificadora,
                numero_recibo=None,  # DBK doesn't have receipt
                dependentes=declaration.dependentes,
                rendimentos=declaration.rendimentos,
                deducoes=declaration.deducoes,
                bens_direitos=declaration.bens_direitos,
                dividas=declaration.dividas,
                alienacoes=declaration.alienacoes,
                total_rendimentos_tributaveis=declaration.total_rendimentos_tributaveis,
                total_rendimentos_isentos=declaration.total_rendimentos_isentos,
                total_deducoes=declaration.total_deducoes,
                base_calculo=declaration.base_calculo,
                imposto_devido=declaration.imposto_devido,
                imposto_pago=declaration.imposto_pago,
                saldo_imposto=declaration.saldo_imposto,
            )

        return declaration


def parse_dbk_file(file_path: Path) -> Declaration:
    """Parse a .DBK file and return a Declaration object."""
    parser = DBKParser(file_path)
    return parser.parse()
