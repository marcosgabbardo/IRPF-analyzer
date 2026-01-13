"""Custom exceptions for IRPF Analyzer."""


class IRPFAnalyzerError(Exception):
    """Base exception for all IRPF Analyzer errors."""

    pass


class ParseError(IRPFAnalyzerError):
    """Error parsing declaration file."""

    pass


class UnsupportedFileError(ParseError):
    """File format not supported."""

    pass


class CorruptedFileError(ParseError):
    """File is corrupted or incomplete."""

    pass


class UnsupportedVersionError(ParseError):
    """Declaration version/year not supported."""

    pass


class ValidationError(IRPFAnalyzerError):
    """Data validation error."""

    pass


class CPFValidationError(ValidationError):
    """Invalid CPF."""

    pass


class CNPJValidationError(ValidationError):
    """Invalid CNPJ."""

    pass


class AnalysisError(IRPFAnalyzerError):
    """Error during analysis."""

    pass


class ReportGenerationError(IRPFAnalyzerError):
    """Error generating report."""

    pass
