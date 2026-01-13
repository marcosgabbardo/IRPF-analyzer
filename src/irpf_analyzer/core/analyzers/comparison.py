"""Comparison analyzer for year-over-year IRPF analysis."""

import re
from decimal import Decimal

from irpf_analyzer.core.models.comparison import (
    AssetHighlight,
    ComparisonResult,
    DeductionComparison,
    IncomeComparison,
    PatrimonyComparison,
    TaxComparison,
    ValueComparison,
)
from irpf_analyzer.core.models.declaration import Declaration
from irpf_analyzer.core.models.enums import GrupoBem


class ComparisonAnalyzer:
    """Analyzes and compares two IRPF declarations from different years."""

    # Display names for asset groups
    GRUPO_DISPLAY_NAMES: dict[GrupoBem, str] = {
        GrupoBem.IMOVEIS: "Imóveis",
        GrupoBem.VEICULOS: "Veículos",
        GrupoBem.PARTICIPACOES_SOCIETARIAS: "Participações Societárias",
        GrupoBem.APLICACOES_FINANCEIRAS: "Aplicações Financeiras",
        GrupoBem.POUPANCA: "Poupança",
        GrupoBem.DEPOSITOS_VISTA: "Depósitos à Vista",
        GrupoBem.FUNDOS: "Fundos",
        GrupoBem.CRIPTOATIVOS: "Criptoativos",
        GrupoBem.OUTROS_BENS: "Outros Bens",
    }

    def __init__(self, decl1: Declaration, decl2: Declaration):
        """Initialize with two declarations.

        Order doesn't matter - they are auto-sorted by year (older first).
        """
        # Auto-sort by year (older first)
        if decl1.ano_exercicio <= decl2.ano_exercicio:
            self.decl_anterior = decl1
            self.decl_atual = decl2
        else:
            self.decl_anterior = decl2
            self.decl_atual = decl1

        self.avisos: list[str] = []

    def validate(self) -> list[str]:
        """Validate that declarations can be compared.

        Returns list of error messages (empty if valid).
        """
        errors = []

        # Check same taxpayer (same CPF)
        if self.decl_anterior.contribuinte.cpf != self.decl_atual.contribuinte.cpf:
            errors.append(
                f"CPFs diferentes: {self.decl_anterior.cpf_masked} vs {self.decl_atual.cpf_masked}. "
                "Só é possível comparar declarações do mesmo contribuinte."
            )

        # Check different years
        if self.decl_anterior.ano_exercicio == self.decl_atual.ano_exercicio:
            errors.append(
                f"Ambas declarações são do mesmo exercício ({self.decl_anterior.ano_exercicio}). "
                "Selecione declarações de anos diferentes."
            )

        return errors

    def compare(self) -> ComparisonResult:
        """Execute comparison and return results."""
        # Check for warnings (non-blocking issues)
        self._check_warnings()

        return ComparisonResult(
            cpf=self.decl_atual.contribuinte.cpf,
            nome_contribuinte=self.decl_atual.contribuinte.nome,
            ano_anterior=self.decl_anterior.ano_exercicio,
            ano_atual=self.decl_atual.ano_exercicio,
            rendimentos=self._compare_income(),
            deducoes=self._compare_deductions(),
            patrimonio=self._compare_patrimony(),
            impostos=self._compare_taxes(),
            destaques_ativos=self._get_asset_highlights(),
            avisos=self.avisos,
        )

    def _check_warnings(self) -> None:
        """Check for non-blocking comparison warnings."""
        # Warn if years are not consecutive
        year_diff = self.decl_atual.ano_exercicio - self.decl_anterior.ano_exercicio
        if year_diff > 1:
            self.avisos.append(
                f"Declarações com {year_diff} anos de diferença. "
                "Variações podem ser significativas."
            )

        # Warn if declaration types differ
        if self.decl_anterior.tipo_declaracao != self.decl_atual.tipo_declaracao:
            self.avisos.append(
                f"Tipos de declaração diferentes: "
                f"{self.decl_anterior.tipo_declaracao.value} → {self.decl_atual.tipo_declaracao.value}. "
                "Isso pode afetar as deduções."
            )

        # Warn if either is rectifying
        if self.decl_anterior.retificadora:
            self.avisos.append(
                f"Declaração {self.decl_anterior.ano_exercicio} é retificadora."
            )
        if self.decl_atual.retificadora:
            self.avisos.append(
                f"Declaração {self.decl_atual.ano_exercicio} é retificadora."
            )

    def _make_value_comparison(
        self,
        campo: str,
        valor_anterior: Decimal,
        valor_atual: Decimal,
    ) -> ValueComparison:
        """Helper to create ValueComparison."""
        return ValueComparison(
            campo=campo,
            ano_anterior=self.decl_anterior.ano_exercicio,
            ano_atual=self.decl_atual.ano_exercicio,
            valor_anterior=valor_anterior,
            valor_atual=valor_atual,
        )

    def _compare_income(self) -> IncomeComparison:
        """Compare income between declarations."""
        d1, d2 = self.decl_anterior, self.decl_atual

        total_anterior = (
            d1.total_rendimentos_tributaveis
            + d1.total_rendimentos_isentos
            + d1.total_rendimentos_exclusivos
        )
        total_atual = (
            d2.total_rendimentos_tributaveis
            + d2.total_rendimentos_isentos
            + d2.total_rendimentos_exclusivos
        )

        return IncomeComparison(
            total_tributaveis=self._make_value_comparison(
                "Rendimentos Tributáveis",
                d1.total_rendimentos_tributaveis,
                d2.total_rendimentos_tributaveis,
            ),
            total_isentos=self._make_value_comparison(
                "Rendimentos Isentos",
                d1.total_rendimentos_isentos,
                d2.total_rendimentos_isentos,
            ),
            total_exclusivos=self._make_value_comparison(
                "Tributação Exclusiva",
                d1.total_rendimentos_exclusivos,
                d2.total_rendimentos_exclusivos,
            ),
            total_geral=self._make_value_comparison(
                "Total de Rendimentos",
                total_anterior,
                total_atual,
            ),
        )

    def _compare_deductions(self) -> DeductionComparison:
        """Compare deductions between declarations."""
        r1 = self.decl_anterior.resumo_deducoes
        r2 = self.decl_atual.resumo_deducoes

        return DeductionComparison(
            total_deducoes=self._make_value_comparison(
                "Total Deduções",
                self.decl_anterior.total_deducoes,
                self.decl_atual.total_deducoes,
            ),
            previdencia_oficial=self._make_value_comparison(
                "Previdência Oficial",
                r1.previdencia_oficial,
                r2.previdencia_oficial,
            ),
            previdencia_privada=self._make_value_comparison(
                "Previdência Privada (PGBL)",
                r1.previdencia_privada,
                r2.previdencia_privada,
            ),
            despesas_medicas=self._make_value_comparison(
                "Despesas Médicas",
                r1.despesas_medicas,
                r2.despesas_medicas,
            ),
            despesas_educacao=self._make_value_comparison(
                "Despesas Educação",
                r1.despesas_educacao,
                r2.despesas_educacao,
            ),
            pensao_alimenticia=self._make_value_comparison(
                "Pensão Alimentícia",
                r1.pensao_alimenticia,
                r2.pensao_alimenticia,
            ),
            dependentes=self._make_value_comparison(
                "Dependentes",
                r1.dependentes,
                r2.dependentes,
            ),
            outras=self._make_value_comparison(
                "Outras Deduções",
                r1.outras + r1.livro_caixa,
                r2.outras + r2.livro_caixa,
            ),
        )

    def _compare_patrimony(self) -> PatrimonyComparison:
        """Compare patrimony between declarations."""
        r1 = self.decl_anterior.resumo_patrimonio
        r2 = self.decl_atual.resumo_patrimonio

        # Get category breakdown
        cat_comparison = self._compare_assets_by_category()

        return PatrimonyComparison(
            patrimonio_liquido_ano_anterior=r1.patrimonio_liquido_atual,
            patrimonio_liquido_ano_atual=r2.patrimonio_liquido_atual,
            total_bens=self._make_value_comparison(
                "Total de Bens",
                r1.total_bens_atual,
                r2.total_bens_atual,
            ),
            total_dividas=self._make_value_comparison(
                "Total de Dívidas",
                r1.total_dividas_atual,
                r2.total_dividas_atual,
            ),
            patrimonio_liquido=self._make_value_comparison(
                "Patrimônio Líquido",
                r1.patrimonio_liquido_atual,
                r2.patrimonio_liquido_atual,
            ),
            por_categoria=cat_comparison,
        )

    def _compare_assets_by_category(self) -> dict[str, ValueComparison]:
        """Group and compare assets by category using smart categorization.

        The group codes in .DEC files are unreliable, so we analyze
        the description to determine the real asset type.
        """
        # Sum by smart category for each declaration
        totals_ant: dict[str, Decimal] = {}
        totals_atu: dict[str, Decimal] = {}

        for bem in self.decl_anterior.bens_direitos:
            cat = self._smart_categorize(bem.discriminacao)
            totals_ant[cat] = totals_ant.get(cat, Decimal("0")) + bem.situacao_atual

        for bem in self.decl_atual.bens_direitos:
            cat = self._smart_categorize(bem.discriminacao)
            totals_atu[cat] = totals_atu.get(cat, Decimal("0")) + bem.situacao_atual

        # Combine all categories from both years
        all_categories = set(totals_ant.keys()) | set(totals_atu.keys())

        categories: dict[str, ValueComparison] = {}
        for cat in sorted(all_categories):
            total_ant = totals_ant.get(cat, Decimal("0"))
            total_atu = totals_atu.get(cat, Decimal("0"))

            # Only include categories with values in either year
            if total_ant > 0 or total_atu > 0:
                categories[cat] = self._make_value_comparison(
                    cat,
                    total_ant,
                    total_atu,
                )

        return categories

    def _compare_taxes(self) -> TaxComparison:
        """Compare tax calculations between declarations."""
        d1, d2 = self.decl_anterior, self.decl_atual

        return TaxComparison(
            base_calculo=self._make_value_comparison(
                "Base de Cálculo",
                d1.base_calculo,
                d2.base_calculo,
            ),
            imposto_devido=self._make_value_comparison(
                "Imposto Devido",
                d1.imposto_devido,
                d2.imposto_devido,
            ),
            imposto_pago=self._make_value_comparison(
                "Imposto Pago (Retido)",
                d1.imposto_pago,
                d2.imposto_pago,
            ),
            saldo_imposto=self._make_value_comparison(
                "Saldo de Imposto",
                d1.saldo_imposto,
                d2.saldo_imposto,
            ),
        )

    def _get_asset_highlights(self, top_n: int = 5) -> list[AssetHighlight]:
        """Get top gainers, losers, new assets, and sold assets."""
        highlights: list[AssetHighlight] = []

        # Create lookup maps by normalized description
        bens_ant = {
            self._normalize_desc(b.discriminacao): b
            for b in self.decl_anterior.bens_direitos
        }
        bens_atu = {
            self._normalize_desc(b.discriminacao): b
            for b in self.decl_atual.bens_direitos
        }

        # Find matching assets and calculate variations
        variations: list[tuple] = []
        for key, bem_atu in bens_atu.items():
            if key in bens_ant:
                bem_ant = bens_ant[key]
                var = bem_atu.situacao_atual - bem_ant.situacao_atual
                if var != 0 and (bem_ant.situacao_atual > 0 or bem_atu.situacao_atual > 0):
                    variations.append(
                        (bem_atu, bem_ant.situacao_atual, bem_atu.situacao_atual, var)
                    )

        # Top gainers
        gainers = sorted(variations, key=lambda x: x[3], reverse=True)[:top_n]
        for bem, val_ant, val_atu, var in gainers:
            if var > 0:
                pct = (var / val_ant * 100) if val_ant > 0 else None
                highlights.append(
                    AssetHighlight(
                        descricao=bem.discriminacao[:60],
                        grupo=self._smart_categorize(bem.discriminacao),
                        valor_ano_anterior=val_ant,
                        valor_ano_atual=val_atu,
                        variacao_absoluta=var,
                        variacao_percentual=pct,
                        tipo="gainer",
                    )
                )

        # Top losers - exclude liquidatable assets (CDB, LCA, etc.) which are normal redemptions
        real_losses = [
            (bem, val_ant, val_atu, var)
            for bem, val_ant, val_atu, var in variations
            if var < 0 and not self._is_liquidatable_asset(bem)
        ]
        losers = sorted(real_losses, key=lambda x: x[3])[:top_n]
        for bem, val_ant, val_atu, var in losers:
            pct = (var / val_ant * 100) if val_ant > 0 else None
            highlights.append(
                AssetHighlight(
                    descricao=bem.discriminacao[:60],
                    grupo=self._smart_categorize(bem.discriminacao),
                    valor_ano_anterior=val_ant,
                    valor_ano_atual=val_atu,
                    variacao_absoluta=var,
                    variacao_percentual=pct,
                    tipo="loser",
                )
            )

        # New assets (in current but not in previous)
        new_assets = []
        for key, bem in bens_atu.items():
            if key not in bens_ant and bem.situacao_atual > 0:
                new_assets.append((bem, bem.situacao_atual))

        # Sort by value and take top_n
        new_assets.sort(key=lambda x: x[1], reverse=True)
        for bem, valor in new_assets[:top_n]:
            highlights.append(
                AssetHighlight(
                    descricao=bem.discriminacao[:60],
                    grupo=self._smart_categorize(bem.discriminacao),
                    valor_ano_anterior=Decimal("0"),
                    valor_ano_atual=valor,
                    variacao_absoluta=valor,
                    variacao_percentual=None,
                    tipo="new",
                )
            )

        # Assets that went to zero - separate redemptions from sales
        redeemed_assets = []  # CDB, LCA, etc. (normal redemptions)
        sold_assets = []  # Real sales

        for key, bem in bens_ant.items():
            current_value = Decimal("0")
            if key in bens_atu:
                current_value = bens_atu[key].situacao_atual

            if bem.situacao_atual > 0 and current_value == 0:
                if self._is_liquidatable_asset(bem):
                    redeemed_assets.append((bem, bem.situacao_atual))
                else:
                    sold_assets.append((bem, bem.situacao_atual))

        # Top redeemed (liquidatable assets - informational only)
        redeemed_assets.sort(key=lambda x: x[1], reverse=True)
        for bem, valor in redeemed_assets[:top_n]:
            highlights.append(
                AssetHighlight(
                    descricao=bem.discriminacao[:60],
                    grupo=self._smart_categorize(bem.discriminacao),
                    valor_ano_anterior=valor,
                    valor_ano_atual=Decimal("0"),
                    variacao_absoluta=-valor,
                    variacao_percentual=Decimal("-100"),
                    tipo="redeemed",  # Resgatado, não vendido
                )
            )

        # Top sold (real sales, not redemptions)
        sold_assets.sort(key=lambda x: x[1], reverse=True)
        for bem, valor in sold_assets[:top_n]:
            highlights.append(
                AssetHighlight(
                    descricao=bem.discriminacao[:60],
                    grupo=self._smart_categorize(bem.discriminacao),
                    valor_ano_anterior=valor,
                    valor_ano_atual=Decimal("0"),
                    variacao_absoluta=-valor,
                    variacao_percentual=Decimal("-100"),
                    tipo="sold",
                )
            )

        return highlights

    def _is_liquidatable_asset(self, bem) -> bool:
        """Check if asset type is a normal redemption (not a real sale/loss).

        CDBs, LCAs, LCIs, and similar fixed income products going to zero
        is a normal operation (matured or redeemed), not a loss.
        """
        descricao_upper = bem.discriminacao.upper()

        # Fixed income products that mature/redeem normally
        fixed_income_keywords = [
            "CDB", "LCA", "LCI", "LF ",
            "RENDA FIXA", "TESOURO", "DEBENTURE", "DEBÊNTURE",
            "APLICACAO", "APLICAÇÃO",
        ]
        for keyword in fixed_income_keywords:
            if keyword in descricao_upper:
                return True

        # Account balances (just money being moved)
        balance_keywords = [
            "SALDO EM CONTA", "SALDO DE CONTA",
            "CONTA CORRENTE", "CONTA POUPANÇA",
            "SALDO DE R$", "SALDO EM R$",
            "SALDO DE US$", "SALDO EM US$",
        ]
        for keyword in balance_keywords:
            if keyword in descricao_upper:
                return True

        # Certain groups are typically safe redemptions
        safe_groups = [
            GrupoBem.APLICACOES_FINANCEIRAS,
            GrupoBem.POUPANCA,
            GrupoBem.DEPOSITOS_VISTA,
        ]
        if bem.grupo in safe_groups:
            return True

        return False

    def _normalize_desc(self, desc: str) -> str:
        """Normalize description for matching across years.

        Removes dates, values, and variable parts to match same assets
        even if description changed slightly.
        """
        normalized = desc.upper().strip()
        # Remove dates in various formats
        normalized = re.sub(r"\d{2}/\d{2}/\d{4}", "", normalized)
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}", "", normalized)
        # Remove currency values
        normalized = re.sub(r"R\$[\d\.,]+", "", normalized)
        normalized = re.sub(r"US\$[\d\.,]+", "", normalized)
        # Collapse whitespace
        normalized = re.sub(r"\s+", " ", normalized)
        # Limit length for matching
        return normalized[:100]

    def _smart_categorize(self, discriminacao: str) -> str:
        """Determine asset category based on description text.

        The group codes in .DEC files are unreliable, so we analyze
        the description to determine the real asset type.
        """
        desc = discriminacao.upper()

        # === Imóveis ===
        imoveis_keywords = [
            "APARTAMENTO", "CASA ", "TERRENO", "LOTE ", "IMÓVEL", "IMOVEL",
            "SALA COMERCIAL", "GALPÃO", "GALPAO", "PRÉDIO", "PREDIO",
            "FAZENDA", "SÍTIO", "SITIO", "CHÁCARA", "CHACARA",
            "GARAGEM", "BOX ", "EDIFÍCIO", "EDIFICIO", " ED. ", "CONDOMÍNIO",
        ]
        for kw in imoveis_keywords:
            if kw in desc:
                return "Imóveis"

        # === Veículos (marcas e tipos) ===
        veiculos_keywords = [
            # Marcas
            "VOLKSWAGEN", "VW ", "TOYOTA", "HONDA", "CHEVROLET", "FIAT",
            "FORD", "HYUNDAI", "NISSAN", "MERCEDES", "BMW", "AUDI",
            "JEEP", "MITSUBISHI", "RENAULT", "PEUGEOT", "CITROEN",
            "KIA", "LAND ROVER", "PORSCHE", "VOLVO", "SUBARU",
            # Modelos populares
            "COROLLA", "CIVIC", "GOL ", "ONIX", "HB20", "CRETA",
            "COMPASS", "RENEGADE", "KICKS", "T-CROSS", "TCROSS",
            "TAOS", "TIGUAN", "RAV4", "HILUX", "S10 ", "RANGER",
            # Tipos
            "MOTOCICLETA", "MOTO ", "BARCO", "LANCHA", "JET SKI",
            "QUADRICICLO", "CAMINHÃO", "CAMINHAO", "ÔNIBUS", "ONIBUS",
        ]
        for kw in veiculos_keywords:
            if kw in desc:
                return "Veículos"

        # === Participações Societárias ===
        # Must have EMPRESA/LTDA/S.A. AND indicators like CAPITAL, QUOTA, CNPJ
        societarias_patterns = [
            (["EMPRESA", "LTDA", "S.A.", "S/A", " SA ", "S/S"], ["CAPITAL", "QUOTA", "CNPJ", "PARTICIPAÇÃO", "PARTICIPACAO"]),
        ]
        for primary, secondary in societarias_patterns:
            if any(p in desc for p in primary) and any(s in desc for s in secondary):
                return "Participações Societárias"

        # === Criptoativos (check early to avoid misclassification) ===
        crypto_keywords = [
            "BITCOIN", "BTC", "ETHEREUM", "ETH", "CRIPTO", "CRYPTO",
            "LITECOIN", "RIPPLE", "CARDANO", "SOLANA", "DOGECOIN",
        ]
        for kw in crypto_keywords:
            if kw in desc:
                return "Criptoativos"

        # === Aplicações Financeiras (renda fixa) - check BEFORE ações ===
        # This must be before ações because "APLICACAO" could match both
        aplicacoes_keywords = [
            "CDB", "LCA", "LCI", "LF ", "DEBENTURE", "DEBÊNTURE",
            "TESOURO", "RENDA FIXA", "TITULO", "TÍTULO",
        ]
        for kw in aplicacoes_keywords:
            if kw in desc:
                return "Aplicações Financeiras"

        # === Ações Estrangeiras (check before generic ações) ===
        foreign_indicators = ["$", "US$", "USD", "AVENUE", "INTERACTIVE BROKERS", "EXTERIOR"]
        if any(ind in desc for ind in foreign_indicators):
            # Has foreign indicators - likely foreign stocks or deposits
            if any(kw in desc for kw in ["SALDO", "CONTA", "CASH"]):
                return "Depósitos e Saldos"
            return "Ações Estrangeiras"

        # === Ações (stocks) ===
        acoes_keywords = [
            "AÇÃO", "ACAO", "ACOES", "AÇÕES",
            "BOVESPA", "B3 ", " B3", "CORRETORA",
            # Common stock tickers patterns
            "PETR4", "VALE3", "ITUB4", "BBDC4", "WEGE3",
        ]
        for kw in acoes_keywords:
            if kw in desc:
                return "Ações"

        # === Fundos ===
        fundos_keywords = [
            "FUNDO ", "FII ", " FII", "FIDC", "FIP ",
            " ETF", "ETF ", "MULTIMERCADO", "RENDA VARIÁVEL",
        ]
        for kw in fundos_keywords:
            if kw in desc:
                return "Fundos"

        # === Generic "APLICACAO" fallback (after specific types checked) ===
        if "APLICACAO" in desc or "APLICAÇÃO" in desc:
            return "Aplicações Financeiras"

        # === Poupança ===
        if "POUPANÇA" in desc or "POUPANCA" in desc:
            return "Poupança"

        # === Depósitos/Saldos ===
        depositos_keywords = [
            "SALDO EM CONTA", "SALDO DE CONTA", "CONTA CORRENTE",
            "SALDO DE R$", "SALDO EM R$", "SALDO DE US$", "SALDO EM US$",
            "DEPOSITO", "DEPÓSITO",
        ]
        for kw in depositos_keywords:
            if kw in desc:
                return "Depósitos e Saldos"

        # === Default ===
        return "Outros Bens"


def compare_declarations(decl1: Declaration, decl2: Declaration) -> ComparisonResult:
    """Convenience function to compare two declarations.

    Raises ValueError if declarations cannot be compared (different CPF, same year).
    """
    analyzer = ComparisonAnalyzer(decl1, decl2)
    errors = analyzer.validate()
    if errors:
        raise ValueError("\n".join(errors))
    return analyzer.compare()
