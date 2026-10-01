# ═══════════════════════════════════════════════════════════════════
# format_utils.py — PKR lakh grouping, dates, phone number formatting
# ═══════════════════════════════════════════════════════════════════
# All format strings come from constants/locales.py; nothing is hard-coded here.
# IMP: lakh grouping (12,34,567) differs from Western (1,234,567) — the
#      rightmost group is 3 digits, then groups of 2 from right to left.
###==============================================================
import sys
from datetime import date, datetime
from typing import Union

from hackdata.constants import locales
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


def group_lakh(n: int) -> str:
    """Format an integer with Indian/Pakistani lakh grouping.

    E.g. 1234567 → "12,34,567"  (rightmost 3 digits, then groups of 2)

    Parameters
    ----------
    n : int
        Non-negative integer to format.

    Returns
    -------
    str
        Grouped string representation.

    # DRY RUN: group_lakh(1234567)
    #   s = "1234567"
    #   right = "567"               ← last 3 digits
    #   rest = "1234"               ← remaining digits
    #   pairs from right: ["34", "12"]
    #   result = "12,34,567"
    """
    try:
        s = str(abs(n))
        # Rightmost 3 digits form the first (rightmost) group
        right = s[-3:]
        rest = s[:-3]
        if not rest:
            result = right
        else:
            # Split `rest` into groups of 2 from right to left
            pairs = []
            while rest:
                pairs.append(rest[-2:])
                rest = rest[:-2]
            result = ",".join(reversed(pairs)) + "," + right
        return ("-" if n < 0 else "") + result
    except Exception as e:
        raise HackDataException(e, sys)


def format_money(minor: int, currency: str = "PKR", grouping: str = "lakh") -> str:
    """Format a minor-unit amount as a human-readable currency string.

    Parameters
    ----------
    minor : int
        Amount in minor units (paisas / cents).
    currency : str
        ISO currency code; looked up in LOC_CURRENCY_SYMBOLS.
    grouping : str
        "lakh" for Pakistani grouping or "western" for standard.

    Returns
    -------
    str
        E.g. "Rs 12,34,567.89"
    """
    try:
        symbol = locales.LOC_CURRENCY_SYMBOLS.get(currency, currency)
        # Convert minor units to major units (2 decimal places)
        major = minor / 100
        integer_part = int(abs(major))
        fraction = round(abs(major) - integer_part, 2)
        frac_str = f"{fraction:.2f}"[1:]  # ".XX"

        if grouping == locales.LOC_GROUPING_LAKH:
            grouped = group_lakh(integer_part)
        else:
            # Western grouping: standard comma every 3 digits
            grouped = f"{integer_part:,}"

        sign = "-" if minor < 0 else ""
        return f"{sign}{symbol} {grouped}{frac_str}"
    except Exception as e:
        raise HackDataException(e, sys)


def format_date(
    d: Union[date, datetime, str],
    locale: str = "en_PK",
    context: str = "export",
) -> str:
    """Format a date according to locale and context.

    Parameters
    ----------
    d : date | datetime | str
        The date to format. Strings are returned as-is (already formatted).
    locale : str
        Locale code; currently only affects which format constant is used.
    context : str
        "export" → LOC_EXPORT_DATE_FORMAT ("%Y-%m-%d")
        anything else → LOC_DOC_DATE_FORMAT ("%d/%m/%Y")

    Returns
    -------
    str
        Formatted date string.
    """
    try:
        if isinstance(d, str):
            return d  # already formatted upstream
        fmt = (
            locales.LOC_EXPORT_DATE_FORMAT
            if context == "export"
            else locales.LOC_DOC_DATE_FORMAT
        )
        return d.strftime(fmt)
    except Exception as e:
        raise HackDataException(e, sys)


def format_phone(locale: str, parts: dict) -> str:
    """Format a phone number from component parts using the locale template.

    Parameters
    ----------
    locale : str
        Locale code (currently only "en_PK" is used; kept for future expansion).
    parts : dict
        Keyword arguments for LOC_MOBILE_TEMPLATE, e.g.
        {"operator": "0", "block1": "123", "block2": "4567"}.

    Returns
    -------
    str
        Formatted phone string, e.g. "+92 300 1234567".

    # IMP: the template tokens are defined in locales.LOC_MOBILE_TEMPLATE;
    #      callers must supply matching keys.
    """
    try:
        # ponytail: locale ignored beyond lookup; add per-locale templates when needed
        return locales.LOC_MOBILE_TEMPLATE.format(**parts)
    except Exception as e:
        raise HackDataException(e, sys)
