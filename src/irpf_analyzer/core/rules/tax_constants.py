"""Tax constants and limits for IRPF optimization analysis.

Values are based on Brazilian Federal Revenue (Receita Federal) rules for 2025.
Sources:
- https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/2025
- https://agenciabrasil.ebc.com.br/economia/noticia/2025-04/ir-2025-saiba-como-incluir-dependentes-e-deduzir-despesas
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

# Incentive donations limit: 6% of tax owed
LIMITE_DOACOES_PERCENTUAL = Decimal("0.06")

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

# === Minimum thresholds for suggestions ===

# Minimum income for PGBL suggestion (below this, likely uses simplified)
RENDA_MINIMA_PGBL = Decimal("50000")

# Minimum potential savings to show a suggestion
ECONOMIA_MINIMA_SUGESTAO = Decimal("100")

# Minimum PGBL space to suggest (avoid suggesting tiny amounts)
ESPACO_MINIMO_PGBL = Decimal("1000")

# === Sanity check limits ===

# Maximum reasonable annual income (to detect parsing errors)
RENDA_MAXIMA_VALIDA = Decimal("10000000")

# Minimum income to consider (to skip irrelevant declarations)
RENDA_MINIMA_VALIDA = Decimal("0")


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
