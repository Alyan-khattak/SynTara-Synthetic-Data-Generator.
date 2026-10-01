# ═══════════════════════════════════════════════════════════════════
# money_utils.py — minor-unit conversions and rounding
# ═══════════════════════════════════════════════════════════════════
# All monetary values inside the engine are stored as integer minor units
# (e.g. 123.45 PKR → 12345 paisas).  Convert only at export / render time.
# IMP: Python's built-in round() uses banker's rounding (ROUND_HALF_EVEN).
#      We use decimal.Decimal with ROUND_HALF_UP so 0.5 always rounds up,
#      matching GEN_ROUNDING_MODE = "half_up" in constants/generation.py.
###==============================================================
import math
import sys
from decimal import ROUND_HALF_UP, Decimal

from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


def round_half_up(value: float, decimals: int = 0) -> float:
    """Round a float to `decimals` decimal places using ROUND_HALF_UP.

    Parameters
    ----------
    value : float
        The value to round.
    decimals : int
        Number of decimal places (default 0 → round to integer).

    Returns
    -------
    float
        Rounded value as a Python float.

    # DRY RUN: round_half_up(2.5, 0) → 3.0  (not 2 as banker's rounding gives)
    #          round_half_up(123.456, 2) → 123.46
    """
    try:
        quant = Decimal("1") if decimals == 0 else Decimal(f"0.{'0' * decimals}")
        result = Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP)
        return float(result)
    except Exception as e:
        raise HackDataException(e, sys)


def to_minor_units(amount: float, decimals: int = 2) -> int:
    """Convert a decimal monetary amount to integer minor units.

    E.g. 123.456 with decimals=2 → 12346 (round_half_up applied).

    Parameters
    ----------
    amount : float
        Decimal amount (e.g. 123.45).
    decimals : int
        Number of minor-unit decimal places (2 for paisas/cents).

    Returns
    -------
    int
        Amount expressed in minor units.
    """
    try:
        return int(round_half_up(amount * (10 ** decimals), 0))
    except Exception as e:
        raise HackDataException(e, sys)


def from_minor_units(amount_minor: int, decimals: int = 2) -> float:
    """Convert integer minor units back to a decimal amount.

    Parameters
    ----------
    amount_minor : int
        Amount in minor units (e.g. 12346).
    decimals : int
        Number of minor-unit decimal places (2 for paisas/cents).

    Returns
    -------
    float
        Decimal amount (e.g. 123.46).
    """
    try:
        return round_half_up(amount_minor / (10 ** decimals), decimals)
    except Exception as e:
        raise HackDataException(e, sys)


def apply_rate(amount_minor: int, rate: float) -> int:
    """Apply a multiplicative rate to a minor-unit amount, flooring the result.

    Used for tax, discount and commission calculations.
    IMP: floor is intentional — never over-charge on a fractional paisa.

    Parameters
    ----------
    amount_minor : int
        Base amount in minor units.
    rate : float
        Multiplicative rate (e.g. 0.18 for 18% GST).

    Returns
    -------
    int
        Result in minor units, floored.
    """
    try:
        return math.floor(amount_minor * rate)
    except Exception as e:
        raise HackDataException(e, sys)
