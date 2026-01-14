"""Data validators for IRPF Analyzer."""

import re


def validate_cpf(cpf: str) -> bool:
    """
    Validate Brazilian CPF number.

    Args:
        cpf: CPF string (can contain formatting characters)

    Returns:
        True if valid, False otherwise
    """
    # Remove non-digits
    cpf = re.sub(r"\D", "", cpf)

    # Check length
    if len(cpf) != 11:
        return False

    # Check for known invalid patterns (all same digits)
    if cpf == cpf[0] * 11:
        return False

    # Calculate first check digit
    sum1 = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digit1 = (sum1 * 10 % 11) % 10

    if digit1 != int(cpf[9]):
        return False

    # Calculate second check digit
    sum2 = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digit2 = (sum2 * 10 % 11) % 10

    return digit2 == int(cpf[10])


def validate_cnpj(cnpj: str) -> bool:
    """
    Validate Brazilian CNPJ number.

    Args:
        cnpj: CNPJ string (can contain formatting characters)

    Returns:
        True if valid, False otherwise
    """
    # Remove non-digits
    cnpj = re.sub(r"\D", "", cnpj)

    # Check length
    if len(cnpj) != 14:
        return False

    # Check for known invalid patterns
    if cnpj == cnpj[0] * 14:
        return False

    # Calculate first check digit
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum1 = sum(int(cnpj[i]) * weights1[i] for i in range(12))
    digit1 = 11 - (sum1 % 11)
    digit1 = 0 if digit1 >= 10 else digit1

    if digit1 != int(cnpj[12]):
        return False

    # Calculate second check digit
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum2 = sum(int(cnpj[i]) * weights2[i] for i in range(13))
    digit2 = 11 - (sum2 % 11)
    digit2 = 0 if digit2 >= 10 else digit2

    return digit2 == int(cnpj[13])


def format_cpf(cpf: str) -> str:
    """Format CPF as XXX.XXX.XXX-XX."""
    cpf = re.sub(r"\D", "", cpf)
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def format_cnpj(cnpj: str) -> str:
    """Format CNPJ as XX.XXX.XXX/XXXX-XX."""
    cnpj = re.sub(r"\D", "", cnpj)
    if len(cnpj) != 14:
        return cnpj
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def mask_cpf(cpf: str) -> str:
    """Mask CPF for display as ***.***.**X-XX."""
    cpf = re.sub(r"\D", "", cpf)
    if len(cpf) != 11:
        return "***.***.***-**"
    return f"***.***.**{cpf[8]}-{cpf[9:]}"


# === Extended validation functions with error messages ===


def validar_cpf(cpf: str) -> tuple[bool, str]:
    """Validate CPF and return reason if invalid.

    Uses módulo 11 algorithm for check digit calculation.
    100% local - no external API calls.

    Args:
        cpf: CPF string (can contain formatting characters)

    Returns:
        (True, "") if valid
        (False, "reason") if invalid
    """
    # Remove formatting
    cpf = re.sub(r"\D", "", cpf)

    if len(cpf) != 11:
        return False, f"CPF deve ter 11 dígitos, tem {len(cpf)}"

    # Reject CPFs with all same digits
    if cpf == cpf[0] * 11:
        return False, "CPF com todos dígitos iguais é inválido"

    # Calculate first check digit
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto

    if int(cpf[9]) != digito1:
        return False, f"Primeiro dígito verificador inválido (esperado {digito1})"

    # Calculate second check digit
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto

    if int(cpf[10]) != digito2:
        return False, f"Segundo dígito verificador inválido (esperado {digito2})"

    return True, ""


def validar_cnpj(cnpj: str) -> tuple[bool, str]:
    """Validate CNPJ and return reason if invalid.

    Uses módulo 11 algorithm for check digit calculation.
    100% local - no external API calls.

    Multipliers:
    - 1st digit: 5,4,3,2,9,8,7,6,5,4,3,2 (positions 0-11)
    - 2nd digit: 6,5,4,3,2,9,8,7,6,5,4,3,2 (positions 0-12)

    Args:
        cnpj: CNPJ string (can contain formatting characters)

    Returns:
        (True, "") if valid
        (False, "reason") if invalid
    """
    # Remove formatting
    cnpj = re.sub(r"\D", "", cnpj)

    if len(cnpj) != 14:
        return False, f"CNPJ deve ter 14 dígitos, tem {len(cnpj)}"

    # Reject CNPJs with all same digits
    if cnpj == cnpj[0] * 14:
        return False, "CNPJ com todos dígitos iguais é inválido"

    # Multipliers for 1st digit
    mult1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * mult1[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto

    if int(cnpj[12]) != digito1:
        return False, f"Primeiro dígito verificador inválido (esperado {digito1})"

    # Multipliers for 2nd digit
    mult2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * mult2[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto

    if int(cnpj[13]) != digito2:
        return False, f"Segundo dígito verificador inválido (esperado {digito2})"

    return True, ""
