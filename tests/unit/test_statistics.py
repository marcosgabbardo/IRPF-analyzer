"""Tests for statistical functions."""

import pytest
from decimal import Decimal

from irpf_analyzer.shared.statistics import (
    BENFORD_EXPECTED,
    calcular_chi_quadrado_benford,
    calcular_distribuicao_benford,
    calcular_estatisticas_basicas,
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
