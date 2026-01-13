"""Value formatters for display."""

from decimal import Decimal


def format_currency(value: Decimal, symbol: str = "R$") -> str:
    """
    Format decimal as Brazilian currency.

    Args:
        value: Decimal value to format
        symbol: Currency symbol (default: R$)

    Returns:
        Formatted string like "R$ 1.234,56"
    """
    # Handle negative values
    negative = value < 0
    value = abs(value)

    # Format with 2 decimal places
    formatted = f"{value:,.2f}"

    # Convert to Brazilian format (. for thousands, , for decimals)
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    result = f"{symbol} {formatted}"
    return f"-{result}" if negative else result


def format_percentage(value: Decimal, decimals: int = 1) -> str:
    """
    Format decimal as percentage.

    Args:
        value: Decimal value (e.g., 15.5 for 15.5%)
        decimals: Number of decimal places

    Returns:
        Formatted string like "15,5%"
    """
    formatted = f"{value:.{decimals}f}".replace(".", ",")
    return f"{formatted}%"


def format_variation(value: Decimal, show_sign: bool = True) -> str:
    """
    Format variation value with sign indicator.

    Args:
        value: Decimal variation value
        show_sign: Whether to show + for positive values

    Returns:
        Formatted string like "+15,5%" or "-3,2%"
    """
    sign = ""
    if show_sign and value > 0:
        sign = "+"
    elif value < 0:
        sign = ""  # Minus sign already included

    formatted = f"{value:.1f}".replace(".", ",")
    return f"{sign}{formatted}%"
