"""Parser for .DEC files (transmitted IRPF declarations)."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from irpf_analyzer.core.models import (
    Declaration,
    Rendimento,
    Deducao,
    BemDireito,
    Dependente,
    TipoDeclaracao,
    TipoRendimento,
    TipoDeducao,
    GrupoBem,
)
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.income import FontePagadora
from irpf_analyzer.core.models.patrimony import Divida
from irpf_analyzer.core.models.enums import TipoDependente
from irpf_analyzer.core.models.alienation import Alienacao
from irpf_analyzer.shared.exceptions import ParseError, CorruptedFileError


def _parse_decimal(value: str, decimals: int = 2) -> Decimal:
    """Parse a string value to Decimal with implicit decimal places."""
    value = value.strip()

    # Return 0 for empty or all-zero values
    if not value:
        return Decimal("0")

    # Remove any non-digit characters except minus sign
    clean_value = ""
    negative = False
    for c in value:
        if c == "-":
            negative = True
        elif c.isdigit():
            clean_value += c

    if not clean_value or clean_value == "0" * len(clean_value):
        return Decimal("0")

    # Insert decimal point
    if len(clean_value) <= decimals:
        clean_value = "0." + clean_value.zfill(decimals)
    else:
        clean_value = clean_value[:-decimals] + "." + clean_value[-decimals:]

    try:
        result = Decimal(clean_value)
        return -result if negative else result
    except Exception:
        return Decimal("0")


def _parse_date(value: str) -> Optional[date]:
    """Parse date in DDMMYYYY format."""
    value = value.strip()
    if not value or len(value) != 8 or value == "0" * 8:
        return None
    try:
        return date(
            year=int(value[4:8]),
            month=int(value[2:4]),
            day=int(value[0:2])
        )
    except (ValueError, IndexError):
        return None


def _parse_datetime(value: str) -> Optional[datetime]:
    """Parse datetime in DDMMYYYYHHmmSS format."""
    value = value.strip()
    if not value or len(value) < 14:
        return None
    try:
        return datetime(
            year=int(value[4:8]),
            month=int(value[2:4]),
            day=int(value[0:2]),
            hour=int(value[8:10]),
            minute=int(value[10:12]),
            second=int(value[12:14])
        )
    except (ValueError, IndexError):
        return None


@dataclass
class ParsedHeader:
    """Parsed header information."""
    ano_exercicio: int
    ano_calendario: int
    cpf: str
    nome: str
    uf: str
    tipo_declaracao: TipoDeclaracao
    retificadora: bool
    numero_recibo: Optional[str] = None


class DECParser:
    """Parser for .DEC files."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.lines: list[str] = []
        self._header: Optional[ParsedHeader] = None

    def parse(self) -> Declaration:
        """Parse the .DEC file and return a Declaration object."""
        self._read_file()

        if not self.lines:
            raise CorruptedFileError("Arquivo vazio")

        # Parse header (line 1)
        self._header = self._parse_header(self.lines[0])

        # Parse contribuinte data (line starting with 16)
        contribuinte = self._parse_contribuinte()

        # Parse summary values (line starting with 20)
        totals = self._parse_totals()

        # Parse dependents (lines starting with 25)
        dependentes = self._parse_dependentes()

        # Parse medical expenses (lines starting with 26)
        deducoes = self._parse_deducoes()

        # Parse assets (lines starting with 27)
        bens_direitos = self._parse_bens_direitos()

        # Parse alienations/sales (lines starting with 63)
        alienacoes = self._parse_alienacoes()

        # Build declaration
        return Declaration(
            contribuinte=contribuinte,
            ano_exercicio=self._header.ano_exercicio,
            ano_calendario=self._header.ano_calendario,
            tipo_declaracao=self._header.tipo_declaracao,
            retificadora=self._header.retificadora,
            numero_recibo=self._header.numero_recibo,
            dependentes=dependentes,
            deducoes=deducoes,
            bens_direitos=bens_direitos,
            alienacoes=alienacoes,
            total_rendimentos_tributaveis=totals.get("rendimentos_tributaveis", Decimal("0")),
            total_rendimentos_isentos=totals.get("rendimentos_isentos", Decimal("0")),
            total_deducoes=totals.get("deducoes", Decimal("0")),
            base_calculo=totals.get("base_calculo", Decimal("0")),
            imposto_devido=totals.get("imposto_devido", Decimal("0")),
            imposto_pago=totals.get("imposto_pago", Decimal("0")),
            saldo_imposto=totals.get("saldo_imposto", Decimal("0")),
        )

    def _read_file(self) -> None:
        """Read the file contents."""
        try:
            with open(self.file_path, "r", encoding="latin-1") as f:
                self.lines = [line.rstrip("\r\n") for line in f.readlines()]
        except Exception as e:
            raise ParseError(f"Erro ao ler arquivo: {e}")

    def _parse_header(self, line: str) -> ParsedHeader:
        """Parse the header line."""
        if not line.startswith("IRPF"):
            raise CorruptedFileError("Arquivo não começa com IRPF - formato inválido")

        # Header structure (positions are approximate):
        # IRPF    YYYYAAAA...CPF...NOME...
        # Positions:
        # 0-8: IRPF + spaces
        # 8-12: ano exercício (YYYY)
        # 12-16: ano calendário (YYYY)
        # 16-18: código (35 = original?)
        # 18-21: zeros
        # 21-32: CPF (11 dígitos)
        # 32-38: código
        # 38-98: Nome (60 chars)
        # 98-100: UF

        try:
            ano_exercicio = int(line[8:12])
            ano_calendario = int(line[12:16])
            cpf = line[21:32].strip()
            nome = line[38:98].strip()
            uf = line[98:100].strip()

            # Determine declaration type from later in header or from line 16
            # For now, default to COMPLETA
            tipo = TipoDeclaracao.COMPLETA
            retificadora = False

            return ParsedHeader(
                ano_exercicio=ano_exercicio,
                ano_calendario=ano_calendario,
                cpf=cpf,
                nome=nome,
                uf=uf,
                tipo_declaracao=tipo,
                retificadora=retificadora,
            )
        except (ValueError, IndexError) as e:
            raise CorruptedFileError(f"Erro ao parsear header: {e}")

    def _parse_contribuinte(self) -> Contribuinte:
        """Parse taxpayer data from line type 16."""
        if not self._header:
            raise ParseError("Header não parseado")

        # Find line starting with 16
        for line in self.lines:
            if line.startswith("16"):
                # Line 16 structure:
                # 16 + CPF(11) + NOME(60) + TIPO_LOGRADOURO(15) + LOGRADOURO(40) +
                # NUMERO(6) + COMPLEMENTO(21) + BAIRRO(19) + CEP(8) + COD_MUNICIPIO(4) +
                # MUNICIPIO(40) + UF(2) + COD_PAIS(3) + EMAIL(70) + ...

                cpf = line[2:13].strip()
                nome = line[13:73].strip()

                # Parse birth date from position ~200+
                # Looking for pattern DDMMYYYY
                data_nasc = None
                # The birth date appears around position 177-185 based on the sample
                if len(line) > 185:
                    data_nasc = _parse_date(line[177:185])

                return Contribuinte(
                    cpf=cpf,
                    nome=nome,
                    data_nascimento=data_nasc,
                )

        # Fallback to header data
        return Contribuinte(
            cpf=self._header.cpf,
            nome=self._header.nome,
        )

    def _parse_totals(self) -> dict[str, Decimal]:
        """Parse summary totals from line type 20.

        Field positions discovered from real DEC file analysis:
        - Position 106-119: Rendimentos tributáveis (13 digits, 2 decimals)
        - Position 227-240: Imposto devido (13 digits, 2 decimals)
        - Position 471-482: Rendimentos isentos e não tributáveis (11 digits, 2 decimals)
        - Position 500-508: Imposto pago (total) (8 digits, 2 decimals)

        Note: Field widths vary. Positions verified against real file with known values.
        """
        totals: dict[str, Decimal] = {}

        for line in self.lines:
            if line.startswith("20") or line.startswith("208"):
                # Line 20 contains financial summary
                if len(line) > 520:
                    # Field positions based on DEC layout analysis
                    totals["rendimentos_tributaveis"] = _parse_decimal(line[106:119])
                    totals["imposto_devido"] = _parse_decimal(line[227:240])

                    # Rendimentos isentos e não tributáveis (dividends, poupança, etc.)
                    # 11-digit field at position 471-482
                    totals["rendimentos_isentos"] = _parse_decimal(line[471:482])

                    # Imposto pago (total) - 8-digit field at position 500-508
                    totals["imposto_pago"] = _parse_decimal(line[500:508])

                elif len(line) > 400:
                    # Fallback for shorter lines
                    totals["rendimentos_tributaveis"] = _parse_decimal(line[106:119])
                    totals["imposto_devido"] = _parse_decimal(line[227:240])
                    totals["imposto_pago"] = _parse_decimal(line[257:270])

                break

        return totals

    def _parse_dependentes(self) -> list[Dependente]:
        """Parse dependents from lines type 25."""
        dependentes = []

        for line in self.lines:
            if line.startswith("25"):
                # Line 25 structure (observed from real file):
                # 25 + CPF_TITULAR(11) + SEQ(4) + FLAG(1) + TIPO(2) + NOME(60) + DATA_NASC(8) + CPF_DEP(11)
                # Example: 25831580730720000121LUCAS LOPES GABBARDO...2906201705476308083
                #          ^^           ^^^^  ^  ^^
                #          25  CPF(11)  SEQ   F  TIPO

                try:
                    # Position 13-17: sequence number (0000)
                    # Position 17-18: flag (1)
                    # Position 18-20: type code (e.g., 21 = filho até 21)
                    tipo_cod = line[18:20].strip()
                    # Position 20-80: name (60 chars)
                    nome = line[20:80].strip()
                    # Position 80-88: birth date DDMMYYYY
                    data_nasc = _parse_date(line[80:88])
                    # Position 88-99: CPF of dependent (11 digits)
                    cpf_dep = line[88:99].strip()

                    # Map type code to enum
                    tipo = self._map_tipo_dependente(tipo_cod)

                    if nome and cpf_dep:
                        dependentes.append(Dependente(
                            tipo=tipo,
                            cpf=cpf_dep,
                            nome=nome,
                            data_nascimento=data_nasc,
                        ))
                except (IndexError, ValueError):
                    continue

        return dependentes

    def _map_tipo_dependente(self, codigo: str) -> TipoDependente:
        """Map dependente type code to enum."""
        mapping = {
            "21": TipoDependente.FILHO_ENTEADO_ATE_21,
            "22": TipoDependente.FILHO_ENTEADO_UNIVERSITARIO,
            "23": TipoDependente.FILHO_ENTEADO_INCAPAZ,
            "11": TipoDependente.CONJUGE,
            "12": TipoDependente.COMPANHEIRO,
            "31": TipoDependente.IRMAO_NETO_BISNETO,
            "41": TipoDependente.PAIS_AVOS_BISAVOS,
            "51": TipoDependente.MENOR_POBRE,
            "61": TipoDependente.INCAPAZ_TUTELADO,
        }
        return mapping.get(codigo, TipoDependente.FILHO_ENTEADO_ATE_21)

    def _parse_deducoes(self) -> list[Deducao]:
        """Parse deductions from lines type 26 (medical expenses)."""
        deducoes = []

        for line in self.lines:
            if line.startswith("26"):
                # Line 26 structure (medical expenses) - discovered positions:
                # 26 + CPF_TITULAR(11) + TIPO(2) + SEQ(5) + CNPJ(14) + NOME(60) + VALOR(13)
                # Positions:
                # - 20-34: CNPJ (14 digits)
                # - 34-94: Nome prestador (60 chars)
                # - 105-118: Valor (13 digits, 2 decimal places)

                try:
                    # Extract CNPJ (position 20-34)
                    cnpj = line[20:34].strip()
                    # Extract name (position 34-94)
                    nome = line[34:94].strip()
                    # Extract value (position 105-118)
                    valor = _parse_decimal(line[105:118])

                    if valor > 0 and nome:
                        deducoes.append(Deducao(
                            tipo=TipoDeducao.DESPESAS_MEDICAS,
                            valor=valor,
                            cnpj_prestador=cnpj,
                            nome_prestador=nome,
                        ))
                except (IndexError, ValueError):
                    continue

        return deducoes

    def _parse_bens_direitos(self) -> list[BemDireito]:
        """Parse assets from lines type 27."""
        bens = []

        for line in self.lines:
            if line.startswith("27"):
                # Line 27 structure (assets) - observed from real file:
                # 27 + CPF_TITULAR(11) + GRUPO(2) + COD(2) + TIPO_SIT(2) +
                # DISCRIMINACAO(~512 chars padded) + VALOR_ANTERIOR(13) + VALOR_ATUAL(13) + rest...
                #
                # Fixed positions discovered:
                # - Position 19-530: Discriminação (padded with spaces)
                # - Position 531-544: Valor em 31/12 do ano anterior (13 dígitos)
                # - Position 544-557: Valor em 31/12 do ano atual (13 dígitos)
                # - Position 1188-1201: Lucro/Prejuízo aplicação financeira (13 dígitos)
                #   Used for foreign stocks where profit/loss is declared within the asset

                try:
                    grupo_cod = line[13:15]
                    codigo = line[15:17]

                    # Discriminação: position 19 to ~530 (padded)
                    discriminacao = line[19:531].strip()

                    # Values at fixed positions (13 digits each)
                    valor_anterior = Decimal("0")
                    valor_atual = Decimal("0")
                    lucro_prejuizo = Decimal("0")

                    if len(line) >= 557:
                        valor_anterior = _parse_decimal(line[531:544])
                        valor_atual = _parse_decimal(line[544:557])

                    # Lucro/Prejuízo field (position 1185-1199, 14 chars, 3 decimal places)
                    # Used for foreign stocks (grupo 01, codigo 12) and similar
                    if len(line) >= 1199:
                        lucro_prejuizo = _parse_decimal(line[1185:1199], decimals=3)

                    # Map grupo code to enum
                    grupo = self._map_grupo_bem(grupo_cod)

                    # Clean up discriminação (remove excessive spaces)
                    discriminacao = " ".join(discriminacao.split())

                    if discriminacao:
                        bens.append(BemDireito(
                            grupo=grupo,
                            codigo=codigo,
                            discriminacao=discriminacao[:500],
                            situacao_anterior=valor_anterior,
                            situacao_atual=valor_atual,
                            lucro_prejuizo=lucro_prejuizo,
                        ))

                except (IndexError, ValueError):
                    continue

        return bens

    def _map_grupo_bem(self, codigo: str) -> GrupoBem:
        """Map asset group code to enum."""
        mapping = {
            "01": GrupoBem.IMOVEIS,
            "02": GrupoBem.VEICULOS,
            "03": GrupoBem.PARTICIPACOES_SOCIETARIAS,
            "04": GrupoBem.APLICACOES_FINANCEIRAS,
            "05": GrupoBem.POUPANCA,
            "06": GrupoBem.DEPOSITOS_VISTA,
            "07": GrupoBem.FUNDOS,
            "08": GrupoBem.CRIPTOATIVOS,
            "99": GrupoBem.OUTROS_BENS,
            "11": GrupoBem.IMOVEIS,  # Alternative code for real estate
            "12": GrupoBem.IMOVEIS,
            "13": GrupoBem.IMOVEIS,
        }
        return mapping.get(codigo, GrupoBem.OUTROS_BENS)

    def _parse_alienacoes(self) -> list[Alienacao]:
        """Parse alienations/sales from lines type 63.

        Field positions discovered from real DEC file analysis:
        - Position 36-96: Nome do bem (60 chars)
        - Position 449-458: Valor recebido/alienação (9 digits, 2 decimals)
        - Position 531-538: Custo de aquisição (7 digits, 2 decimals)
        - Position 542-551: Ganho de capital (9 digits, 2 decimals)
        - Position 617-625: Imposto devido (8 digits, 2 decimals)

        Note: Field widths vary. Positions verified against real file with known values.
        """
        alienacoes = []

        for line in self.lines:
            if line.startswith("63"):
                try:
                    # Nome do bem/empresa (position 36-96)
                    nome = line[36:96].strip()

                    # Try to find CNPJ (14 consecutive digits after position 150)
                    cnpj = None
                    for i in range(150, min(220, len(line) - 14)):
                        potential_cnpj = line[i:i+14]
                        if potential_cnpj.isdigit() and potential_cnpj != "0" * 14:
                            cnpj = potential_cnpj
                            break

                    # Tipo de operação (look for "ALIENAC" keyword area)
                    tipo_operacao = ""
                    if "ALIENAC" in line:
                        idx = line.find("ALIENAC")
                        tipo_operacao = line[idx:idx+70].strip()

                    # Tipo de bem (QUOTAS, ACOES, etc.)
                    tipo_bem = ""
                    if "QUOTAS" in line.upper():
                        tipo_bem = "QUOTAS"
                    elif "ACOES" in line.upper() or "AÇÕES" in line.upper():
                        tipo_bem = "AÇÕES"

                    # Data da alienação (look for DDMMYYYY pattern after position 380)
                    data_alienacao = None
                    for i in range(380, min(450, len(line) - 8)):
                        potential_date = line[i:i+8]
                        if potential_date.isdigit() and potential_date != "0" * 8:
                            parsed = _parse_date(potential_date)
                            if parsed and parsed.year >= 2020:
                                data_alienacao = parsed
                                break

                    # Extract financial values from verified positions
                    valor_alienacao = Decimal("0")
                    custo_aquisicao = Decimal("0")
                    ganho_capital = Decimal("0")
                    imposto_devido = Decimal("0")

                    if len(line) >= 555:
                        # Valor recebido/alienação: position 449-458 (9 digits)
                        valor_alienacao = _parse_decimal(line[449:458])

                        # Custo de aquisição: position 531-538 (7 digits)
                        custo_aquisicao = _parse_decimal(line[531:538])

                        # Ganho de capital: position 542-551 (9 digits)
                        ganho_capital = _parse_decimal(line[542:551])

                    if len(line) >= 630:
                        # Imposto devido: position 617-625 (8 digits)
                        imposto_devido = _parse_decimal(line[617:625])

                    if nome:
                        alienacoes.append(Alienacao(
                            nome_bem=nome,
                            cnpj=cnpj,
                            tipo_operacao=tipo_operacao,
                            tipo_bem=tipo_bem,
                            data_alienacao=data_alienacao,
                            valor_alienacao=valor_alienacao,
                            custo_aquisicao=custo_aquisicao,
                            ganho_capital=ganho_capital,
                            imposto_devido=imposto_devido,
                        ))

                except (IndexError, ValueError):
                    continue

        return alienacoes


def parse_dec_file(file_path: Path) -> Declaration:
    """Parse a .DEC file and return a Declaration object."""
    parser = DECParser(file_path)
    return parser.parse()
