"""Investment optimization analyzer for tax-efficient allocation.

This module provides investment analysis including:
- Tax-efficient allocation suggestions (LCI/LCA vs CDB)
- Real estate fund (FII) dividend exemption opportunities
- Capital loss compensation opportunities
- Investment diversification recommendations

Based on Brazilian tax regulations for investment income.
"""

from collections import defaultdict
from decimal import Decimal
from typing import NamedTuple

from irpf_analyzer.core.models.analysis import (
    RiskLevel,
    Suggestion,
    Warning,
    WarningCategory,
)
from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import GrupoBem, TipoRendimento
from irpf_analyzer.core.rules.tax_constants import ALIQUOTA_MAXIMA


class InvestmentClassification(NamedTuple):
    """Classification of an investment by type and tax treatment."""

    name: str
    value: Decimal
    tax_type: str  # "ISENTO", "EXCLUSIVO", "TRIBUTAVEL"
    tax_rate: Decimal  # Effective or estimated tax rate
    is_fii: bool = False
    is_crypto: bool = False


class InvestmentOptimizationAnalyzer:
    """Analyzes declaration for investment optimization opportunities.

    Detects:
    - Tax-efficient allocation suggestions (LCI/LCA exempt vs CDB taxed)
    - Real estate fund dividend opportunities
    - Capital loss compensation opportunities
    - Portfolio concentration and diversification suggestions
    """

    # Asset codes for investment types
    # LCI/LCA/CRI/CRA are tax-exempt for individuals
    CODIGOS_RENDA_FIXA_ISENTA = {"45", "46", "47", "48"}  # LCI, LCA, CRI, CRA

    # CDB/RDB are subject to exclusive taxation (IOF + IR)
    CODIGOS_RENDA_FIXA_TRIBUTADA = {"41", "42", "43", "44"}  # CDB, RDB, Debêntures

    # FIIs (Fundos de Investimento Imobiliário) - codigo 73
    CODIGO_FII = "73"

    # Criptoativos - grupo 08
    GRUPO_CRIPTO = GrupoBem.CRIPTOATIVOS

    # Minimum investment to consider for suggestions
    VALOR_MINIMO_INVESTIMENTO = Decimal("10000")

    # Threshold for suggesting tax-efficient reallocation
    RATIO_MINIMO_REALOCACAO = Decimal("0.20")  # 20% of taxed investments

    # Average tax rate on CDB/RDB (considering holding period)
    # 22.5% for < 180 days, 20% for 181-360, 17.5% for 361-720, 15% for > 720
    TAXA_MEDIA_IR_CDB = Decimal("0.175")  # Average assuming 1-2 year holding

    # FII dividend exemption threshold (PF with < 10% participation)
    FII_PARTICIPACAO_MAXIMA_ISENCAO = Decimal("0.10")  # 10%

    # Minimum accumulated loss to suggest compensation
    PREJUIZO_MINIMO_COMPENSACAO = Decimal("1000")

    def __init__(self, declaration: Declaration):
        """Initialize analyzer with a declaration.

        Args:
            declaration: The IRPF declaration to analyze
        """
        self.declaration = declaration
        self.suggestions: list[Suggestion] = []
        self.warnings: list[Warning] = []

        # Cached values
        self._renda_tributavel = declaration.total_rendimentos_tributaveis
        self._investments_classified: list[InvestmentClassification] | None = None

    def analyze(self) -> tuple[list[Suggestion], list[Warning]]:
        """Run all investment optimization checks.

        Returns:
            Tuple of (suggestions, warnings) found
        """
        self._analyze_tax_efficient_allocation()
        self._analyze_fii_opportunities()
        self._analyze_loss_compensation()
        self._analyze_portfolio_concentration()

        return self.suggestions, self.warnings

    @property
    def investments_classified(self) -> list[InvestmentClassification]:
        """Classify all investments by type and tax treatment."""
        if self._investments_classified is not None:
            return self._investments_classified

        investments = []

        for bem in self.declaration.bens_direitos:
            if bem.situacao_atual <= 0:
                continue

            # Determine tax treatment based on asset code/group
            tax_type = "TRIBUTAVEL"
            tax_rate = self.TAXA_MEDIA_IR_CDB
            is_fii = False
            is_crypto = False

            # LCI/LCA/CRI/CRA - tax exempt
            if bem.codigo in self.CODIGOS_RENDA_FIXA_ISENTA:
                tax_type = "ISENTO"
                tax_rate = Decimal("0")

            # CDB/RDB/Debêntures - exclusive taxation
            elif bem.codigo in self.CODIGOS_RENDA_FIXA_TRIBUTADA:
                tax_type = "EXCLUSIVO"
                tax_rate = self.TAXA_MEDIA_IR_CDB

            # FII
            elif bem.codigo == self.CODIGO_FII:
                is_fii = True
                tax_type = "ISENTO"  # Dividends are exempt for PF
                tax_rate = Decimal("0")

            # Criptoativos
            elif bem.grupo == self.GRUPO_CRIPTO:
                is_crypto = True
                tax_type = "TRIBUTAVEL"  # Capital gains are taxed
                tax_rate = Decimal("0.15")  # 15% on capital gains

            # Poupança
            elif bem.grupo == GrupoBem.POUPANCA:
                tax_type = "ISENTO"
                tax_rate = Decimal("0")

            # Other funds (check if it looks like FII from description)
            elif bem.grupo == GrupoBem.FUNDOS:
                desc_upper = bem.discriminacao.upper()
                if any(kw in desc_upper for kw in ["FII", "IMOBILIARIO", "IMOBILIÁRIO"]):
                    is_fii = True
                    tax_type = "ISENTO"
                    tax_rate = Decimal("0")
                else:
                    tax_type = "EXCLUSIVO"
                    tax_rate = Decimal("0.15")  # Come-cotas

            investments.append(InvestmentClassification(
                name=bem.discriminacao[:50],
                value=bem.situacao_atual,
                tax_type=tax_type,
                tax_rate=tax_rate,
                is_fii=is_fii,
                is_crypto=is_crypto,
            ))

        self._investments_classified = investments
        return investments

    def _analyze_tax_efficient_allocation(self) -> None:
        """Analyze if taxpayer should reallocate from taxed to exempt investments.

        LCI/LCA are tax-exempt for individuals, while CDB/RDB are subject to
        exclusive taxation (15-22.5% depending on holding period).

        For high-income taxpayers, the tax savings from exempt investments
        can be significant.
        """
        # Calculate totals by tax type
        total_isento = Decimal("0")
        total_tributado = Decimal("0")
        total_investimentos = Decimal("0")

        investimentos_tributados = []

        for inv in self.investments_classified:
            total_investimentos += inv.value

            if inv.tax_type == "ISENTO":
                total_isento += inv.value
            elif inv.tax_type in ("EXCLUSIVO", "TRIBUTAVEL"):
                total_tributado += inv.value
                if inv.value >= self.VALOR_MINIMO_INVESTIMENTO:
                    investimentos_tributados.append(inv)

        # Skip if no significant investments
        if total_investimentos < self.VALOR_MINIMO_INVESTIMENTO * 2:
            return

        # Calculate ratio of taxed investments
        ratio_tributado = total_tributado / total_investimentos if total_investimentos > 0 else Decimal("0")

        # Suggest reallocation if taxed investments are > 60% of portfolio
        if ratio_tributado > Decimal("0.60") and total_tributado > self.VALOR_MINIMO_INVESTIMENTO:
            # Estimate annual tax savings from switching 50% of taxed to exempt
            valor_realocar = total_tributado * Decimal("0.50")
            rendimento_estimado = valor_realocar * Decimal("0.10")  # Assume 10% annual yield
            economia_anual = rendimento_estimado * self.TAXA_MEDIA_IR_CDB

            if economia_anual >= Decimal("100"):
                self.suggestions.append(
                    Suggestion(
                        titulo="Considere diversificar para investimentos isentos",
                        descricao=(
                            f"Você possui R$ {total_tributado:,.2f} ({ratio_tributado*100:.0f}%) "
                            f"em investimentos tributados (CDB, RDB, fundos). "
                            f"Considere alocar parte em LCI/LCA/CRI/CRA, que são isentos de IR. "
                            f"Economia estimada: R$ {economia_anual:,.2f}/ano "
                            f"(considerando realocar 50% e rendimento de 10% a.a.)."
                        ),
                        economia_potencial=economia_anual,
                        prioridade=2,
                    )
                )

        # Specific suggestion for CDB holders
        total_cdb = sum(
            inv.value for inv in self.investments_classified
            if inv.tax_type == "EXCLUSIVO"
            and any(kw in inv.name.upper() for kw in ["CDB", "RDB"])
        )

        if total_cdb > self.VALOR_MINIMO_INVESTIMENTO * 3:
            economia_lci = total_cdb * Decimal("0.10") * self.TAXA_MEDIA_IR_CDB

            self.suggestions.append(
                Suggestion(
                    titulo="Oportunidade: LCI/LCA vs CDB",
                    descricao=(
                        f"Você possui R$ {total_cdb:,.2f} em CDB/RDB. "
                        f"LCI e LCA de bancos com mesma classificação de risco "
                        f"oferecem rentabilidade similar sem tributação. "
                        f"Economia potencial: R$ {economia_lci:,.2f}/ano "
                        f"(considerando rendimento de 10% a.a. e IR médio de 17.5%)."
                    ),
                    economia_potencial=economia_lci,
                    prioridade=1,
                )
            )

    def _analyze_fii_opportunities(self) -> None:
        """Analyze real estate fund (FII) opportunities.

        FIIs offer tax-exempt dividends for individuals who:
        - Hold less than 10% of the fund's shares
        - The fund has at least 50 shareholders
        - The fund's shares are traded on the stock exchange

        Note: Capital gains on FII sales are taxed at 20%.
        """
        # Find existing FII holdings
        total_fii = Decimal("0")
        fii_holdings = []

        for inv in self.investments_classified:
            if inv.is_fii:
                total_fii += inv.value
                fii_holdings.append(inv)

        # Find dividend income from FIIs
        dividendos_fii = Decimal("0")
        for rendimento in self.declaration.rendimentos:
            if rendimento.tipo == TipoRendimento.LUCROS_DIVIDENDOS:
                desc = (rendimento.descricao or "").upper()
                if any(kw in desc for kw in ["FII", "IMOBILIARIO", "IMOBILIÁRIO"]):
                    dividendos_fii += rendimento.valor_anual

        # If user has FIIs but no dividend income, might be holding non-dividend FIIs
        if total_fii > self.VALOR_MINIMO_INVESTIMENTO and dividendos_fii == 0:
            self.warnings.append(
                Warning(
                    mensagem=(
                        f"Você possui R$ {total_fii:,.2f} em FIIs mas não declarou "
                        f"dividendos isentos. Verifique se os dividendos foram "
                        f"corretamente declarados como rendimentos isentos."
                    ),
                    risco=RiskLevel.LOW,
                    campo="rendimentos",
                    categoria=WarningCategory.CONSISTENCIA,
                    informativo=True,
                )
            )

        # If user has significant taxed investments but no FIIs, suggest
        total_investimentos = sum(inv.value for inv in self.investments_classified)

        if total_fii == 0 and total_investimentos > self.VALOR_MINIMO_INVESTIMENTO * 5:
            # Estimate potential tax savings from FII allocation
            valor_sugerido = total_investimentos * Decimal("0.10")  # 10% allocation
            yield_medio_fii = Decimal("0.08")  # 8% average dividend yield
            dividendos_potenciais = valor_sugerido * yield_medio_fii

            if dividendos_potenciais >= Decimal("500"):
                self.suggestions.append(
                    Suggestion(
                        titulo="Considere Fundos Imobiliários (FIIs)",
                        descricao=(
                            f"Você não possui FIIs em carteira. "
                            f"FIIs oferecem dividendos isentos de IR para pessoa física. "
                            f"Alocando 10% da carteira (R$ {valor_sugerido:,.2f}), "
                            f"você poderia receber ~R$ {dividendos_potenciais:,.2f}/ano "
                            f"em dividendos isentos (considerando yield médio de 8% a.a.)."
                        ),
                        economia_potencial=dividendos_potenciais * ALIQUOTA_MAXIMA,
                        prioridade=3,
                    )
                )

    def _analyze_loss_compensation(self) -> None:
        """Analyze capital loss compensation opportunities.

        Brazilian tax law allows:
        - Losses from stock trading can offset gains from stock trading
        - Losses from day-trading can only offset gains from day-trading
        - Losses from FII sales can offset gains from FII sales
        - Crypto losses can offset crypto gains (same asset type)

        Accumulated losses can be carried forward to future years.
        """
        # Analyze alienations for gains and losses
        ganhos_totais = Decimal("0")
        prejuizos_totais = Decimal("0")
        prejuizos_por_tipo: dict[str, Decimal] = defaultdict(Decimal)
        ganhos_por_tipo: dict[str, Decimal] = defaultdict(Decimal)

        for alienacao in self.declaration.alienacoes:
            tipo = alienacao.tipo_bem or "OUTROS"

            if alienacao.tem_ganho:
                ganhos_totais += alienacao.ganho_capital
                ganhos_por_tipo[tipo] += alienacao.ganho_capital
            elif alienacao.tem_perda:
                prejuizo = abs(alienacao.ganho_capital)
                prejuizos_totais += prejuizo
                prejuizos_por_tipo[tipo] += prejuizo

        # Check for accumulated losses that could be compensated
        for tipo, prejuizo in prejuizos_por_tipo.items():
            if prejuizo < self.PREJUIZO_MINIMO_COMPENSACAO:
                continue

            ganho_mesmo_tipo = ganhos_por_tipo.get(tipo, Decimal("0"))

            # If there are losses without matching gains, suggest future compensation
            if prejuizo > ganho_mesmo_tipo:
                prejuizo_acumulado = prejuizo - ganho_mesmo_tipo

                if prejuizo_acumulado >= self.PREJUIZO_MINIMO_COMPENSACAO:
                    self.suggestions.append(
                        Suggestion(
                            titulo=f"Prejuízo acumulado em {tipo}",
                            descricao=(
                                f"Você possui R$ {prejuizo_acumulado:,.2f} em prejuízos "
                                f"de {tipo} que podem ser compensados com ganhos futuros "
                                f"do mesmo tipo. Mantenha controle mensal via GCAP ou "
                                f"planilha para não perder o benefício."
                            ),
                            economia_potencial=prejuizo_acumulado * Decimal("0.15"),
                            prioridade=2,
                        )
                    )

        # Check lucro_prejuizo field in bens_direitos (foreign stocks)
        prejuizo_acoes_exterior = Decimal("0")
        lucro_acoes_exterior = Decimal("0")

        for bem in self.declaration.bens_direitos:
            if bem.tem_lucro_prejuizo_declarado:
                if bem.lucro_prejuizo < 0:
                    prejuizo_acoes_exterior += abs(bem.lucro_prejuizo)
                else:
                    lucro_acoes_exterior += bem.lucro_prejuizo

        if prejuizo_acoes_exterior > self.PREJUIZO_MINIMO_COMPENSACAO:
            if lucro_acoes_exterior > 0:
                compensavel = min(prejuizo_acoes_exterior, lucro_acoes_exterior)
                economia = compensavel * Decimal("0.15")

                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Verifique compensação de prejuízos em ações estrangeiras: "
                            f"Prejuízo R$ {prejuizo_acoes_exterior:,.2f}, "
                            f"Lucro R$ {lucro_acoes_exterior:,.2f}. "
                            f"Economia potencial de até R$ {economia:,.2f}."
                        ),
                        risco=RiskLevel.LOW,
                        campo="bens_direitos",
                        categoria=WarningCategory.PADRAO,
                        informativo=True,
                        valor_impacto=economia,
                    )
                )
            else:
                self.suggestions.append(
                    Suggestion(
                        titulo="Prejuízo em ações estrangeiras",
                        descricao=(
                            f"Você possui R$ {prejuizo_acoes_exterior:,.2f} em prejuízos "
                            f"de ações estrangeiras. Esse valor pode ser compensado com "
                            f"lucros futuros de ações estrangeiras (mesmo tipo de operação)."
                        ),
                        economia_potencial=prejuizo_acoes_exterior * Decimal("0.15"),
                        prioridade=3,
                    )
                )

    def _analyze_portfolio_concentration(self) -> None:
        """Analyze portfolio concentration and diversification.

        High concentration in a single asset type may indicate:
        - Higher risk exposure
        - Missed tax optimization opportunities
        - Potential for better diversification
        """
        # Group investments by type
        por_tipo: dict[str, Decimal] = defaultdict(Decimal)
        total = Decimal("0")

        for inv in self.investments_classified:
            total += inv.value

            if inv.is_fii:
                por_tipo["FII"] += inv.value
            elif inv.is_crypto:
                por_tipo["CRIPTO"] += inv.value
            elif inv.tax_type == "ISENTO":
                por_tipo["RENDA_FIXA_ISENTA"] += inv.value
            elif inv.tax_type == "EXCLUSIVO":
                por_tipo["RENDA_FIXA_TRIBUTADA"] += inv.value
            else:
                por_tipo["OUTROS"] += inv.value

        if total < self.VALOR_MINIMO_INVESTIMENTO:
            return

        # Check for high concentration (> 80% in one type)
        for tipo, valor in por_tipo.items():
            concentracao = valor / total if total > 0 else Decimal("0")

            if concentracao > Decimal("0.80"):
                tipo_legivel = {
                    "FII": "Fundos Imobiliários",
                    "CRIPTO": "Criptoativos",
                    "RENDA_FIXA_ISENTA": "Renda Fixa Isenta (LCI/LCA)",
                    "RENDA_FIXA_TRIBUTADA": "Renda Fixa Tributada (CDB/RDB)",
                    "OUTROS": "Outros Investimentos",
                }.get(tipo, tipo)

                self.warnings.append(
                    Warning(
                        mensagem=(
                            f"Alta concentração em {tipo_legivel}: "
                            f"{concentracao*100:.0f}% da carteira (R$ {valor:,.2f}). "
                            f"Considere diversificar para reduzir riscos e otimizar tributos."
                        ),
                        risco=RiskLevel.LOW,
                        campo="bens_direitos",
                        categoria=WarningCategory.PADRAO,
                        informativo=True,
                        valor_impacto=valor,
                    )
                )


def analyze_investment_optimization(
    declaration: Declaration,
) -> tuple[list[Suggestion], list[Warning]]:
    """Convenience function to run investment optimization analysis.

    Args:
        declaration: The IRPF declaration to analyze

    Returns:
        Tuple of (suggestions, warnings) found
    """
    analyzer = InvestmentOptimizationAnalyzer(declaration)
    return analyzer.analyze()
