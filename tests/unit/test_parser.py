"""Tests for DEC and DBK file parsers."""

from decimal import Decimal
from pathlib import Path

import pytest

from irpf_analyzer.infrastructure.parsers.dec_parser import (
    DECParser,
    parse_dec_file,
    _parse_decimal,
    _parse_date,
)
from irpf_analyzer.infrastructure.parsers.dbk_parser import DBKParser, parse_dbk_file
from irpf_analyzer.infrastructure.parsers import parse_file, detect_file_type, FileType
from irpf_analyzer.core.models.enums import TipoDeclaracao, TipoDependente, TipoDeducao


class TestParseDecimal:
    """Tests for _parse_decimal function."""

    def test_parse_simple_value(self):
        """Test parsing simple decimal values."""
        assert _parse_decimal("00000000058240") == Decimal("582.40")
        assert _parse_decimal("00000000050000") == Decimal("500.00")

    def test_parse_large_value(self):
        """Test parsing large values."""
        assert _parse_decimal("00002067445350") == Decimal("20674453.50")
        assert _parse_decimal("00000214000000") == Decimal("2140000.00")

    def test_parse_zero(self):
        """Test parsing zero values."""
        assert _parse_decimal("00000000000000") == Decimal("0")
        assert _parse_decimal("") == Decimal("0")

    def test_parse_with_spaces(self):
        """Test parsing values with spaces."""
        assert _parse_decimal("  00000058240  ") == Decimal("582.40")

    def test_parse_negative(self):
        """Test parsing negative values."""
        assert _parse_decimal("-00000000058240") == Decimal("-582.40")

    def test_parse_invalid(self):
        """Test parsing invalid values returns zero."""
        assert _parse_decimal("ABCDEF") == Decimal("0")
        assert _parse_decimal("   ") == Decimal("0")


class TestParseDate:
    """Tests for _parse_date function."""

    def test_parse_valid_date(self):
        """Test parsing valid dates in DDMMYYYY format."""
        date = _parse_date("29062017")
        assert date is not None
        assert date.day == 29
        assert date.month == 6
        assert date.year == 2017

    def test_parse_invalid_date(self):
        """Test parsing invalid dates returns None."""
        assert _parse_date("") is None
        assert _parse_date("00000000") is None
        assert _parse_date("invalid") is None

    def test_parse_short_date(self):
        """Test parsing date that's too short."""
        assert _parse_date("290620") is None


class TestDECParser:
    """Tests for DECParser class."""

    @pytest.fixture
    def real_dec_path(self) -> Path:
        """Path to real DEC file for testing."""
        return Path(__file__).parent.parent / "fixtures" / "83158073072-IRPF-A-2025-2024-ORIGI.DEC"

    def test_parse_real_file(self, real_dec_path: Path):
        """Test parsing real DEC file."""
        if not real_dec_path.exists():
            pytest.skip("Real DEC file not available")

        declaration = parse_dec_file(real_dec_path)

        # Basic info
        assert declaration.ano_exercicio == 2025
        assert declaration.ano_calendario == 2024
        assert declaration.contribuinte.nome == "MARCOS D AVILA GABBARDO"
        assert declaration.contribuinte.cpf == "83158073072"
        assert declaration.tipo_declaracao == TipoDeclaracao.COMPLETA

    def test_parse_dependentes(self, real_dec_path: Path):
        """Test parsing dependents from real file."""
        if not real_dec_path.exists():
            pytest.skip("Real DEC file not available")

        declaration = parse_dec_file(real_dec_path)

        assert len(declaration.dependentes) >= 1
        dep = declaration.dependentes[0]
        assert dep.nome == "LUCAS LOPES GABBARDO"
        assert dep.cpf == "05476308083"
        assert dep.tipo == TipoDependente.FILHO_ENTEADO_ATE_21
        assert dep.data_nascimento is not None
        assert dep.data_nascimento.year == 2017

    def test_parse_deducoes_medicas(self, real_dec_path: Path):
        """Test parsing medical expenses from real file."""
        if not real_dec_path.exists():
            pytest.skip("Real DEC file not available")

        declaration = parse_dec_file(real_dec_path)

        # Should have 5 medical expenses
        assert len(declaration.deducoes) == 5

        # Check total
        total = sum(d.valor for d in declaration.deducoes)
        assert total == Decimal("2964.80")

        # Check one specific expense
        genesis = next(
            (d for d in declaration.deducoes if "GENESIS" in d.nome_prestador),
            None
        )
        assert genesis is not None
        assert genesis.tipo == TipoDeducao.DESPESAS_MEDICAS
        assert genesis.valor == Decimal("582.40")
        assert genesis.cnpj_prestador == "50020892000160"

    def test_parse_bens_direitos(self, real_dec_path: Path):
        """Test parsing assets from real file."""
        if not real_dec_path.exists():
            pytest.skip("Real DEC file not available")

        declaration = parse_dec_file(real_dec_path)

        assert len(declaration.bens_direitos) > 0

        # Check that we have assets with values
        bens_com_valor = [b for b in declaration.bens_direitos if b.situacao_atual > 0 or b.situacao_anterior > 0]
        assert len(bens_com_valor) > 0

    def test_resumo_patrimonio(self, real_dec_path: Path):
        """Test patrimony summary calculation."""
        if not real_dec_path.exists():
            pytest.skip("Real DEC file not available")

        declaration = parse_dec_file(real_dec_path)
        resumo = declaration.resumo_patrimonio

        # Should have non-zero totals
        assert resumo.total_bens_anterior > 0 or resumo.total_bens_atual > 0

    def test_invalid_file_raises(self, tmp_path: Path):
        """Test that invalid file raises appropriate error."""
        from irpf_analyzer.shared.exceptions import CorruptedFileError

        invalid_file = tmp_path / "invalid.dec"
        invalid_file.write_text("This is not a valid DEC file")

        with pytest.raises(CorruptedFileError):
            parse_dec_file(invalid_file)

    def test_empty_file_raises(self, tmp_path: Path):
        """Test that empty file raises appropriate error."""
        from irpf_analyzer.shared.exceptions import CorruptedFileError

        empty_file = tmp_path / "empty.dec"
        empty_file.write_text("")

        with pytest.raises(CorruptedFileError):
            parse_dec_file(empty_file)


class TestDBKParser:
    """Tests for DBKParser class."""

    @pytest.fixture
    def real_dbk_path(self) -> Path:
        """Path to real DBK file for testing."""
        return Path(__file__).parent.parent / "fixtures" / "83158073072-IRPF-A-2025-2024-ORIGI.DBK"

    def test_parse_real_dbk_file(self, real_dbk_path: Path):
        """Test parsing real DBK file."""
        if not real_dbk_path.exists():
            pytest.skip("Real DBK file not available")

        declaration = parse_dbk_file(real_dbk_path)

        # Basic info should match DEC file
        assert declaration.ano_exercicio == 2025
        assert declaration.ano_calendario == 2024
        assert declaration.contribuinte.nome == "MARCOS D AVILA GABBARDO"
        assert declaration.contribuinte.cpf == "83158073072"
        assert declaration.tipo_declaracao == TipoDeclaracao.COMPLETA

        # DBK files should not have receipt number
        assert declaration.numero_recibo is None

    def test_dbk_has_same_data_as_dec(self, real_dbk_path: Path):
        """Test that DBK file has same core data as DEC file."""
        dec_path = real_dbk_path.with_suffix(".DEC")

        if not real_dbk_path.exists() or not dec_path.exists():
            pytest.skip("Real DBK/DEC files not available")

        dbk_decl = parse_dbk_file(real_dbk_path)
        dec_decl = parse_dec_file(dec_path)

        # Core data should match
        assert dbk_decl.contribuinte.cpf == dec_decl.contribuinte.cpf
        assert dbk_decl.contribuinte.nome == dec_decl.contribuinte.nome
        assert dbk_decl.ano_exercicio == dec_decl.ano_exercicio
        assert dbk_decl.total_rendimentos_tributaveis == dec_decl.total_rendimentos_tributaveis
        assert len(dbk_decl.dependentes) == len(dec_decl.dependentes)
        assert len(dbk_decl.deducoes) == len(dec_decl.deducoes)


class TestUnifiedParser:
    """Tests for unified parse_file function."""

    @pytest.fixture
    def dec_path(self) -> Path:
        return Path(__file__).parent.parent / "fixtures" / "83158073072-IRPF-A-2025-2024-ORIGI.DEC"

    @pytest.fixture
    def dbk_path(self) -> Path:
        return Path(__file__).parent.parent / "fixtures" / "83158073072-IRPF-A-2025-2024-ORIGI.DBK"

    def test_detect_dec_file(self, dec_path: Path):
        """Test DEC file type detection."""
        if not dec_path.exists():
            pytest.skip("DEC file not available")

        file_type = detect_file_type(dec_path)
        assert file_type == FileType.DEC

    def test_detect_dbk_file(self, dbk_path: Path):
        """Test DBK file type detection."""
        if not dbk_path.exists():
            pytest.skip("DBK file not available")

        file_type = detect_file_type(dbk_path)
        assert file_type == FileType.DBK

    def test_parse_file_dec(self, dec_path: Path):
        """Test parse_file with DEC file."""
        if not dec_path.exists():
            pytest.skip("DEC file not available")

        declaration = parse_file(dec_path)
        assert declaration.contribuinte.cpf == "83158073072"

    def test_parse_file_dbk(self, dbk_path: Path):
        """Test parse_file with DBK file."""
        if not dbk_path.exists():
            pytest.skip("DBK file not available")

        declaration = parse_file(dbk_path)
        assert declaration.contribuinte.cpf == "83158073072"
        assert declaration.numero_recibo is None

    def test_unsupported_file_raises(self, tmp_path: Path):
        """Test that unsupported file extension raises error."""
        from irpf_analyzer.shared.exceptions import UnsupportedFileError

        unsupported_file = tmp_path / "test.txt"
        unsupported_file.write_text("test")

        with pytest.raises(UnsupportedFileError):
            parse_file(unsupported_file)
