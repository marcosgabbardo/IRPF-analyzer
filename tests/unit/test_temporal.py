"""Tests for temporal pattern analyzer."""

from decimal import Decimal

import pytest

from irpf_analyzer.core.analyzers.temporal import (
    TemporalPatternAnalyzer,
    TemporalPattern,
    analyze_temporal_patterns,
)
from irpf_analyzer.core.models import (
    Declaration,
    TipoDeclaracao,
    RiskLevel,
)
from irpf_analyzer.core.models.declaration import Contribuinte
from irpf_analyzer.core.models.analysis import InconsistencyType
from irpf_analyzer.core.models.patrimony import BemDireito, ResumoPatrimonio
from irpf_analyzer.core.models.deductions import Deducao
from irpf_analyzer.core.models.enums import TipoDeducao, GrupoBem


def create_declaration(
    ano: int,
    renda_tributavel: Decimal = Decimal("100000"),
    renda_isenta: Decimal = Decimal("0"),
    patrimonio: Decimal = Decimal("500000"),
    despesas_medicas: Decimal = Decimal("5000"),
    cpf: str = "52998224725",
    bens: list | None = None,
) -> Declaration:
    """Helper to create a declaration for testing."""
    if bens is None:
        bens = [
            BemDireito(
                grupo=GrupoBem.IMOVEIS,
                codigo="11",
                discriminacao="Apartamento",
                situacao_anterior=patrimonio,
                situacao_atual=patrimonio,
            )
        ]

    # Create deductions list (resumo_deducoes is computed from deducoes)
    deducoes = []
    if despesas_medicas > 0:
        deducoes.append(
            Deducao(tipo=TipoDeducao.DESPESAS_MEDICAS, valor=despesas_medicas)
        )

    return Declaration(
        contribuinte=Contribuinte(cpf=cpf, nome="Test User"),
        ano_exercicio=ano,
        ano_calendario=ano - 1,
        tipo_declaracao=TipoDeclaracao.COMPLETA,
        total_rendimentos_tributaveis=renda_tributavel,
        total_rendimentos_isentos=renda_isenta,
        bens_direitos=bens,
        deducoes=deducoes,
    )


class TestTemporalPatternAnalyzerInit:
    """Tests for TemporalPatternAnalyzer initialization."""

    def test_requires_at_least_two_declarations(self):
        """Test that analyzer requires at least 2 declarations."""
        decl = create_declaration(2025)

        with pytest.raises(ValueError, match="pelo menos 2 declarações"):
            TemporalPatternAnalyzer([decl])

    def test_requires_same_taxpayer(self):
        """Test that all declarations must be from the same taxpayer."""
        decl1 = create_declaration(2024, cpf="52998224725")
        decl2 = create_declaration(2025, cpf="11144477735")

        with pytest.raises(ValueError, match="mesmo contribuinte"):
            TemporalPatternAnalyzer([decl1, decl2])

    def test_requires_different_years(self):
        """Test that declarations must be from different years."""
        decl1 = create_declaration(2025)
        decl2 = create_declaration(2025)

        with pytest.raises(ValueError, match="anos diferentes"):
            TemporalPatternAnalyzer([decl1, decl2])

    def test_sorts_by_year(self):
        """Test that declarations are sorted by year."""
        decl2025 = create_declaration(2025)
        decl2023 = create_declaration(2023)
        decl2024 = create_declaration(2024)

        analyzer = TemporalPatternAnalyzer([decl2025, decl2023, decl2024])

        anos = [d.ano_exercicio for d in analyzer.declarations]
        assert anos == [2023, 2024, 2025]

    def test_periodo_property(self):
        """Test that periodo property returns correct range."""
        decl1 = create_declaration(2023)
        decl2 = create_declaration(2025)

        analyzer = TemporalPatternAnalyzer([decl1, decl2])

        assert analyzer.periodo == "2023-2025"


class TestRendaEstagnadaPatrimonioCrescente:
    """Tests for stagnant income with growing patrimony detection."""

    def test_detects_stagnant_income_growing_patrimony(self):
        """Test detection of stagnant income with growing patrimony."""
        # Year 1: Income 100k, Patrimony 500k
        # Year 2: Income 102k (+2%), Patrimony 650k (+30%)
        # Year 3: Income 104k (+2%), Patrimony 850k (+31%)
        decl1 = create_declaration(2023, renda_tributavel=Decimal("100000"), patrimonio=Decimal("500000"))
        decl2 = create_declaration(2024, renda_tributavel=Decimal("102000"), patrimonio=Decimal("650000"))
        decl3 = create_declaration(2025, renda_tributavel=Decimal("104000"), patrimonio=Decimal("850000"))

        analyzer = TemporalPatternAnalyzer([decl1, decl2, decl3])
        patterns = analyzer.analyze()

        stagnant_patterns = [
            p for p in patterns
            if p.tipo == InconsistencyType.RENDA_ESTAGNADA_PATRIMONIO_CRESCENTE
        ]
        assert len(stagnant_patterns) > 0
        assert stagnant_patterns[0].risco == RiskLevel.HIGH

    def test_no_detection_when_income_grows(self):
        """Test no detection when income grows with patrimony."""
        # Income growing 15% per year
        decl1 = create_declaration(2023, renda_tributavel=Decimal("100000"), patrimonio=Decimal("500000"))
        decl2 = create_declaration(2024, renda_tributavel=Decimal("115000"), patrimonio=Decimal("650000"))
        decl3 = create_declaration(2025, renda_tributavel=Decimal("132000"), patrimonio=Decimal("850000"))

        analyzer = TemporalPatternAnalyzer([decl1, decl2, decl3])
        patterns = analyzer.analyze()

        stagnant_patterns = [
            p for p in patterns
            if p.tipo == InconsistencyType.RENDA_ESTAGNADA_PATRIMONIO_CRESCENTE
        ]
        assert len(stagnant_patterns) == 0


class TestQuedaSubitaRenda:
    """Tests for sudden income drop detection."""

    def test_detects_sudden_income_drop(self):
        """Test detection of sudden income drop with stable patrimony."""
        decl1 = create_declaration(2024, renda_tributavel=Decimal("200000"), patrimonio=Decimal("500000"))
        decl2 = create_declaration(2025, renda_tributavel=Decimal("100000"), patrimonio=Decimal("500000"))  # 50% drop

        analyzer = TemporalPatternAnalyzer([decl1, decl2])
        patterns = analyzer.analyze()

        drop_patterns = [
            p for p in patterns
            if p.tipo == InconsistencyType.QUEDA_SUBITA_RENDA
        ]
        assert len(drop_patterns) > 0

    def test_no_detection_when_patrimony_also_drops(self):
        """Test no detection when patrimony drops with income."""
        decl1 = create_declaration(2024, renda_tributavel=Decimal("200000"), patrimonio=Decimal("500000"))
        decl2 = create_declaration(2025, renda_tributavel=Decimal("100000"), patrimonio=Decimal("300000"))  # Both drop

        analyzer = TemporalPatternAnalyzer([decl1, decl2])
        patterns = analyzer.analyze()

        drop_patterns = [
            p for p in patterns
            if p.tipo == InconsistencyType.QUEDA_SUBITA_RENDA
        ]
        assert len(drop_patterns) == 0


class TestDespesasMedicasConstantes:
    """Tests for constant medical expenses detection."""

    def test_detects_constant_medical_expenses(self):
        """Test detection of suspiciously constant medical expenses."""
        # Medical expenses vary by less than 10% each year (very suspicious)
        decl1 = create_declaration(2023, despesas_medicas=Decimal("10000"))
        decl2 = create_declaration(2024, despesas_medicas=Decimal("10200"))  # +2%
        decl3 = create_declaration(2025, despesas_medicas=Decimal("10400"))  # +2%

        analyzer = TemporalPatternAnalyzer([decl1, decl2, decl3])
        patterns = analyzer.analyze()

        constant_patterns = [
            p for p in patterns
            if p.tipo == InconsistencyType.DESPESAS_MEDICAS_CONSTANTES
        ]
        assert len(constant_patterns) > 0

    def test_no_detection_with_varying_expenses(self):
        """Test no detection when medical expenses vary significantly."""
        decl1 = create_declaration(2023, despesas_medicas=Decimal("10000"))
        decl2 = create_declaration(2024, despesas_medicas=Decimal("15000"))  # +50%
        decl3 = create_declaration(2025, despesas_medicas=Decimal("8000"))   # -47%

        analyzer = TemporalPatternAnalyzer([decl1, decl2, decl3])
        patterns = analyzer.analyze()

        constant_patterns = [
            p for p in patterns
            if p.tipo == InconsistencyType.DESPESAS_MEDICAS_CONSTANTES
        ]
        assert len(constant_patterns) == 0


class TestPadraoLiquidacao:
    """Tests for liquidation pattern detection."""

    def test_detects_systematic_liquidation(self):
        """Test detection of systematic asset liquidation.

        The analyzer detects liquidation when:
        - 2+ assets are liquidated in a year
        - Total liquidated > R$ 50,000
        - This happens in 2+ years
        """
        # Year 1: Has 4 assets (total > 100k to trigger pattern)
        bens_2023 = [
            BemDireito(grupo=GrupoBem.IMOVEIS, codigo="11", discriminacao="Apartamento Centro", situacao_anterior=Decimal("300000"), situacao_atual=Decimal("300000")),
            BemDireito(grupo=GrupoBem.IMOVEIS, codigo="12", discriminacao="Casa Praia", situacao_anterior=Decimal("200000"), situacao_atual=Decimal("200000")),
            BemDireito(grupo=GrupoBem.VEICULOS, codigo="21", discriminacao="BMW X5", situacao_anterior=Decimal("150000"), situacao_atual=Decimal("150000")),
            BemDireito(grupo=GrupoBem.VEICULOS, codigo="22", discriminacao="Mercedes C180", situacao_anterior=Decimal("100000"), situacao_atual=Decimal("100000")),
        ]
        decl1 = create_declaration(2023, bens=bens_2023)

        # Year 2: Sold 2 assets (Casa Praia + BMW X5) = R$ 350k > R$ 50k threshold
        bens_2024 = [
            BemDireito(grupo=GrupoBem.IMOVEIS, codigo="11", discriminacao="Apartamento Centro", situacao_anterior=Decimal("300000"), situacao_atual=Decimal("300000")),
            BemDireito(grupo=GrupoBem.VEICULOS, codigo="22", discriminacao="Mercedes C180", situacao_anterior=Decimal("100000"), situacao_atual=Decimal("100000")),
        ]
        decl2 = create_declaration(2024, bens=bens_2024)

        # Year 3: Sold 2 more assets (Apartamento + Mercedes) = R$ 400k > R$ 50k threshold
        bens_2025 = []
        decl3 = create_declaration(2025, bens=bens_2025)

        analyzer = TemporalPatternAnalyzer([decl1, decl2, decl3])
        patterns = analyzer.analyze()

        liquidation_patterns = [
            p for p in patterns
            if p.tipo == InconsistencyType.PADRAO_LIQUIDACAO_SUSPEITO
        ]
        assert len(liquidation_patterns) > 0


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_analyze_temporal_patterns_returns_list(self):
        """Test that convenience function returns list of patterns."""
        decl1 = create_declaration(2024)
        decl2 = create_declaration(2025)

        result = analyze_temporal_patterns([decl1, decl2])

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, TemporalPattern)

    def test_analyze_temporal_patterns_raises_on_invalid_input(self):
        """Test that convenience function raises on invalid input."""
        decl = create_declaration(2025)

        with pytest.raises(ValueError):
            analyze_temporal_patterns([decl])


class TestTemporalPatternModel:
    """Tests for TemporalPattern model."""

    def test_pattern_has_required_fields(self):
        """Test that TemporalPattern has all required fields."""
        pattern = TemporalPattern(
            tipo=InconsistencyType.RENDA_ESTAGNADA_PATRIMONIO_CRESCENTE,
            descricao="Test description",
            anos_afetados=[2024, 2025],
            risco=RiskLevel.HIGH,
        )

        assert pattern.tipo == InconsistencyType.RENDA_ESTAGNADA_PATRIMONIO_CRESCENTE
        assert pattern.descricao == "Test description"
        assert pattern.anos_afetados == [2024, 2025]
        assert pattern.risco == RiskLevel.HIGH
        assert pattern.valor_impacto is None
        assert pattern.recomendacao is None

    def test_pattern_with_optional_fields(self):
        """Test TemporalPattern with optional fields."""
        pattern = TemporalPattern(
            tipo=InconsistencyType.QUEDA_SUBITA_RENDA,
            descricao="Income dropped",
            anos_afetados=[2024, 2025],
            risco=RiskLevel.MEDIUM,
            valor_impacto=Decimal("50000"),
            recomendacao="Check income sources",
        )

        assert pattern.valor_impacto == Decimal("50000")
        assert pattern.recomendacao == "Check income sources"
