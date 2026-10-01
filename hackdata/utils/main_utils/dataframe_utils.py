# ═══════════════════════════════════════════════════════════════════
# dataframe_utils.py — safe CSV reading, sampling, dtype helpers
# ═══════════════════════════════════════════════════════════════════
# IMP: read_csv_safely tries every (encoding, delimiter) combination
#      from constants before giving up — never hard-code "utf-8" or ",".
###==============================================================
import sys

import numpy as np
import pandas as pd

from hackdata.constants import data_mode
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


def read_csv_safely(path: str) -> pd.DataFrame:
    """Read a CSV file by trying multiple encodings and delimiters.

    Tries every combination of DM_ENCODINGS_TO_TRY × DM_DELIMITERS_TO_TRY
    until one succeeds (parse success rate > DM_PARSE_SUCCESS_RATIO).

    Parameters
    ----------
    path : str
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
        Parsed DataFrame on the first successful combination.

    Raises
    ------
    HackDataException
        If no encoding+delimiter combination succeeds.

    # DRY RUN: path = "data.csv" (latin-1, semicolon-delimited)
    #   try ("utf-8", ",")  → UnicodeDecodeError → skip
    #   try ("utf-8", ";")  → UnicodeDecodeError → skip
    #   try ("latin-1", ";") → success, 95% columns non-null → return df
    """
    try:
        logging.info(f"read_csv_safely: reading {path}")
        last_error: Exception = RuntimeError("No encoding/delimiter combination succeeded")
        for enc in data_mode.DM_ENCODINGS_TO_TRY:
            for delim in data_mode.DM_DELIMITERS_TO_TRY:
                try:
                    df = pd.read_csv(path, encoding=enc, sep=delim, low_memory=False)
                    # IMP: a wrong delimiter still parses but produces one-column junk;
                    #      check that at least DM_PARSE_SUCCESS_RATIO columns have data.
                    if df.shape[1] < 2:
                        continue
                    # Accept if median column non-null rate exceeds the threshold
                    non_null_rate = df.notna().mean().mean()
                    if non_null_rate >= data_mode.DM_PARSE_SUCCESS_RATIO:
                        logging.info(
                            f"read_csv_safely: success enc={enc} sep={repr(delim)} "
                            f"shape={df.shape}"
                        )
                        return df
                except (UnicodeDecodeError, pd.errors.ParserError) as exc:
                    last_error = exc
                    continue
        raise last_error
    except HackDataException:
        raise
    except Exception as e:
        raise HackDataException(e, sys)


def sample_rows(df: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Return a random sample of rows without replacement.

    Parameters
    ----------
    df : pd.DataFrame
        Source DataFrame (not mutated).
    n : int
        Desired number of rows; capped at len(df).
    rng : np.random.Generator
        A seeded Generator from make_rng() so sampling is reproducible.

    Returns
    -------
    pd.DataFrame
        A new DataFrame with min(n, len(df)) rows, reset index.
    """
    try:
        size = min(n, len(df))
        indices = rng.choice(len(df), size=size, replace=False)
        return df.iloc[indices].reset_index(drop=True)
    except Exception as e:
        raise HackDataException(e, sys)


def is_numeric_like(series: pd.Series) -> bool:
    """Return True if more than 90% of a series coerces cleanly to numeric.

    Parameters
    ----------
    series : pd.Series
        Any column from a DataFrame.

    Returns
    -------
    bool
        True when the series is predominantly numeric.
    """
    try:
        # IMP: errors='coerce' turns parse failures into NaN; we count the successes.
        return pd.to_numeric(series, errors="coerce").notna().mean() > data_mode.DM_PARSE_SUCCESS_RATIO
    except Exception as e:
        raise HackDataException(e, sys)
