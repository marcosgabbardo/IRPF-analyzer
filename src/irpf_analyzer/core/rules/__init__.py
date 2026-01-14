"""Business rules and thresholds for IRPF analysis."""

from irpf_analyzer.core.rules.tax_constants import (
    ALIQUOTA_MAXIMA,
    DEDUCAO_DEPENDENTE,
    ECONOMIA_MINIMA_SUGESTAO,
    ESPACO_MINIMO_PGBL,
    FAIXAS_IR_ANUAL,
    FAIXAS_IR_MENSAL,
    LIMITE_DOACOES_PERCENTUAL,
    LIMITE_EDUCACAO_PESSOA,
    LIMITE_PGBL_PERCENTUAL,
    LIMITE_SIMPLIFICADA,
    RENDA_MAXIMA_VALIDA,
    RENDA_MINIMA_PGBL,
    RENDA_MINIMA_VALIDA,
    calcular_imposto_anual,
    obter_aliquota_marginal,
)

__all__ = [
    "ALIQUOTA_MAXIMA",
    "DEDUCAO_DEPENDENTE",
    "ECONOMIA_MINIMA_SUGESTAO",
    "ESPACO_MINIMO_PGBL",
    "FAIXAS_IR_ANUAL",
    "FAIXAS_IR_MENSAL",
    "LIMITE_DOACOES_PERCENTUAL",
    "LIMITE_EDUCACAO_PESSOA",
    "LIMITE_PGBL_PERCENTUAL",
    "LIMITE_SIMPLIFICADA",
    "RENDA_MAXIMA_VALIDA",
    "RENDA_MINIMA_PGBL",
    "RENDA_MINIMA_VALIDA",
    "calcular_imposto_anual",
    "obter_aliquota_marginal",
]
