"""Tests for validators."""

import pytest

from irpf_analyzer.shared.validators import (
    validate_cpf,
    validate_cnpj,
    format_cpf,
    format_cnpj,
    mask_cpf,
)


class TestCPFValidation:
    """Tests for CPF validation."""

    def test_valid_cpf(self):
        """Test valid CPF numbers."""
        # Known valid CPFs (generated for testing)
        assert validate_cpf("52998224725") is True
        assert validate_cpf("529.982.247-25") is True
        assert validate_cpf("111.444.777-35") is True

    def test_invalid_cpf_all_same_digits(self):
        """Test that CPFs with all same digits are invalid."""
        assert validate_cpf("11111111111") is False
        assert validate_cpf("00000000000") is False
        assert validate_cpf("99999999999") is False

    def test_invalid_cpf_wrong_length(self):
        """Test CPFs with wrong length."""
        assert validate_cpf("1234567890") is False
        assert validate_cpf("123456789012") is False
        assert validate_cpf("") is False

    def test_invalid_cpf_wrong_check_digits(self):
        """Test CPFs with wrong check digits."""
        assert validate_cpf("52998224726") is False
        assert validate_cpf("52998224724") is False


class TestCNPJValidation:
    """Tests for CNPJ validation."""

    def test_valid_cnpj(self):
        """Test valid CNPJ numbers."""
        assert validate_cnpj("11222333000181") is True
        assert validate_cnpj("11.222.333/0001-81") is True

    def test_invalid_cnpj_all_same_digits(self):
        """Test that CNPJs with all same digits are invalid."""
        assert validate_cnpj("11111111111111") is False
        assert validate_cnpj("00000000000000") is False

    def test_invalid_cnpj_wrong_length(self):
        """Test CNPJs with wrong length."""
        assert validate_cnpj("1122233300018") is False
        assert validate_cnpj("112223330001811") is False


class TestFormatters:
    """Tests for formatting functions."""

    def test_format_cpf(self):
        """Test CPF formatting."""
        assert format_cpf("52998224725") == "529.982.247-25"
        assert format_cpf("529.982.247-25") == "529.982.247-25"

    def test_format_cnpj(self):
        """Test CNPJ formatting."""
        assert format_cnpj("11222333000181") == "11.222.333/0001-81"

    def test_mask_cpf(self):
        """Test CPF masking (shows one extra digit for identification)."""
        assert mask_cpf("52998224725") == "***.***.**7-25"
        assert mask_cpf("12345678900") == "***.***.**9-00"
