"""Tax constants and limits for IRPF optimization analysis.

Values are based on Brazilian Federal Revenue (Receita Federal) rules.

For IRPF 2026 (ano-calendario 2025):
- Law 15.270/2025: New exemption for income up to R$ 5,000/month
- Progressive reduction for income R$ 5,000 to R$ 7,350/month

Sources:
- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/2025
- https://agenciabrasil.ebc.com.br/economia/noticia/2025-04/ir-2025-saiba-como-incluir-dependentes-e-deduzir-despesas
- https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2025/dezembro/receita-federal-orienta-fontes-pagadoras-e-contribuintes-a-calcular-a-reducao-do-imposto-de-renda-a-partir-de-1o-de-janeiro-de-2026
"""

from decimal import Decimal

# === Deduction Limits (IRPF 2025 - ano-calendario 2024) ===

# Simplified declaration: 20% discount capped at this value
LIMITE_SIMPLIFICADA = Decimal("16754.34")

# Education expenses limit per person per year
LIMITE_EDUCACAO_PESSOA = Decimal("3561.50")

# Dependent deduction (fixed amount per dependent)
DEDUCAO_DEPENDENTE = Decimal("2275.08")

# PGBL (private pension) limit: 12% of gross taxable income
LIMITE_PGBL_PERCENTUAL = Decimal("0.12")

# Incentive donations limit: 6% of tax owed (global maximum)
LIMITE_DOACOES_PERCENTUAL = Decimal("0.06")

# === Detailed Incentive Donation Limits (% of tax owed) ===
# FIA (Fundo da Infância e Adolescência) and Fundo do Idoso share 6% limit
LIMITE_DOACAO_FIA = Decimal("0.03")  # 3% - Fundo da Infância e Adolescência
LIMITE_DOACAO_IDOSO = Decimal("0.03")  # 3% - Fundo do Idoso
LIMITE_DOACAO_CULTURA = Decimal("0.06")  # 6% - Lei de Incentivo à Cultura (Rouanet)
LIMITE_DOACAO_AUDIOVISUAL = Decimal("0.06")  # 6% - Lei do Audiovisual
LIMITE_DOACAO_ESPORTE = Decimal("0.06")  # 6% - Lei de Incentivo ao Esporte
LIMITE_DOACAO_PRONON = Decimal("0.01")  # 1% - Programa Nacional de Apoio à Oncologia
LIMITE_DOACAO_PRONAS = Decimal("0.01")  # 1% - Programa de Apoio à Pessoa com Deficiência
LIMITE_DOACAO_GLOBAL = Decimal("0.06")  # 6% maximum combined

# === Capital Gains Exemptions ===
# Exemption for sale of single property up to this value
LIMITE_ISENCAO_UNICO_IMOVEL = Decimal("440000")  # R$ 440k
# Days to reinvest proceeds for capital gains exemption (Lei 11.196/2005)
PRAZO_REINVESTIMENTO_IMOVEL = 180  # days
# Years between exemption uses
PRAZO_ENTRE_ISENCOES = 5  # years

# === Vehicle Depreciation Rates ===
# Expected remaining value by vehicle age
DEPRECIACAO_VEICULO = {
    1: Decimal("0.85"),   # 1 year old = 85% of new value
    2: Decimal("0.75"),   # 2 years = 75%
    3: Decimal("0.65"),   # 3 years = 65%
    5: Decimal("0.50"),   # 5 years = 50%
    7: Decimal("0.35"),   # 7 years = 35%
    10: Decimal("0.25"),  # 10 years = 25%
    15: Decimal("0.15"),  # 15 years = 15%
}

# === FUNPRESP (Federal Servants) ===
# Additional deduction limit for federal public servants
LIMITE_FUNPRESP_ADICIONAL = Decimal("0.085")  # 8.5% additional to PGBL

# === Cross-Validation Thresholds ===
# e-Financeira reporting threshold (bank balance > this is reported)
LIMITE_EFINANCEIRA = Decimal("5000")  # R$ 5k
# DCBE reporting threshold (foreign assets > USD 1M)
LIMITE_DCBE_USD = Decimal("1000000")  # USD 1M

# === Detection Thresholds ===
# Medical expenses with individual (PF) above this value trigger alert
LIMITE_DESPESA_MEDICA_PF = Decimal("5000")  # R$ 5k per provider
# Rental yield below this percentage is suspicious (annual)
YIELD_ALUGUEL_MINIMO = Decimal("0.02")  # 2%
# Rental yield above this percentage is suspicious (annual)
YIELD_ALUGUEL_MAXIMO = Decimal("0.10")  # 10%

# === Dependent Age Limits ===
IDADE_LIMITE_FILHO = 21  # years (basic limit)
IDADE_LIMITE_UNIVERSITARIO = 24  # years (if in university)

# === Tax Brackets (Monthly, IRPF 2025) ===
# Format: (base_mensal, aliquota, deducao_parcela)

FAIXAS_IR_MENSAL = [
    (Decimal("0"), Decimal("0"), Decimal("0")),           # Isento
    (Decimal("2259.21"), Decimal("0.075"), Decimal("169.44")),   # 7.5%
    (Decimal("2826.66"), Decimal("0.15"), Decimal("381.44")),    # 15%
    (Decimal("3751.06"), Decimal("0.225"), Decimal("662.77")),   # 22.5%
    (Decimal("4664.68"), Decimal("0.275"), Decimal("896.00")),   # 27.5%
]

# Annual tax brackets (12x monthly)
FAIXAS_IR_ANUAL = [
    (base * 12, aliq, ded * 12)
    for base, aliq, ded in FAIXAS_IR_MENSAL
]

# Maximum marginal rate (for potential savings calculations)
ALIQUOTA_MAXIMA = Decimal("0.275")

# === IRPF 2026 Reform (Lei 15.270/2025) ===
# New exemption and reduction rules effective January 1, 2026

# Monthly exemption limit (full exemption up to this amount)
ISENCAO_MENSAL_2026 = Decimal("5000")
# Annual exemption limit
ISENCAO_ANUAL_2026 = Decimal("60000")

# Reduction zone upper limit (gradual reduction between exemption and this)
REDUCAO_MENSAL_LIMITE_2026 = Decimal("7350")
REDUCAO_ANUAL_LIMITE_2026 = Decimal("88200")

# Maximum monthly reduction value (R$ 312.89)
REDUCAO_MAXIMA_MENSAL_2026 = Decimal("312.89")

# High income minimum tax (IRPFM) thresholds
# Above R$ 600k/year: progressive minimum tax up to 10%
LIMITE_IRPFM = Decimal("600000")
# Above R$ 1.2M/year: minimum effective rate of 10%
LIMITE_IRPFM_MAXIMO = Decimal("1200000")
ALIQUOTA_IRPFM_MAXIMA = Decimal("0.10")

# === Minimum thresholds for suggestions ===

# Minimum income for PGBL suggestion (below this, likely uses simplified)
RENDA_MINIMA_PGBL = Decimal("50000")

# Minimum potential savings to show a suggestion
ECONOMIA_MINIMA_SUGESTAO = Decimal("100")

# Minimum PGBL space to suggest (avoid suggesting tiny amounts)
ESPACO_MINIMO_PGBL = Decimal("1000")

# === Declaration Obligation Thresholds (IRPF 2026) ===

# Minimum taxable income requiring declaration (ano-base 2025)
OBRIGATORIEDADE_RENDIMENTOS_TRIBUTAVEIS = Decimal("33888")

# Minimum exempt income requiring declaration
OBRIGATORIEDADE_RENDIMENTOS_ISENTOS = Decimal("200000")

# Minimum patrimony requiring declaration
OBRIGATORIEDADE_PATRIMONIO = Decimal("800000")

# Minimum capital gains requiring declaration
OBRIGATORIEDADE_GANHO_CAPITAL = Decimal("0")  # Any capital gain

# Minimum rural revenue requiring declaration
OBRIGATORIEDADE_RECEITA_RURAL = Decimal("169440")

# === Sanity check limits ===

# Maximum reasonable annual income (to detect parsing errors)
RENDA_MAXIMA_VALIDA = Decimal("10000000")

# Minimum income to consider (to skip irrelevant declarations)
RENDA_MINIMA_VALIDA = Decimal("0")

# === INSS (Previdência Social) Limits 2024 ===

# INSS contribution rates by bracket (2024)
# Progressive rates: 7.5%, 9%, 12%, 14%
INSS_FAIXA_1 = Decimal("1412.00")  # Up to this: 7.5%
INSS_FAIXA_2 = Decimal("2666.68")  # Up to this: 9%
INSS_FAIXA_3 = Decimal("4000.03")  # Up to this: 12%
INSS_FAIXA_4 = Decimal("7786.02")  # Up to this (ceiling): 14%

INSS_ALIQUOTA_1 = Decimal("0.075")
INSS_ALIQUOTA_2 = Decimal("0.09")
INSS_ALIQUOTA_3 = Decimal("0.12")
INSS_ALIQUOTA_4 = Decimal("0.14")

# Maximum annual INSS contribution (ceiling * 12 months * max rate)
TETO_INSS_MENSAL = INSS_FAIXA_4
TETO_INSS_ANUAL = TETO_INSS_MENSAL * 12

# === Alimony (Pensão Alimentícia) Limits ===

# Typical alimony as percentage of income (judicial guidelines)
PENSAO_MINIMA_PERCENTUAL = Decimal("0.10")  # 10% minimum
PENSAO_MAXIMA_PERCENTUAL = Decimal("0.40")  # 40% maximum typical
PENSAO_LIMITE_ABSOLUTO = Decimal("0.50")  # 50% absolute maximum

# === Statistical Detection Thresholds ===

# Z-score threshold for extreme outliers
ZSCORE_LIMITE_OUTLIER = Decimal("3.0")  # 99.7% of data

# Coefficient of variation threshold for suspicious uniformity
CV_MINIMO_ESPERADO = Decimal("10")  # Below this = too uniform

# Gini coefficient threshold for concentration
GINI_CONCENTRACAO_ALTA = Decimal("0.85")  # Above this = highly concentrated

# Benford's Law chi-squared critical value (df=8, α=0.05)
BENFORD_CHI2_CRITICO = Decimal("15.51")

# === Income Analysis Thresholds ===

# IRRF ratio tolerances by income bracket (min_income, max_ratio)
IRRF_TOLERANCIA_SUPERIOR = Decimal("0.05")  # 5% above expected
IRRF_TOLERANCIA_INFERIOR = Decimal("0.02")  # 2% below expected

# 13th salary expected ratio (1/12 = 8.33%)
DECIMO_TERCEIRO_RATIO_ESPERADO = Decimal("0.0833")
DECIMO_TERCEIRO_TOLERANCIA = Decimal("0.20")  # 20% tolerance

# Exempt income ratio threshold (above this = needs documentation)
RENDIMENTOS_ISENTOS_ALERTA = Decimal("0.60")  # 60%

# === Livro-Caixa (Cash Book) Limits ===

# Maximum livro-caixa as percentage of autonomous income
LIVRO_CAIXA_MAXIMO_RATIO = Decimal("0.80")  # 80% max


def calcular_imposto_anual(renda_tributavel: Decimal) -> Decimal:
    """Calculate annual tax for a given taxable income.

    Uses progressive tax brackets.

    Args:
        renda_tributavel: Annual taxable income

    Returns:
        Annual tax amount
    """
    imposto = Decimal("0")
    renda_restante = renda_tributavel

    # Find applicable bracket
    for i in range(len(FAIXAS_IR_ANUAL) - 1, -1, -1):
        base, aliquota, deducao = FAIXAS_IR_ANUAL[i]
        if renda_tributavel > base:
            imposto = renda_tributavel * aliquota - deducao
            break

    return max(imposto, Decimal("0"))


def obter_aliquota_marginal(renda_tributavel: Decimal) -> Decimal:
    """Get the marginal tax rate for a given income.

    Args:
        renda_tributavel: Annual taxable income

    Returns:
        Marginal tax rate (0 to 0.275)
    """
    for i in range(len(FAIXAS_IR_ANUAL) - 1, -1, -1):
        base, aliquota, _ = FAIXAS_IR_ANUAL[i]
        if renda_tributavel > base:
            return aliquota

    return Decimal("0")
