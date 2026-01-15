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


def calcular_desvio_padrao(valores: list[Decimal]) -> Decimal:
    """Calculate standard deviation for a list of values.

    Args:
        valores: List of Decimal values

    Returns:
        Standard deviation (0 if insufficient data)
    """
    if len(valores) < 2:
        return Decimal("0")

    n = len(valores)
    media = sum(valores) / n

    # Calculate variance
    soma_quadrados = sum((v - media) ** 2 for v in valores)
    variancia = soma_quadrados / (n - 1)  # Sample variance (n-1)

    # Square root approximation for Decimal
    # Using Newton-Raphson method
    if variancia == 0:
        return Decimal("0")

    # Initial guess
    x = variancia
    for _ in range(50):  # Iterate until convergence
        x_new = (x + variancia / x) / 2
        if abs(x_new - x) < Decimal("0.0000001"):
            break
        x = x_new

    return x


def calcular_zscore(valor: Decimal, media: Decimal, desvio_padrao: Decimal) -> Decimal:
    """Calculate z-score for a value.

    Z-score measures how many standard deviations a value is from the mean.
    |z| > 2 is unusual, |z| > 3 is very unusual.

    Args:
        valor: Value to calculate z-score for
        media: Mean of the distribution
        desvio_padrao: Standard deviation

    Returns:
        Z-score (0 if desvio_padrao is 0)
    """
    if desvio_padrao == 0:
        return Decimal("0")

    return (valor - media) / desvio_padrao


def detectar_outliers_zscore(
    valores: list[Decimal],
    limite: Decimal = Decimal("3.0"),
) -> list[tuple[Decimal, Decimal]]:
    """Detect outliers using z-score method.

    Z-score measures how many standard deviations a value is from the mean.
    Values with |z| > limite are considered outliers.

    More sensitive than IQR for normally distributed data.

    Args:
        valores: List of Decimal values to analyze
        limite: Z-score threshold (default 3.0 = 99.7% of data)

    Returns:
        List of (value, z_score) tuples for outliers
    """
    if len(valores) < 3:
        return []  # Need at least 3 values

    media = sum(valores) / len(valores)
    desvio = calcular_desvio_padrao(valores)

    if desvio == 0:
        return []

    outliers = []
    for v in valores:
        z = calcular_zscore(v, media, desvio)
        if abs(z) > limite:
            outliers.append((v, z))

    return outliers


def calcular_coeficiente_variacao(valores: list[Decimal]) -> Decimal:
    """Calculate coefficient of variation (CV).

    CV = (std deviation / mean) * 100
    Measures relative variability:
    - CV < 15%: Low variability (consistent)
    - CV 15-30%: Moderate variability
    - CV > 30%: High variability (inconsistent)

    Useful for comparing variability between datasets with different means.

    Args:
        valores: List of Decimal values

    Returns:
        Coefficient of variation as percentage (0 if mean is 0)
    """
    if len(valores) < 2:
        return Decimal("0")

    media = sum(valores) / len(valores)
    if media == 0:
        return Decimal("0")

    desvio = calcular_desvio_padrao(valores)
    return (desvio / abs(media)) * 100


def calcular_indice_gini(valores: list[Decimal]) -> Decimal:
    """Calculate Gini coefficient for concentration analysis.

    Gini coefficient measures inequality/concentration:
    - 0 = Perfect equality (all values equal)
    - 1 = Perfect inequality (one value has everything)

    Useful for detecting:
    - Income concentration (few sources dominate)
    - Expense concentration (one provider dominates)

    Args:
        valores: List of Decimal values (must be non-negative)

    Returns:
        Gini coefficient (0-1)
    """
    if not valores or len(valores) < 2:
        return Decimal("0")

    # Filter negative values and sort
    valores_positivos = sorted([v for v in valores if v >= 0])
    if not valores_positivos:
        return Decimal("0")

    n = len(valores_positivos)
    soma_total = sum(valores_positivos)

    if soma_total == 0:
        return Decimal("0")

    # Gini formula: G = (2 * sum(i * x_i) - (n + 1) * sum(x_i)) / (n * sum(x_i))
    soma_ponderada = sum(
        Decimal(str(i + 1)) * v for i, v in enumerate(valores_positivos)
    )

    gini = (2 * soma_ponderada - (n + 1) * soma_total) / (n * soma_total)
    return max(Decimal("0"), min(Decimal("1"), gini))


def calcular_entropia(valores: list[Decimal]) -> Decimal:
    """Calculate Shannon entropy for distribution analysis.

    Entropy measures how "spread out" a distribution is:
    - Low entropy: Concentrated in few values
    - High entropy: Evenly distributed

    Normalized to 0-1 range (1 = maximum entropy).

    Args:
        valores: List of Decimal values (must be non-negative)

    Returns:
        Normalized entropy (0-1)
    """
    if not valores or len(valores) < 2:
        return Decimal("0")

    # Filter zero/negative values
    valores_positivos = [v for v in valores if v > 0]
    if not valores_positivos:
        return Decimal("0")

    soma = sum(valores_positivos)
    if soma == 0:
        return Decimal("0")

    # Calculate probabilities
    probabilidades = [v / soma for v in valores_positivos]

    # Shannon entropy: H = -sum(p * log2(p))
    # Using natural log and converting to log2
    import math

    entropia = Decimal("0")
    for p in probabilidades:
        if p > 0:
            # log2(p) = ln(p) / ln(2)
            log_p = Decimal(str(math.log(float(p))))
            entropia -= p * log_p

    # Convert to log2 and normalize
    ln2 = Decimal(str(math.log(2)))
    entropia_bits = entropia / ln2

    # Maximum entropy for n items is log2(n)
    max_entropia = Decimal(str(math.log2(len(valores_positivos))))
    if max_entropia == 0:
        return Decimal("0")

    return min(Decimal("1"), entropia_bits / max_entropia)


def detectar_valores_duplicados(
    valores: list[Decimal],
    tolerancia: Decimal = Decimal("0.01"),
) -> list[tuple[Decimal, int]]:
    """Detect duplicate or near-duplicate values.

    Useful for detecting:
    - Copy-paste errors
    - Fabricated data with repeated values
    - Systematic fraud patterns

    Args:
        valores: List of Decimal values
        tolerancia: Tolerance for considering values "equal" (default 1%)

    Returns:
        List of (value, count) tuples for values appearing 2+ times
    """
    if len(valores) < 2:
        return []

    # Group values by similarity
    grupos: dict[Decimal, int] = {}

    for v in valores:
        if v <= 0:
            continue

        # Check if similar value exists
        encontrou = False
        for base in list(grupos.keys()):
            if abs(v - base) / base <= tolerancia:
                grupos[base] += 1
                encontrou = True
                break

        if not encontrou:
            grupos[v] = 1

    # Return only duplicates (count >= 2)
    return [(v, c) for v, c in grupos.items() if c >= 2]


def calcular_taxa_variacao(valor_anterior: Decimal, valor_atual: Decimal) -> Decimal:
    """Calculate rate of variation between two values.

    Args:
        valor_anterior: Previous value
        valor_atual: Current value

    Returns:
        Rate of variation as percentage (-100 to +inf)
    """
    if valor_anterior == 0:
        if valor_atual == 0:
            return Decimal("0")
        return Decimal("100")  # From 0 to something = 100%

    return ((valor_atual - valor_anterior) / abs(valor_anterior)) * 100


def calcular_percentil(valores: list[Decimal], percentil: int) -> Decimal:
    """Calculate a specific percentile of the values.

    Args:
        valores: List of Decimal values
        percentil: Percentile to calculate (0-100)

    Returns:
        Value at the specified percentile
    """
    if not valores:
        return Decimal("0")

    percentil = max(0, min(100, percentil))
    valores_ordenados = sorted(valores)
    n = len(valores_ordenados)

    # Calculate index
    indice = (percentil / 100) * (n - 1)
    indice_inferior = int(indice)
    indice_superior = min(indice_inferior + 1, n - 1)

    # Linear interpolation
    fracao = Decimal(str(indice - indice_inferior))
    return valores_ordenados[indice_inferior] + fracao * (
        valores_ordenados[indice_superior] - valores_ordenados[indice_inferior]
    )


def detectar_sequencia_linear(
    valores: list[Decimal],
    tolerancia: Decimal = Decimal("0.05"),
) -> bool:
    """Detect if values follow a linear pattern (suspicious for fabricated data).

    Real financial data rarely shows perfect linear progression.
    Values growing by exactly the same amount each time may indicate fabrication.

    Args:
        valores: List of Decimal values in order
        tolerancia: Tolerance for variation (default 5%)

    Returns:
        True if values appear to follow linear pattern
    """
    if len(valores) < 4:
        return False

    # Calculate differences between consecutive values
    diferencas = [valores[i + 1] - valores[i] for i in range(len(valores) - 1)]

    if not diferencas:
        return False

    media_diff = sum(diferencas) / len(diferencas)
    if media_diff == 0:
        return False

    # Check if all differences are within tolerance of the mean
    for diff in diferencas:
        if abs(diff - media_diff) / abs(media_diff) > tolerancia:
            return False

    return True


def calcular_correlacao_pearson(
    x: list[Decimal],
    y: list[Decimal],
) -> Decimal:
    """Calculate Pearson correlation coefficient between two series.

    Measures linear relationship:
    - +1: Perfect positive correlation
    - 0: No linear correlation
    - -1: Perfect negative correlation

    Args:
        x: First list of values
        y: Second list of values (must be same length)

    Returns:
        Correlation coefficient (-1 to +1)
    """
    if len(x) != len(y) or len(x) < 3:
        return Decimal("0")

    n = len(x)
    media_x = sum(x) / n
    media_y = sum(y) / n

    # Calculate covariance and standard deviations
    soma_xy = sum((x[i] - media_x) * (y[i] - media_y) for i in range(n))
    soma_x2 = sum((xi - media_x) ** 2 for xi in x)
    soma_y2 = sum((yi - media_y) ** 2 for yi in y)

    if soma_x2 == 0 or soma_y2 == 0:
        return Decimal("0")

    # Correlation = cov(X,Y) / (std(X) * std(Y))
    import math

    denominador = Decimal(str(math.sqrt(float(soma_x2) * float(soma_y2))))
    if denominador == 0:
        return Decimal("0")

    correlacao = soma_xy / denominador
    return max(Decimal("-1"), min(Decimal("1"), correlacao))
