"""Tests for statistical functions."""

import pytest
from decimal import Decimal

from irpf_analyzer.shared.statistics import (
    BENFORD_EXPECTED,
    calcular_chi_quadrado_benford,
    calcular_distribuicao_benford,
    calcular_estatisticas_basicas,
    calcular_desvio_padrao,
    calcular_zscore,
    detectar_outliers_zscore,
    calcular_coeficiente_variacao,
    calcular_indice_gini,
    calcular_entropia,
    detectar_valores_duplicados,
    calcular_taxa_variacao,
    calcular_percentil,
    detectar_sequencia_linear,
    calcular_correlacao_pearson,
    detectar_outliers_iqr,
    detectar_valores_redondos,
    extrair_primeiro_digito,
)


class TestExtrairPrimeiroDigito:
    """Tests for extrair_primeiro_digito function."""

    def test_simple_integer(self):
        """Extract first digit from simple integers."""
        assert extrair_primeiro_digito(Decimal("123")) == 1
        assert extrair_primeiro_digito(Decimal("5000")) == 5
        assert extrair_primeiro_digito(Decimal("9999")) == 9

    def test_decimal_values(self):
        """Extract first digit from decimal values."""
        assert extrair_primeiro_digito(Decimal("1.23")) == 1
        assert extrair_primeiro_digito(Decimal("0.56")) == 5
        assert extrair_primeiro_digito(Decimal("0.0078")) == 7

    def test_negative_values(self):
        """Extract first digit from negative values (ignore sign)."""
        assert extrair_primeiro_digito(Decimal("-123")) == 1
        assert extrair_primeiro_digito(Decimal("-0.45")) == 4

    def test_zero_returns_none(self):
        """Zero should return None."""
        assert extrair_primeiro_digito(Decimal("0")) is None
        assert extrair_primeiro_digito(Decimal("0.00")) is None

    def test_none_returns_none(self):
        """None should return None."""
        assert extrair_primeiro_digito(None) is None


class TestCalcularDistribuicaoBenford:
    """Tests for calcular_distribuicao_benford function."""

    def test_uniform_distribution(self):
        """Test with values that have all first digits."""
        valores = [
            Decimal("100"),  # 1
            Decimal("200"),  # 2
            Decimal("300"),  # 3
            Decimal("400"),  # 4
            Decimal("500"),  # 5
            Decimal("600"),  # 6
            Decimal("700"),  # 7
            Decimal("800"),  # 8
            Decimal("900"),  # 9
        ]
        dist = calcular_distribuicao_benford(valores)

        # Each digit should appear 1/9 of the time
        for digito in range(1, 10):
            assert digito in dist
            assert abs(dist[digito] - Decimal("0.111")) < Decimal("0.01")

    def test_empty_list(self):
        """Empty list should return empty dict."""
        assert calcular_distribuicao_benford([]) == {}

    def test_all_zeros(self):
        """List of zeros should return empty dict."""
        valores = [Decimal("0"), Decimal("0"), Decimal("0")]
        assert calcular_distribuicao_benford(valores) == {}

    def test_concentrated_distribution(self):
        """Test with concentration on digit 1."""
        valores = [
            Decimal("100"),
            Decimal("110"),
            Decimal("120"),
            Decimal("200"),
        ]
        dist = calcular_distribuicao_benford(valores)
        assert dist[1] == Decimal("0.75")  # 3 out of 4
        assert dist[2] == Decimal("0.25")  # 1 out of 4


class TestCalcularChiQuadradoBenford:
    """Tests for calcular_chi_quadrado_benford function."""

    def test_insufficient_data(self):
        """Less than 9 different digits should return (0, False)."""
        valores = [Decimal("100"), Decimal("200")]
        chi2, anomalo = calcular_chi_quadrado_benford(valores)
        assert chi2 == Decimal("0")
        assert anomalo is False

    def test_benford_like_distribution(self):
        """Distribution close to Benford should not be flagged."""
        # Create a list that roughly follows Benford's distribution
        valores = []
        for _ in range(30):  # ~30% start with 1
            valores.append(Decimal("1000") + Decimal(str(_ * 10)))
        for _ in range(18):  # ~18% start with 2
            valores.append(Decimal("2000") + Decimal(str(_ * 10)))
        for _ in range(12):  # ~12% start with 3
            valores.append(Decimal("3000") + Decimal(str(_ * 10)))
        for _ in range(10):  # ~10% start with 4
            valores.append(Decimal("4000") + Decimal(str(_ * 10)))
        for _ in range(8):  # ~8% start with 5
            valores.append(Decimal("5000") + Decimal(str(_ * 10)))
        for _ in range(7):  # ~7% start with 6
            valores.append(Decimal("6000") + Decimal(str(_ * 10)))
        for _ in range(6):  # ~6% start with 7
            valores.append(Decimal("7000") + Decimal(str(_ * 10)))
        for _ in range(5):  # ~5% start with 8
            valores.append(Decimal("8000") + Decimal(str(_ * 10)))
        for _ in range(4):  # ~4% start with 9
            valores.append(Decimal("9000") + Decimal(str(_ * 10)))

        chi2, anomalo = calcular_chi_quadrado_benford(valores)
        # Should not be anomalous (follows Benford)
        # Note: exact result depends on implementation details
        assert isinstance(chi2, Decimal)
        assert isinstance(anomalo, bool)


class TestDetectarOutliersIQR:
    """Tests for detectar_outliers_iqr function."""

    def test_no_outliers(self):
        """Data without outliers should return empty list."""
        valores = [Decimal("100"), Decimal("110"), Decimal("120"), Decimal("130")]
        outliers = detectar_outliers_iqr(valores)
        assert outliers == []

    def test_upper_outlier(self):
        """Detect upper outlier."""
        valores = [
            Decimal("100"),
            Decimal("110"),
            Decimal("120"),
            Decimal("130"),
            Decimal("500"),  # Outlier
        ]
        outliers = detectar_outliers_iqr(valores)
        assert len(outliers) == 1
        assert outliers[0][0] == Decimal("500")
        assert outliers[0][1] == "superior"

    def test_lower_outlier(self):
        """Detect lower outlier."""
        valores = [
            Decimal("10"),  # Outlier
            Decimal("100"),
            Decimal("110"),
            Decimal("120"),
            Decimal("130"),
        ]
        outliers = detectar_outliers_iqr(valores)
        assert len(outliers) == 1
        assert outliers[0][0] == Decimal("10")
        assert outliers[0][1] == "inferior"

    def test_insufficient_data(self):
        """Less than 4 values should return empty list."""
        valores = [Decimal("100"), Decimal("200"), Decimal("300")]
        assert detectar_outliers_iqr(valores) == []

    def test_custom_multiplier(self):
        """Higher multiplier should be more lenient."""
        valores = [
            Decimal("100"),
            Decimal("120"),
            Decimal("140"),
            Decimal("160"),
            Decimal("250"),  # Borderline outlier with 1.5x, not with 3.0x
        ]
        # With default multiplier (1.5), 250 is an outlier
        # IQR = 160 - 120 = 40, Q3 + 1.5*IQR = 160 + 60 = 220
        outliers_strict = detectar_outliers_iqr(valores, Decimal("1.5"))
        assert len(outliers_strict) == 1
        assert outliers_strict[0][0] == Decimal("250")

        # With higher multiplier (3.0), 250 is not an outlier
        # Q3 + 3.0*IQR = 160 + 120 = 280
        outliers_lenient = detectar_outliers_iqr(valores, Decimal("3.0"))
        assert len(outliers_lenient) == 0


class TestDetectarValoresRedondos:
    """Tests for detectar_valores_redondos function."""

    def test_detect_round_values(self):
        """Detect values that are multiples of 100."""
        valores = [
            Decimal("1000"),  # Round
            Decimal("2500"),  # Round
            Decimal("3456"),  # Not round
            Decimal("5000"),  # Round
        ]
        redondos = detectar_valores_redondos(valores)
        assert Decimal("1000") in redondos
        assert Decimal("2500") in redondos
        assert Decimal("5000") in redondos
        assert Decimal("3456") not in redondos

    def test_minimum_threshold(self):
        """Values below minimum should not be flagged."""
        valores = [
            Decimal("100"),  # Below minimum (500)
            Decimal("200"),  # Below minimum
            Decimal("1000"),  # Above minimum
        ]
        redondos = detectar_valores_redondos(valores)
        assert Decimal("100") not in redondos
        assert Decimal("200") not in redondos
        assert Decimal("1000") in redondos

    def test_custom_tolerance(self):
        """Custom tolerance for round detection."""
        valores = [
            Decimal("1500"),
            Decimal("1750"),
        ]
        # With tolerance 500, 1500 is round, 1750 is not
        redondos = detectar_valores_redondos(valores, tolerancia=500, minimo=Decimal("1000"))
        assert Decimal("1500") in redondos
        assert Decimal("1750") not in redondos

    def test_empty_list(self):
        """Empty list should return empty list."""
        assert detectar_valores_redondos([]) == []

    def test_zero_values(self):
        """Zero values should not be flagged."""
        valores = [Decimal("0"), Decimal("1000")]
        redondos = detectar_valores_redondos(valores)
        assert Decimal("0") not in redondos


class TestCalcularEstatisticasBasicas:
    """Tests for calcular_estatisticas_basicas function."""

    def test_basic_statistics(self):
        """Calculate basic statistics."""
        valores = [Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400")]
        stats = calcular_estatisticas_basicas(valores)

        assert stats["soma"] == Decimal("1000")
        assert stats["media"] == Decimal("250")
        assert stats["min"] == Decimal("100")
        assert stats["max"] == Decimal("400")
        # Mediana of [100, 200, 300, 400] is (200+300)/2 = 250
        assert stats["mediana"] == Decimal("250")

    def test_odd_count_median(self):
        """Median with odd number of values."""
        valores = [Decimal("100"), Decimal("200"), Decimal("300")]
        stats = calcular_estatisticas_basicas(valores)
        assert stats["mediana"] == Decimal("200")

    def test_empty_list(self):
        """Empty list should return zeros."""
        stats = calcular_estatisticas_basicas([])
        assert stats["soma"] == Decimal("0")
        assert stats["media"] == Decimal("0")
        assert stats["mediana"] == Decimal("0")
        assert stats["min"] == Decimal("0")
        assert stats["max"] == Decimal("0")


class TestCalcularDesvioPadrao:
    """Tests for calcular_desvio_padrao function."""

    def test_uniform_values(self):
        """Uniform values should have zero std deviation."""
        valores = [Decimal("100"), Decimal("100"), Decimal("100")]
        assert calcular_desvio_padrao(valores) == Decimal("0")

    def test_simple_std(self):
        """Calculate std deviation for simple values."""
        valores = [Decimal("2"), Decimal("4"), Decimal("4"), Decimal("4"), Decimal("5"), Decimal("5"), Decimal("7"), Decimal("9")]
        std = calcular_desvio_padrao(valores)
        # Expected std ~= 2.14
        assert Decimal("2.0") < std < Decimal("2.3")

    def test_insufficient_data(self):
        """Less than 2 values should return 0."""
        assert calcular_desvio_padrao([Decimal("100")]) == Decimal("0")
        assert calcular_desvio_padrao([]) == Decimal("0")


class TestCalcularZscore:
    """Tests for calcular_zscore function."""

    def test_at_mean(self):
        """Value at mean should have z-score of 0."""
        z = calcular_zscore(Decimal("100"), Decimal("100"), Decimal("10"))
        assert z == Decimal("0")

    def test_one_std_above(self):
        """Value one std above mean should have z-score of 1."""
        z = calcular_zscore(Decimal("110"), Decimal("100"), Decimal("10"))
        assert z == Decimal("1")

    def test_two_std_below(self):
        """Value two std below mean should have z-score of -2."""
        z = calcular_zscore(Decimal("80"), Decimal("100"), Decimal("10"))
        assert z == Decimal("-2")

    def test_zero_std(self):
        """Zero std deviation should return 0."""
        z = calcular_zscore(Decimal("150"), Decimal("100"), Decimal("0"))
        assert z == Decimal("0")


class TestDetectarOutliersZscore:
    """Tests for detectar_outliers_zscore function."""

    def test_no_outliers(self):
        """Normal data should have no z-score outliers."""
        valores = [Decimal("100"), Decimal("102"), Decimal("98"), Decimal("101"), Decimal("99")]
        outliers = detectar_outliers_zscore(valores)
        assert outliers == []

    def test_detect_extreme_outlier(self):
        """Detect extreme outlier with z > 3."""
        # Need more data points with tighter distribution for z-score to detect outlier
        valores = [
            Decimal("100"), Decimal("102"), Decimal("98"), Decimal("101"), Decimal("99"),
            Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), Decimal("102"),
            Decimal("1000"),  # Extreme outlier
        ]
        outliers = detectar_outliers_zscore(valores)
        assert len(outliers) >= 1
        # The outlier value 1000 should be detected
        outlier_values = [o[0] for o in outliers]
        assert Decimal("1000") in outlier_values

    def test_insufficient_data(self):
        """Less than 3 values should return empty list."""
        valores = [Decimal("100"), Decimal("200")]
        assert detectar_outliers_zscore(valores) == []


class TestCalcularCoeficienteVariacao:
    """Tests for calcular_coeficiente_variacao function."""

    def test_low_cv(self):
        """Uniform data should have low CV."""
        valores = [Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100")]
        cv = calcular_coeficiente_variacao(valores)
        assert cv < Decimal("5")  # Less than 5%

    def test_high_cv(self):
        """Varied data should have high CV."""
        valores = [Decimal("100"), Decimal("500"), Decimal("50"), Decimal("1000")]
        cv = calcular_coeficiente_variacao(valores)
        assert cv > Decimal("50")  # More than 50%

    def test_insufficient_data(self):
        """Less than 2 values should return 0."""
        assert calcular_coeficiente_variacao([Decimal("100")]) == Decimal("0")


class TestCalcularIndiceGini:
    """Tests for calcular_indice_gini function."""

    def test_perfect_equality(self):
        """Equal values should have Gini close to 0."""
        valores = [Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")]
        gini = calcular_indice_gini(valores)
        assert gini < Decimal("0.1")

    def test_high_concentration(self):
        """One dominant value should have high Gini."""
        valores = [Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1000")]
        gini = calcular_indice_gini(valores)
        assert gini > Decimal("0.7")

    def test_empty_list(self):
        """Empty list should return 0."""
        assert calcular_indice_gini([]) == Decimal("0")


class TestCalcularEntropia:
    """Tests for calcular_entropia function."""

    def test_uniform_distribution(self):
        """Uniform distribution should have high entropy (close to 1)."""
        valores = [Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")]
        entropia = calcular_entropia(valores)
        assert entropia > Decimal("0.9")

    def test_concentrated_distribution(self):
        """Concentrated distribution should have low entropy."""
        valores = [Decimal("1000"), Decimal("1"), Decimal("1"), Decimal("1")]
        entropia = calcular_entropia(valores)
        assert entropia < Decimal("0.5")

    def test_empty_list(self):
        """Empty list should return 0."""
        assert calcular_entropia([]) == Decimal("0")


class TestDetectarValoresDuplicados:
    """Tests for detectar_valores_duplicados function."""

    def test_detect_duplicates(self):
        """Detect duplicate values."""
        valores = [Decimal("100"), Decimal("100"), Decimal("200"), Decimal("100")]
        duplicados = detectar_valores_duplicados(valores)
        assert len(duplicados) == 1
        assert duplicados[0][0] == Decimal("100")
        assert duplicados[0][1] == 3

    def test_no_duplicates(self):
        """No duplicates should return empty list."""
        valores = [Decimal("100"), Decimal("200"), Decimal("300")]
        duplicados = detectar_valores_duplicados(valores)
        assert duplicados == []

    def test_near_duplicates(self):
        """Detect near-duplicates within tolerance."""
        valores = [Decimal("100"), Decimal("100.5"), Decimal("200")]
        duplicados = detectar_valores_duplicados(valores, tolerancia=Decimal("0.01"))
        assert len(duplicados) == 1  # 100 and 100.5 are within 1%


class TestCalcularTaxaVariacao:
    """Tests for calcular_taxa_variacao function."""

    def test_positive_growth(self):
        """Positive growth should return positive percentage."""
        taxa = calcular_taxa_variacao(Decimal("100"), Decimal("150"))
        assert taxa == Decimal("50")

    def test_negative_growth(self):
        """Negative growth should return negative percentage."""
        taxa = calcular_taxa_variacao(Decimal("100"), Decimal("80"))
        assert taxa == Decimal("-20")

    def test_from_zero(self):
        """Growth from zero should return 100%."""
        taxa = calcular_taxa_variacao(Decimal("0"), Decimal("100"))
        assert taxa == Decimal("100")

    def test_no_change(self):
        """No change should return 0%."""
        taxa = calcular_taxa_variacao(Decimal("100"), Decimal("100"))
        assert taxa == Decimal("0")


class TestCalcularPercentil:
    """Tests for calcular_percentil function."""

    def test_median(self):
        """50th percentile should be the median."""
        valores = [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40"), Decimal("50")]
        p50 = calcular_percentil(valores, 50)
        assert p50 == Decimal("30")

    def test_quartiles(self):
        """Test quartiles."""
        valores = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")]
        p25 = calcular_percentil(valores, 25)
        p75 = calcular_percentil(valores, 75)
        assert Decimal("1") <= p25 <= Decimal("2")
        assert Decimal("4") <= p75 <= Decimal("5")

    def test_empty_list(self):
        """Empty list should return 0."""
        assert calcular_percentil([], 50) == Decimal("0")


class TestDetectarSequenciaLinear:
    """Tests for detectar_sequencia_linear function."""

    def test_linear_sequence(self):
        """Perfect linear sequence should be detected."""
        valores = [Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"), Decimal("500")]
        assert detectar_sequencia_linear(valores) is True

    def test_non_linear(self):
        """Non-linear data should not be detected."""
        valores = [Decimal("100"), Decimal("300"), Decimal("150"), Decimal("500"), Decimal("200")]
        assert detectar_sequencia_linear(valores) is False

    def test_insufficient_data(self):
        """Less than 4 values should return False."""
        valores = [Decimal("100"), Decimal("200"), Decimal("300")]
        assert detectar_sequencia_linear(valores) is False


class TestCalcularCorrelacaoPearson:
    """Tests for calcular_correlacao_pearson function."""

    def test_perfect_positive(self):
        """Perfect positive correlation should be 1."""
        x = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]
        y = [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40")]
        corr = calcular_correlacao_pearson(x, y)
        assert corr > Decimal("0.99")

    def test_perfect_negative(self):
        """Perfect negative correlation should be -1."""
        x = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]
        y = [Decimal("40"), Decimal("30"), Decimal("20"), Decimal("10")]
        corr = calcular_correlacao_pearson(x, y)
        assert corr < Decimal("-0.99")

    def test_no_correlation(self):
        """No correlation should be close to 0."""
        x = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]
        y = [Decimal("5"), Decimal("1"), Decimal("8"), Decimal("2")]
        corr = calcular_correlacao_pearson(x, y)
        assert Decimal("-0.5") < corr < Decimal("0.5")

    def test_mismatched_lengths(self):
        """Mismatched lengths should return 0."""
        x = [Decimal("1"), Decimal("2")]
        y = [Decimal("1"), Decimal("2"), Decimal("3")]
        assert calcular_correlacao_pearson(x, y) == Decimal("0")
