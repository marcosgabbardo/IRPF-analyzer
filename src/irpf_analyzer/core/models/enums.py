"""Enumerations for IRPF domain models."""

from enum import Enum


class TipoDeclaracao(str, Enum):
    """Declaration type."""

    COMPLETA = "completa"
    SIMPLIFICADA = "simplificada"


class TipoRendimento(str, Enum):
    """Income types."""

    TRABALHO_ASSALARIADO = "trabalho_assalariado"
    TRABALHO_NAO_ASSALARIADO = "trabalho_nao_assalariado"
    ALUGUEIS = "alugueis"
    RENDIMENTOS_EXTERIOR = "rendimentos_exterior"
    LUCROS_DIVIDENDOS = "lucros_dividendos"
    GANHO_CAPITAL = "ganho_capital"
    RENDIMENTOS_ISENTOS = "rendimentos_isentos"
    TRIBUTACAO_EXCLUSIVA = "tributacao_exclusiva"
    RENDIMENTOS_PJ = "rendimentos_pj"
    RENDIMENTOS_RECEBIDOS_ACUMULADAMENTE = "rra"
    OUTROS = "outros"


class TipoDeducao(str, Enum):
    """Deduction types."""

    PREVIDENCIA_OFICIAL = "previdencia_oficial"
    PREVIDENCIA_PRIVADA = "previdencia_privada"
    DEPENDENTES = "dependentes"
    DESPESAS_MEDICAS = "despesas_medicas"
    DESPESAS_EDUCACAO = "despesas_educacao"
    PENSAO_ALIMENTICIA = "pensao_alimenticia"
    LIVRO_CAIXA = "livro_caixa"
    FUNPRESP = "funpresp"
    OUTROS = "outros"


class GrupoBem(str, Enum):
    """Asset groups (Grupos de bens e direitos)."""

    IMOVEIS = "01"
    VEICULOS = "02"
    PARTICIPACOES_SOCIETARIAS = "03"
    APLICACOES_FINANCEIRAS = "04"
    POUPANCA = "05"
    DEPOSITOS_VISTA = "06"
    FUNDOS = "07"
    CRIPTOATIVOS = "08"
    OUTROS_BENS = "99"


class TipoDependente(str, Enum):
    """Dependent types."""

    CONJUGE = "conjuge"
    COMPANHEIRO = "companheiro"
    FILHO_ENTEADO_ATE_21 = "filho_enteado_ate_21"
    FILHO_ENTEADO_UNIVERSITARIO = "filho_enteado_universitario"
    FILHO_ENTEADO_INCAPAZ = "filho_enteado_incapaz"
    IRMAO_NETO_BISNETO = "irmao_neto_bisneto"
    PAIS_AVOS_BISAVOS = "pais_avos_bisavos"
    MENOR_POBRE = "menor_pobre"
    INCAPAZ_TUTELADO = "incapaz_tutelado"


class Severity(str, Enum):
    """Severity levels for findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    """Risk levels for malha fina score."""

    LOW = "low"  # 0-25
    MEDIUM = "medium"  # 26-50
    HIGH = "high"  # 51-75
    CRITICAL = "critical"  # 76-100
