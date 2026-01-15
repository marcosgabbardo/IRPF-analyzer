"""Cryptocurrency analyzer for IRPF declarations per IN RFB 1888/2019.

This analyzer checks cryptocurrency assets (Grupo 08) for:
- Capital gains above R$ 35,000/month threshold
- IN 1888/2019 reporting requirements
- Exchange CNPJ validation
- Suspicious patterns (round values, atypical variations)
- Portfolio concentration alerts
"""

from decimal import Decimal

from irpf_analyzer.core.models.analysis import (
    Inconsistency,
    InconsistencyType,
    RiskLevel,
    Warning,
    WarningCategory,
)
from irpf_analyzer.core.models.declaration import BemDireito, Declaration
from irpf_analyzer.core.models.enums import GrupoBem
from irpf_analyzer.core.rules.tax_constants import (
    CONCENTRACAO_CRIPTO_MAXIMA,
    CRIPTO_VALOR_MINIMO_ANALISE,
    GANHO_CAPITAL_CRIPTO_MENSAL,
    PATRIMONIO_CRIPTO_OBRIGATORIO,
    VARIACAO_CRIPTO_MAXIMA,
    VARIACAO_CRIPTO_MINIMA,
)
from irpf_analyzer.shared.validators import validar_cnpj


class CryptocurrencyAnalyzer:
    """Analyzer for cryptocurrency assets per IN RFB 1888/2019.

    The Instrução Normativa RFB 1888/2019 establishes reporting requirements
    for cryptocurrency operations in Brazil:
    - Monthly reporting if capital gains exceed R$ 35,000/month
    - Annual declaration if holdings exceed R$ 5,000
    - Mandatory declaration of all crypto transactions to exchanges

    This analyzer detects potential compliance issues and suspicious patterns.
    """

    # Known Brazilian cryptocurrency exchanges with their CNPJs
    # Updated as of 2025
    KNOWN_EXCHANGES: dict[str, str] = {
        "18189547000142": "Mercado Bitcoin",
        "33042953000171": "Binance Brasil",
        "28527136000153": "Foxbit",
        "34711571000136": "NovaDAX",
        "21830817000141": "BitcoinTrade",
        "29999082000105": "Ripio",
        "40579789000101": "BitPreço",
        "35724943000132": "PagCripto",
        "28176697000160": "Nox Bitcoin",
        "35927388000193": "Coinext",
        "21018182000106": "BTG Pactual (Mynt)",
        "47508411000156": "Nubank Cripto",
        "60701190000104": "Itaú Cripto",
        "00000000000191": "Banco do Brasil Cripto",
    }

    # Cryptocurrency sub-codes within group 08
    CRYPTO_CODES: dict[str, str] = {
        "01": "Bitcoin (BTC)",
        "02": "Outras criptomoedas (altcoins)",
        "03": "Stablecoins (USDT, USDC, etc.)",
        "10": "NFTs (Tokens Não-Fungíveis)",
        "99": "Outros criptoativos",
    }

    def __init__(self, declaration: Declaration) -> None:
        """Initialize analyzer with declaration data.

        Args:
            declaration: The IRPF declaration to analyze
        """
        self.declaration = declaration
        self.inconsistencies: list[Inconsistency] = []
        self.warnings: list[Warning] = []

    def analyze(self) -> tuple[list[Inconsistency], list[Warning]]:
        """Run all cryptocurrency checks.

        Returns:
            Tuple of (inconsistencies, warnings) found during analysis
        """
        cryptos = self._get_cryptoativos()

        if not cryptos:
            return self.inconsistencies, self.warnings

        # Core compliance checks
        self._check_capital_gains_threshold(cryptos)
        self._check_in1888_reporting(cryptos)
        self._check_exchange_validation(cryptos)

        # Pattern detection
        self._check_round_values(cryptos)
        self._check_appreciation_alerts(cryptos)
        self._check_portfolio_diversity(cryptos)

        return self.inconsistencies, self.warnings

    def _get_cryptoativos(self) -> list[BemDireito]:
        """Filter cryptocurrency assets from declaration.

        Returns:
            List of BemDireito objects with grupo == CRIPTOATIVOS
        """
        return [
            bem for bem in self.declaration.bens_direitos
            if bem.grupo == GrupoBem.CRIPTOATIVOS
        ]

    def _check_capital_gains_threshold(self, cryptos: list[BemDireito]) -> None:
        """Check if capital gains exceed IN 1888/2019 monthly threshold.

        Per IN 1888/2019, taxpayers must file monthly reports if their
        cryptocurrency capital gains exceed R$ 35,000 in any month.

        Since we only have annual data, we estimate monthly average.
        """
        total_ganho = Decimal("0")

        # Aggregate lucro_prejuizo from crypto assets
        for crypto in cryptos:
            if crypto.lucro_prejuizo > 0:
                total_ganho += crypto.lucro_prejuizo

        # Aggregate capital gains from crypto alienations
        for alienacao in self.declaration.alienacoes:
            if self._is_crypto_alienacao(alienacao):
                if alienacao.ganho_capital > 0:
                    total_ganho += alienacao.ganho_capital

        if total_ganho <= 0:
            return

        # Estimate monthly average (conservative: divide by 12)
        ganho_mensal_estimado = total_ganho / 12

        if ganho_mensal_estimado > GANHO_CAPITAL_CRIPTO_MENSAL:
            self.inconsistencies.append(
                Inconsistency(
                    tipo=InconsistencyType.GANHO_CAPITAL_CRIPTO_ACIMA_LIMITE,
                    descricao=(
                        f"Ganho de capital em criptomoedas estimado em "
                        f"R$ {ganho_mensal_estimado:,.2f}/mês excede o limite de "
                        f"R$ {GANHO_CAPITAL_CRIPTO_MENSAL:,.2f}/mês da IN RFB 1888/2019. "
                        f"Total anual: R$ {total_ganho:,.2f}"
                    ),
                    valor_declarado=ganho_mensal_estimado,
                    valor_esperado=GANHO_CAPITAL_CRIPTO_MENSAL,
                    risco=RiskLevel.HIGH,
                    recomendacao=(
                        "Verifique se as obrigações da IN RFB 1888/2019 foram cumpridas. "
                        "Operações com ganho > R$ 35k/mês devem ser declaradas mensalmente "
                        "à Receita Federal via e-CAC."
                    ),
                    valor_impacto=total_ganho,
                )
            )

    def _check_in1888_reporting(self, cryptos: list[BemDireito]) -> None:
        """Check IN 1888/2019 reporting obligation.

        Taxpayers holding cryptocurrencies above R$ 5,000 must declare
        them in their annual income tax return.
        """
        total_cripto = sum(c.situacao_atual for c in cryptos)

        if total_cripto >= PATRIMONIO_CRIPTO_OBRIGATORIO:
            # Count how many different cryptos
            num_cryptos = len([c for c in cryptos if c.situacao_atual > 0])

            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Patrimônio em criptoativos: R$ {total_cripto:,.2f} "
                        f"({num_cryptos} ativo(s)). "
                        f"Conforme IN RFB 1888/2019, holdings acima de "
                        f"R$ {PATRIMONIO_CRIPTO_OBRIGATORIO:,.2f} devem ser declarados. "
                        f"Mantenha documentação de aquisição e movimentações."
                    ),
                    risco=RiskLevel.LOW,
                    campo="bens_direitos",
                    categoria=WarningCategory.CONSISTENCIA,
                    informativo=True,  # Informational, doesn't affect score
                    valor_impacto=total_cripto,
                )
            )

    def _check_exchange_validation(self, cryptos: list[BemDireito]) -> None:
        """Validate exchange CNPJs in cryptocurrency declarations.

        Checks if the declared exchange CNPJs are valid and known.
        Unknown exchanges generate warnings for verification.
        """
        for crypto in cryptos:
            if not crypto.cnpj_instituicao:
                # No CNPJ declared - might be self-custody
                if crypto.situacao_atual >= PATRIMONIO_CRIPTO_OBRIGATORIO:
                    self.warnings.append(
                        Warning(
                            mensagem=(
                                f"Criptoativo sem CNPJ de exchange/custodiante: "
                                f"'{crypto.discriminacao[:50]}...' "
                                f"(R$ {crypto.situacao_atual:,.2f}). "
                                f"Se em self-custody, documente carteiras e chaves."
                            ),
                            risco=RiskLevel.LOW,
                            campo="bens_direitos",
                            categoria=WarningCategory.CONSISTENCIA,
                            informativo=True,
                        )
                    )
                continue

            cnpj = crypto.cnpj_instituicao.replace(".", "").replace("/", "").replace("-", "")

            # Validate CNPJ format (validar_cnpj returns tuple (bool, reason))
            is_valid, _ = validar_cnpj(cnpj)
            if not is_valid:
                self.inconsistencies.append(
                    Inconsistency(
                        tipo=InconsistencyType.EXCHANGE_CNPJ_INVALIDO,
                        descricao=(
                            f"CNPJ inválido para exchange/custodiante: "
                            f"'{crypto.cnpj_instituicao}' "
                            f"no criptoativo '{crypto.discriminacao[:30]}...'"
                        ),
                        valor_declarado=None,
                        valor_esperado=None,
                        risco=RiskLevel.MEDIUM,
                        recomendacao="Verifique e corrija o CNPJ da exchange/custodiante.",
                        valor_impacto=crypto.situacao_atual,
                    )
                )
            elif cnpj not in self.KNOWN_EXCHANGES:
                # Valid CNPJ but not a known exchange
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Exchange/custodiante não reconhecido: CNPJ {crypto.cnpj_instituicao} "
                            f"para '{crypto.discriminacao[:30]}...'. "
                            f"Verifique se a instituição está regularizada."
                        ),
                        risco=RiskLevel.LOW,
                        campo="bens_direitos",
                        categoria=WarningCategory.CONSISTENCIA,
                        informativo=True,
                    )
                )

    def _check_round_values(self, cryptos: list[BemDireito]) -> None:
        """Detect suspiciously round values in cryptocurrency declarations.

        Cryptocurrency values are typically not round due to market fluctuations.
        Multiple round values might indicate estimated rather than actual values.
        """
        round_values: list[tuple[BemDireito, Decimal]] = []

        for crypto in cryptos:
            if crypto.situacao_atual < CRIPTO_VALOR_MINIMO_ANALISE:
                continue

            # Check if value is suspiciously round (divisible by 1000 and > 0)
            if crypto.situacao_atual > 0 and crypto.situacao_atual % 1000 == 0:
                round_values.append((crypto, crypto.situacao_atual))

        # Alert if multiple round values found
        if len(round_values) >= 2:
            valores_str = ", ".join(
                f"R$ {v:,.0f}" for _, v in round_values[:3]
            )
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Detectados {len(round_values)} criptoativos com valores redondos "
                        f"({valores_str}). Valores de mercado raramente são redondos. "
                        f"Verifique se os valores declarados refletem cotações reais."
                    ),
                    risco=RiskLevel.LOW,
                    campo="bens_direitos",
                    categoria=WarningCategory.PADRAO,
                    informativo=False,
                    valor_impacto=sum(v for _, v in round_values),
                )
            )

    def _check_appreciation_alerts(self, cryptos: list[BemDireito]) -> None:
        """Check for atypical appreciation or depreciation in crypto holdings.

        Extreme variations (>200% gain or >80% loss) may require additional
        documentation to explain the movements.
        """
        for crypto in cryptos:
            # Skip if previous value too small for meaningful analysis
            if crypto.situacao_anterior < CRIPTO_VALOR_MINIMO_ANALISE:
                continue

            # Calculate year-over-year variation
            variacao = (crypto.situacao_atual - crypto.situacao_anterior) / crypto.situacao_anterior

            # Check for extreme appreciation
            if variacao > VARIACAO_CRIPTO_MAXIMA:
                variacao_pct = variacao * 100
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Valorização atípica em '{crypto.discriminacao[:30]}...': "
                            f"{variacao_pct:.0f}% "
                            f"(de R$ {crypto.situacao_anterior:,.2f} para "
                            f"R$ {crypto.situacao_atual:,.2f}). "
                            f"Documente as operações que justificam esta variação."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="bens_direitos",
                        categoria=WarningCategory.CONSISTENCIA,
                        informativo=False,
                        valor_impacto=crypto.variacao_absoluta,
                    )
                )

            # Check for extreme depreciation
            elif variacao < VARIACAO_CRIPTO_MINIMA:
                variacao_pct = variacao * 100
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Desvalorização atípica em '{crypto.discriminacao[:30]}...': "
                            f"{variacao_pct:.0f}% "
                            f"(de R$ {crypto.situacao_anterior:,.2f} para "
                            f"R$ {crypto.situacao_atual:,.2f}). "
                            f"Verifique se houve venda parcial não declarada como alienação."
                        ),
                        risco=RiskLevel.MEDIUM,
                        campo="bens_direitos",
                        categoria=WarningCategory.CONSISTENCIA,
                        informativo=False,
                        valor_impacto=abs(crypto.variacao_absoluta),
                    )
                )

    def _check_portfolio_diversity(self, cryptos: list[BemDireito]) -> None:
        """Check cryptocurrency portfolio concentration.

        High concentration in a single asset may indicate risk and
        should be documented if intentional.
        """
        # Filter cryptos with meaningful value
        significant_cryptos = [
            c for c in cryptos
            if c.situacao_atual >= CRIPTO_VALOR_MINIMO_ANALISE
        ]

        if len(significant_cryptos) < 2:
            # Need at least 2 assets to analyze concentration
            return

        total_value = sum(c.situacao_atual for c in significant_cryptos)
        if total_value <= 0:
            return

        # Find maximum concentration
        for crypto in significant_cryptos:
            concentration = crypto.situacao_atual / total_value

            if concentration > CONCENTRACAO_CRIPTO_MAXIMA:
                concentration_pct = concentration * 100
                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Alta concentração em '{crypto.discriminacao[:30]}...': "
                            f"{concentration_pct:.0f}% do portfólio de criptoativos "
                            f"(R$ {crypto.situacao_atual:,.2f} de R$ {total_value:,.2f}). "
                            f"Considere diversificação para gestão de risco."
                        ),
                        risco=RiskLevel.LOW,
                        campo="bens_direitos",
                        categoria=WarningCategory.GERAL,
                        informativo=True,  # Informational only
                    )
                )

    def _is_crypto_alienacao(self, alienacao) -> bool:
        """Check if an alienation is related to cryptocurrency.

        Args:
            alienacao: The alienation object to check

        Returns:
            True if alienation appears to be cryptocurrency-related
        """
        if not alienacao.nome_bem:
            return False

        descricao = alienacao.nome_bem.upper()
        crypto_keywords = [
            "BITCOIN", "BTC", "ETHEREUM", "ETH", "CRIPTO", "CRIPTOMOEDA",
            "ALTCOIN", "TOKEN", "NFT", "STABLECOIN", "USDT", "USDC",
            "BINANCE", "LITECOIN", "LTC", "RIPPLE", "XRP", "CARDANO", "ADA",
            "SOLANA", "SOL", "POLKADOT", "DOT", "DOGECOIN", "DOGE",
        ]
        return any(kw in descricao for kw in crypto_keywords)


def analyze_cryptocurrency(
    declaration: Declaration,
) -> tuple[list[Inconsistency], list[Warning]]:
    """Convenience function to analyze cryptocurrency in a declaration.

    Args:
        declaration: The IRPF declaration to analyze

    Returns:
        Tuple of (inconsistencies, warnings) from the analysis
    """
    analyzer = CryptocurrencyAnalyzer(declaration)
    return analyzer.analyze()
