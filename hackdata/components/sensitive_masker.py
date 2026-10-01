# ═══════════════════════════════════════════════════════════════════
# sensitive_masker.py — detect and mask sensitive columns in upload mode
# ═══════════════════════════════════════════════════════════════════
# Used by DataModePipeline after synthetic sampling: any column whose
# name matches a sensitive pattern is replaced with GEN_MASK_CHAR × 8
# before the result reaches the user.
#
# IMP: operates on column NAMES only — no row values are inspected or
#      sent anywhere. This is intentional and tested.
###==============================================================
import sys
from typing import List, Tuple

import pandas as pd

from hackdata.constants import generation as gen_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


def detect_and_mask(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Replace sensitive columns with a fixed mask string.

    A column is sensitive when its lowercased name contains any substring
    from GEN_SENSITIVE_COL_PATTERNS (e.g. "email", "card", "national_id").

    Parameters
    ----------
    df : pd.DataFrame
        Synthetic output DataFrame to inspect.

    Returns
    -------
    (masked_df, masked_col_names)
        masked_df         : copy of df with sensitive columns replaced by
                            GEN_MASK_CHAR repeated 8 times.
        masked_col_names  : list of column names that were masked; empty when
                            no sensitive columns were detected.

    # DRY RUN: df has columns ["order_id", "email", "amount"]
    #   "email" contains pattern "email" → masked to "********"
    #   → returns df with email="********", masked_col_names=["email"]
    """
    try:
        result = df.copy()
        masked: List[str] = []
        mask_value = gen_const.GEN_MASK_CHAR * 8   # fixed-width, not data-length

        for col in df.columns:
            col_lower = col.lower()
            if any(pattern in col_lower for pattern in gen_const.GEN_SENSITIVE_COL_PATTERNS):
                result[col] = mask_value
                masked.append(col)

        if masked:
            logging.info(
                "sensitive_masker.detect_and_mask: masked columns "  # noqa: hardcode
                f"{masked}"
            )
        return result, masked

    except Exception as e:
        raise HackDataException(e, sys)
