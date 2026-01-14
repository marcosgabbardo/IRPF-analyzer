"""Shared utilities for IRPF Analyzer."""

from irpf_analyzer.shared.validators import (
    format_cnpj,
    format_cpf,
    mask_cpf,
    validate_cnpj,
    validate_cpf,
    validar_cnpj,
    validar_cpf,
)
from irpf_analyzer.shared.statistics import (
    BENFORD_EXPECTED,
    calcular_chi_quadrado_benford,
    calcular_distribuicao_benford,
    calcular_estatisticas_basicas,
    detectar_outliers_iqr,
    detectar_valores_redondos,
    extrair_primeiro_digito,
)

__all__ = [
    # Validators
    "format_cnpj",
    "format_cpf",
    "mask_cpf",
    "validate_cnpj",
    "validate_cpf",
    "validar_cnpj",
    "validar_cpf",
    # Statistics
    "BENFORD_EXPECTED",
    "calcular_chi_quadrado_benford",
    "calcular_distribuicao_benford",
    "calcular_estatisticas_basicas",
    "detectar_outliers_iqr",
    "detectar_valores_redondos",
    "extrair_primeiro_digito",
]
