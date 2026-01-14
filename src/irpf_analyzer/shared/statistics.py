"""Statistical functions for anomaly detection in IRPF declarations.

This module provides statistical tools for detecting suspicious patterns:
- Benford's Law analysis for detecting fabricated numbers
- Outlier detection using IQR method
- Round value detection
"""

from collections import Counter
from decimal import Decimal


# Expected distribution according to Benford's Law (first digit)
# Natural datasets follow this distribution - deviations may indicate fabrication
BENFORD_EXPECTED = {
    1: Decimal("0.301"),  # 30.1%
    2: Decimal("0.176"),  # 17.6%
    3: Decimal("0.125"),  # 12.5%
    4: Decimal("0.097"),  # 9.7%
    5: Decimal("0.079"),  # 7.9%
    6: Decimal("0.067"),  # 6.7%
    7: Decimal("0.058"),  # 5.8%
    8: Decimal("0.051"),  # 5.1%
    9: Decimal("0.046"),  # 4.6%
}


def extrair_primeiro_digito(valor: Decimal) -> int | None:
    """Extract the first significant digit from a value.

    Ignores leading zeros and negative signs.

    Args:
        valor: Decimal value to analyze

    Returns:
        First significant digit (1-9) or None if value is zero/invalid
    """
    if not valor or valor == 0:
        return None

    # Remove decimal point first, then strip leading zeros
    valor_str = str(abs(valor)).replace(".", "").lstrip("0")
    if not valor_str:
        return None

    return int(valor_str[0])


def calcular_distribuicao_benford(valores: list[Decimal]) -> dict[int, Decimal]:
    """Calculate the distribution of first digits in a list of values.

    Args:
        valores: List of Decimal values to analyze

    Returns:
        Dict mapping digit (1-9) to observed frequency (0-1)
    """
    primeiros_digitos = [
        extrair_primeiro_digito(v)
        for v in valores
        if extrair_primeiro_digito(v) is not None
    ]

    if not primeiros_digitos:
        return {}

    contagem = Counter(primeiros_digitos)
    total = len(primeiros_digitos)

    return {
        digito: Decimal(str(contagem.get(digito, 0) / total))
        for digito in range(1, 10)
    }


def calcular_chi_quadrado_benford(valores: list[Decimal]) -> tuple[Decimal, bool]:
    """Calculate chi-squared statistic comparing observed distribution to Benford's Law.

    The chi-squared test measures how much the observed first-digit distribution
    deviates from Benford's expected distribution.

    Args:
        valores: List of Decimal values to analyze

    Returns:
        (chi_squared, is_anomalous)
        is_anomalous=True if chi_squared > 15.51 (critical value for 8 df, α=0.05)
    """
    observado = calcular_distribuicao_benford(valores)

    if not observado:
        return Decimal("0"), False  # No data

    # Check if we have representation of all 9 digits (with non-zero frequencies)
    digits_with_data = sum(1 for d in range(1, 10) if observado.get(d, Decimal("0")) > 0)
    if digits_with_data < 9:
        return Decimal("0"), False  # Insufficient data - need all digits represented

    n = len([v for v in valores if extrair_primeiro_digito(v) is not None])

    chi2 = Decimal("0")
    for digito in range(1, 10):
        esperado = BENFORD_EXPECTED[digito]
        obs = observado.get(digito, Decimal("0"))

        # Chi² = Σ (O - E)² / E
        if esperado > 0:
            diff = obs - esperado
            chi2 += (diff ** 2) / esperado

    # Multiply by n to get absolute chi²
    chi2_absoluto = chi2 * n

    # Critical value for 8 degrees of freedom, α=0.05: 15.51
    VALOR_CRITICO = Decimal("15.51")

    return chi2_absoluto, chi2_absoluto > VALOR_CRITICO


def detectar_outliers_iqr(
    valores: list[Decimal],
    multiplicador: Decimal = Decimal("1.5"),
) -> list[tuple[Decimal, str]]:
    """Detect outliers using the IQR (Interquartile Range) method.

    A value is an outlier if:
    - value < Q1 - multiplier * IQR (lower outlier)
    - value > Q3 + multiplier * IQR (upper outlier)

    Args:
        valores: List of Decimal values to analyze
        multiplicador: IQR multiplier (1.5 for standard, 2.0 for lenient)

    Returns:
        List of (value, type) tuples where type is "inferior" or "superior"
    """
    if len(valores) < 4:
        return []  # Need at least 4 values for IQR

    valores_ordenados = sorted(valores)
    n = len(valores_ordenados)

    # Calculate quartiles
    q1_idx = n // 4
    q3_idx = (3 * n) // 4

    q1 = valores_ordenados[q1_idx]
    q3 = valores_ordenados[q3_idx]
    iqr = q3 - q1

    limite_inferior = q1 - multiplicador * iqr
    limite_superior = q3 + multiplicador * iqr

    outliers = []
    for v in valores:
        if v < limite_inferior:
            outliers.append((v, "inferior"))
        elif v > limite_superior:
            outliers.append((v, "superior"))

    return outliers


def detectar_valores_redondos(
    valores: list[Decimal],
    tolerancia: int = 100,
    minimo: Decimal = Decimal("500"),
) -> list[Decimal]:
    """Detect suspiciously round values.

    Values are considered "round" if they're exact multiples of the tolerance.
    Examples: R$ 1,000.00 / R$ 5,000.00 / R$ 10,000.00

    Round values in deductions may indicate estimated or fabricated amounts.

    Args:
        valores: List of Decimal values to analyze
        tolerancia: Tolerance for rounding (default 100)
        minimo: Minimum value to consider (default 500)

    Returns:
        List of round values found
    """
    redondos = []
    for v in valores:
        if v > 0 and v % tolerancia == 0 and v >= minimo:
            redondos.append(v)

    return redondos


def calcular_estatisticas_basicas(valores: list[Decimal]) -> dict[str, Decimal]:
    """Calculate basic statistics for a list of values.

    Args:
        valores: List of Decimal values

    Returns:
        Dict with media, mediana, min, max, soma
    """
    if not valores:
        return {
            "media": Decimal("0"),
            "mediana": Decimal("0"),
            "min": Decimal("0"),
            "max": Decimal("0"),
            "soma": Decimal("0"),
        }

    valores_ordenados = sorted(valores)
    n = len(valores_ordenados)

    soma = sum(valores)
    media = soma / n

    if n % 2 == 0:
        mediana = (valores_ordenados[n // 2 - 1] + valores_ordenados[n // 2]) / 2
    else:
        mediana = valores_ordenados[n // 2]

    return {
        "media": media,
        "mediana": mediana,
        "min": valores_ordenados[0],
        "max": valores_ordenados[-1],
        "soma": soma,
    }
