# ═══════════════════════════════════════════════════════════════════
# exception.py — one custom exception for the whole project
# ═══════════════════════════════════════════════════════════════════
# Adds FILE NAME + LINE NUMBER to any error. Raise it everywhere
# instead of plain Exception.
# Usage:  raise HackDataException(e, sys)   inside every except block
###==============================================================
import sys
from hackdata.constants import messages


def error_message_detail(error: Exception, error_detail: sys) -> str:
    """Build a message that includes the source file and line number.

    Parameters
    ----------
    error : Exception
        The original exception.
    error_detail : sys
        The `sys` module — caller passes it so we can call exc_info().

    Returns
    -------
    str
        Formatted message with file, line and error text.

    # DRY RUN: error_detail.exc_info() returns (type, value, traceback)
    # exc_tb.tb_frame.f_code.co_filename → "/home/aizen/HackData_v2/hackdata/..."
    # exc_tb.tb_lineno → 42
    # result → "error occurred in python script [ ... ], line [ 42 ], message [ ... ]"
    """
    _, _, exc_tb = error_detail.exc_info()
    if exc_tb is None:
        # IMP: raised outside an except block (e.g., manual raise in tests)
        return messages.MSG_NO_TRACEBACK.format(error=error)
    return messages.MSG_ERROR_DETAIL.format(
        file=exc_tb.tb_frame.f_code.co_filename,
        line=exc_tb.tb_lineno,
        error=str(error),
    )


class HackDataException(Exception):
    """Project-wide exception that enriches any error with file and line info.

    Usage
    -----
        except Exception as e:
            raise HackDataException(e, sys)
    """

    def __init__(self, error_message: Exception, error_detail: sys):
        super().__init__(error_message)
        self.error_message: str = error_message_detail(error_message, error_detail)

    def __str__(self) -> str:
        return self.error_message
