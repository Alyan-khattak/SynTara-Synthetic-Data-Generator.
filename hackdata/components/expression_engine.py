# ═══════════════════════════════════════════════════════════════════
# expression_engine.py — safe per-row expression evaluator
# ═══════════════════════════════════════════════════════════════════
# Used by DataGenerator for "expr" columns: evaluates a string like
# "price * quantity" with a row dict as namespace.
#
# IMP: NEVER use eval() — simpleeval restricts to arithmetic and the
#      SPEC_EXPR_ALLOWED_FUNCTIONS whitelist, blocking __import__ and
#      all attribute access.
###==============================================================
import builtins
import sys

import pandas as pd
from simpleeval import SimpleEval, FeatureNotAvailable

from hackdata.constants import spec as spec_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


class ExpressionEngine:
    """Evaluate per-row derived column expressions safely via simpleeval.

    ExpressionEngine
      │ expr = "price * quantity"
      │ row  = {"price": 500, "quantity": 3}
      └─▶ 1500.0

    IMP: Never use eval(). simpleeval restricts to arithmetic plus
    the SPEC_EXPR_ALLOWED_FUNCTIONS whitelist (round, min, max, abs,
    int, float).  Attribute access and __import__ are blocked by
    simpleeval's FeatureNotAvailable.

    DRY RUN: expr="round(a * b, 0)", row={"a": 3.5, "b": 2.0}
        simpleeval evaluates 3.5 * 2.0 = 7.0, round(7.0, 0) = 8.0?
        Actually 3.5 * 2.0 = 7.0, round(7.0, 0) = 7.0
        Hmm — let's trace: round(3.5 * 2.0, 0) = round(7.0, 0) = 7.0
        The acceptance test uses round(a * b, 0) with a=3.5, b=2.0 → 7.0.
        (Python's round uses banker's rounding: round(3.5*2.0, 0) = 7.0)
    """

    def __init__(self):
        try:
            self._evaluator = SimpleEval()
            # Build whitelist from builtins — only SPEC_EXPR_ALLOWED_FUNCTIONS
            self._evaluator.functions = {
                name: getattr(builtins, name)
                for name in spec_const.SPEC_EXPR_ALLOWED_FUNCTIONS
                if hasattr(builtins, name)
            }
        except Exception as e:
            raise HackDataException(e, sys)

    def evaluate(self, expr: str, row: dict) -> float:
        """Evaluate expr with row values as the name namespace.

        Parameters
        ----------
        expr : str
            Arithmetic expression string, e.g. "price * qty * 1.18".
        row : dict
            Column name → value mapping for one row.

        Returns
        -------
        float
            Result of the expression.

        Raises
        ------
        HackDataException
            On FeatureNotAvailable (forbidden construct) or any eval error.
        """
        try:
            self._evaluator.names = row
            return float(self._evaluator.eval(expr))
        except FeatureNotAvailable as e:
            # IMP: simpleeval raises FeatureNotAvailable for __import__,
            #      attribute access, function calls not in whitelist, etc.
            raise HackDataException(ValueError(f"Forbidden expression: {e}"), sys)
        except Exception as e:
            raise HackDataException(e, sys)

    def evaluate_series(self, expr: str, df: pd.DataFrame) -> pd.Series:
        """Apply evaluate row-by-row over df.  Returns float Series.

        Parameters
        ----------
        expr : str
            Expression referencing df column names.
        df : pd.DataFrame
            Must not be mutated; each row's dict is passed to evaluate().

        Returns
        -------
        pd.Series
            Float series aligned with df.index.

        IMP: df is never mutated — row.to_dict() creates a copy each time.
        """
        try:
            logging.info(f"ExpressionEngine.evaluate_series: expr='{expr}' rows={len(df)}")
            return df.apply(lambda row: self.evaluate(expr, row.to_dict()), axis=1)
        except HackDataException:
            raise
        except Exception as e:
            raise HackDataException(e, sys)
