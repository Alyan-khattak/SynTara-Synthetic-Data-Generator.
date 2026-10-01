# ═══════════════════════════════════════════════════════════════════
# data_profiler.py — local column profiling and relationship analysis
# ═══════════════════════════════════════════════════════════════════
# Computes entirely locally with pandas/SciPy/scikit-learn.
# No row values or category values are ever sent outside this module.
# Called by the /api/runs/{run_id}/profile endpoint.
# ═══════════════════════════════════════════════════════════════════
import math
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import spearmanr

from hackdata.constants import data_mode as dm_const, messages as msg_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


# ── column-type inference ────────────────────────────────────────────────────

_DATE_KEYWORDS = ("date", "time", "created", "updated", "timestamp", "dt", "day", "month", "year")
_ID_KEYWORDS   = ("id", "key", "uuid", "guid", "code", "ref", "no", "num", "number")
_DATE_PATTERN  = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _infer_col_type(series: pd.Series, col_name: str) -> str:
    """Return one of: 'numeric', 'categorical', 'date', 'text', 'id-like'."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return "categorical"

    # Try numeric first
    numeric_vals = pd.to_numeric(non_null, errors="coerce")
    if numeric_vals.notna().mean() >= dm_const.DM_PARSE_SUCCESS_RATIO:
        # id-like: unique ratio above threshold for integer column
        if numeric_vals.dropna().apply(lambda x: x == int(x)).all():
            if non_null.nunique() / len(non_null) >= dm_const.DM_ID_UNIQUE_RATIO:
                return "id-like"
        return "numeric"

    # Try date by keyword or pattern
    col_lower = col_name.lower()
    if any(kw in col_lower for kw in _DATE_KEYWORDS):
        return "date"
    sample_str = non_null.astype(str).head(5)
    if sample_str.apply(lambda v: bool(_DATE_PATTERN.match(v))).all():
        return "date"

    # id-like by name keyword + high uniqueness
    if any(kw == col_lower or col_lower.endswith(f"_{kw}") for kw in _ID_KEYWORDS):
        if non_null.nunique() / len(non_null) >= dm_const.DM_ID_UNIQUE_RATIO:
            return "id-like"

    # text: long mean length
    mean_len = non_null.astype(str).str.len().mean()
    if mean_len >= dm_const.DM_FREE_TEXT_MIN_MEAN_LENGTH:
        return "text"

    return "categorical"


def _to_numeric_series(series: pd.Series, col_type: str) -> Optional[pd.Series]:
    """Convert a column to numeric for correlation; None if not possible."""
    if col_type == "numeric":
        return pd.to_numeric(series, errors="coerce")
    if col_type == "date":
        try:
            return pd.to_datetime(series, errors="coerce").astype(np.int64) // 10**9
        except Exception:
            return None
    return None


# ── per-column statistics ────────────────────────────────────────────────────

def _profile_column(series: pd.Series, col_name: str) -> Dict[str, Any]:
    """Return a dict of per-column statistics."""
    n_total = len(series)
    n_missing = int(series.isna().sum())
    n_unique = int(series.nunique(dropna=True))
    col_type = _infer_col_type(series, col_name)

    profile: Dict[str, Any] = {
        "name": col_name,
        "type": col_type,
        "missing_pct": round(n_missing / n_total * 100, 2) if n_total else 0.0,
        "n_unique": n_unique,
        "is_constant": n_unique <= 1,
        "is_id_like": col_type == "id-like",
        "high_cardinality": False,
    }

    non_null = series.dropna()

    if col_type == "numeric":
        vals = pd.to_numeric(non_null, errors="coerce").dropna()
        if len(vals):
            q1, q3 = vals.quantile(0.25), vals.quantile(0.75)
            iqr = q3 - q1
            outlier_mask = (vals < q1 - 1.5 * iqr) | (vals > q3 + 1.5 * iqr)
            profile.update({
                "min": round(float(vals.min()), 4),
                "max": round(float(vals.max()), 4),
                "mean": round(float(vals.mean()), 4),
                "median": round(float(vals.median()), 4),
                "std": round(float(vals.std()), 4),
                "skew": round(float(vals.skew()), 4),
                "outlier_pct": round(float(outlier_mask.mean()) * 100, 2),
            })

    elif col_type in ("categorical", "id-like", "text"):
        vc = non_null.value_counts()
        total_non_null = len(non_null)
        n_show = min(dm_const.DM_TOP_CATEGORIES, len(vc))
        profile["top_categories"] = [
            {"value": str(k), "count": int(v)}
            for k, v in vc.head(n_show).items()
        ]
        # high cardinality: more distinct values than the categorical threshold
        cat_threshold = max(
            dm_const.DM_CATEGORICAL_MAX_DISTINCT_FLOOR,
            int(total_non_null * dm_const.DM_CATEGORICAL_MAX_DISTINCT_FRACTION),
        )
        profile["high_cardinality"] = n_unique > cat_threshold

    elif col_type == "date":
        parsed = pd.to_datetime(non_null, errors="coerce").dropna()
        if len(parsed):
            profile["date_min"] = str(parsed.min().date())
            profile["date_max"] = str(parsed.max().date())

    return profile


# ── pairwise relationship measures ──────────────────────────────────────────

def _pearson(a: pd.Series, b: pd.Series) -> Optional[float]:
    pair = pd.concat([a, b], axis=1).dropna()
    if len(pair) < 3:
        return None
    r, _ = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
    return round(float(r), 4)


def _spearman(a: pd.Series, b: pd.Series) -> Optional[float]:
    pair = pd.concat([a, b], axis=1).dropna()
    if len(pair) < 3:
        return None
    r, _ = spearmanr(pair.iloc[:, 0], pair.iloc[:, 1])
    return round(float(r), 4)


def _cramers_v(a: pd.Series, b: pd.Series) -> Optional[float]:
    """Cramér's V for two categorical columns via scipy.stats.contingency.association."""
    pair = pd.concat([a.astype(str), b.astype(str)], axis=1).dropna()
    if len(pair) < 3:
        return None
    ct = pd.crosstab(pair.iloc[:, 0], pair.iloc[:, 1])
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return None
    try:
        from scipy.stats.contingency import association
        v = association(ct.values, method="cramer")
        return round(float(v), 4)
    except Exception:
        return None


def _eta_squared(numeric: pd.Series, categorical: pd.Series) -> Optional[float]:
    """Correlation ratio (η²): variance of group means / total variance.

    No scipy/sklearn function exists for this exact measure, so implemented here.
    η² = Σ_g n_g * (ȳ_g - ȳ)² / Σ_i (y_i - ȳ)²
    Range [0, 1]; 0 = no relationship, 1 = perfect.
    """
    pair = pd.concat([numeric, categorical.astype(str)], axis=1).dropna()
    if len(pair) < 3:
        return None
    y = pd.to_numeric(pair.iloc[:, 0], errors="coerce").dropna()
    if y.std() == 0:
        return None
    pair = pair.loc[y.index]
    g = pair.iloc[:, 1]
    grand_mean = y.mean()
    ss_between = 0.0
    for cat in g.unique():
        group_y = y[g == cat]
        if len(group_y) > 0:
            ss_between += len(group_y) * (group_y.mean() - grand_mean) ** 2
    ss_total = ((y - grand_mean) ** 2).sum()
    if ss_total == 0:
        return None
    return round(float(ss_between / ss_total), 4)


def _relationship(
    col_a: str, col_b: str, types: Dict[str, str], df: pd.DataFrame
) -> Dict[str, Any]:
    """Compute relationship stats between two columns. Returns a dict."""
    ta, tb = types[col_a], types[col_b]
    a, b = df[col_a], df[col_b]

    num_types = {"numeric", "date"}
    cat_types = {"categorical", "id-like", "text"}

    a_is_num = ta in num_types
    b_is_num = tb in num_types

    result: Dict[str, Any] = {"col_a": col_a, "col_b": col_b, "measure": None, "value": None}

    if a_is_num and b_is_num:
        # Convert dates to unix seconds for numeric comparison
        an = _to_numeric_series(a, ta) if ta == "date" else pd.to_numeric(a, errors="coerce")
        bn = _to_numeric_series(b, tb) if tb == "date" else pd.to_numeric(b, errors="coerce")
        p = _pearson(an, bn)
        s = _spearman(an, bn)
        result.update({"measure": "pearson+spearman", "pearson": p, "spearman": s,
                        "value": s if s is not None else p})

    elif not a_is_num and not b_is_num:
        v = _cramers_v(a, b)
        result.update({"measure": "cramers_v", "value": v})

    else:
        # one numeric, one categorical
        num_s = (pd.to_numeric(a, errors="coerce") if a_is_num
                 else pd.to_numeric(b, errors="coerce"))
        cat_s = b if a_is_num else a
        eta = _eta_squared(num_s, cat_s)
        result.update({"measure": "eta_squared", "value": eta})

    return result


# ── plain-language findings ──────────────────────────────────────────────────

_STRENGTH = [(0.7, "strongly"), (0.4, "moderately"), (0.2, "weakly")]


def _strength_word(v: float) -> str:
    for threshold, word in _STRENGTH:
        if abs(v) >= threshold:
            return word
    return "very weakly"


def _generate_findings(
    profiles: List[Dict],
    relationships: List[Dict],
    duplicate_rows: int,
    n_rows: int,
) -> List[str]:
    """Template-based plain-language findings (no LLM)."""
    findings: List[str] = []

    # Strongest relationships first
    scored = [
        (abs(r["value"]), r)
        for r in relationships
        if r.get("value") is not None
    ]
    scored.sort(key=lambda t: t[0], reverse=True)

    for abs_val, r in scored[: dm_const.DM_MAX_FINDINGS]:
        sw = _strength_word(abs_val)
        measure = r["measure"]
        val = r["value"]
        ca, cb = r["col_a"], r["col_b"]
        if measure == "pearson+spearman":
            findings.append(
                f"'{ca}' and '{cb}' are {sw} correlated (Spearman {val:+.2f})."
            )
        elif measure == "cramers_v":
            findings.append(
                f"'{ca}' and '{cb}' have a {sw} categorical association (Cramér's V {val:.2f})."
            )
        elif measure == "eta_squared":
            findings.append(
                f"'{ca}' varies {sw} across groups of '{cb}' (η² = {val:.2f})."
            )

    # Structural flags
    for p in profiles:
        if p.get("is_id_like"):
            findings.append(f"'{p['name']}' looks like a primary key (high uniqueness).")
        if p.get("is_constant"):
            findings.append(f"'{p['name']}' is constant — all values are the same.")
        missing = p.get("missing_pct", 0)
        if missing > 20:
            findings.append(f"'{p['name']}' has {missing:.0f}% missing values.")

    if duplicate_rows > 0:
        findings.append(
            f"{duplicate_rows} duplicate rows detected ({duplicate_rows/n_rows*100:.1f}% of data)."
        )

    return findings[: dm_const.DM_MAX_FINDINGS]


# ── relationship matrix (for heatmap) ───────────────────────────────────────

def _build_relationship_matrix(
    cols: List[str], types: Dict[str, str], df: pd.DataFrame
) -> Tuple[List[List[Optional[float]]], List[str], List[Dict]]:
    """Return (matrix, col_names, all_relationships).

    matrix[i][j] = absolute relationship strength (0-1) or None.
    Diagonal is 1.0. Skips constant columns and capped columns.
    """
    n = len(cols)
    matrix: List[List[Optional[float]]] = [[None] * n for _ in range(n)]
    all_rels: List[Dict] = []

    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            r = _relationship(cols[i], cols[j], types, df)
            all_rels.append(r)
            v = abs(r["value"]) if r.get("value") is not None else None
            matrix[i][j] = v
            matrix[j][i] = v

    return matrix, cols, all_rels


# ── public API ───────────────────────────────────────────────────────────────

def profile_dataframe(df: pd.DataFrame, label: str = "original") -> Dict[str, Any]:
    """Compute full profile of a DataFrame.

    Parameters
    ----------
    df    : DataFrame to profile (uploaded original or synthetic)
    label : 'original' or 'synthetic' — included in the response

    Returns
    -------
    dict with keys: label, n_rows, n_cols, duplicate_rows, profiles,
                    columns, col_types, matrix, relationships, findings,
                    matrix_capped (bool), matrix_note (str or None)
    """
    try:
        n_rows, n_cols = df.shape
        duplicate_rows = int(df.duplicated().sum())

        # Per-column profiles
        profiles = [_profile_column(df[c], c) for c in df.columns]
        col_types = {p["name"]: p["type"] for p in profiles}

        # Cap columns for heatmap to avoid quadratic blowup
        all_cols = list(df.columns)
        capped = len(all_cols) > dm_const.DM_MAX_PROFILE_COLS
        heatmap_cols = all_cols[: dm_const.DM_MAX_PROFILE_COLS]

        # Skip constant columns from relationship matrix (they carry no info)
        constant_names = {p["name"] for p in profiles if p.get("is_constant")}
        rel_cols = [c for c in heatmap_cols if c not in constant_names]

        matrix: List[List[Optional[float]]] = []
        relationships: List[Dict] = []
        if len(rel_cols) >= 2:
            matrix, _, relationships = _build_relationship_matrix(
                rel_cols, col_types, df[rel_cols]
            )

        findings = _generate_findings(profiles, relationships, duplicate_rows, n_rows)

        matrix_note = None
        if capped:
            matrix_note = msg_const.MSG_DM_PROFILE_COLS_CAPPED.format(
                cap=dm_const.DM_MAX_PROFILE_COLS, total=n_cols
            )

        return {
            "label": label,
            "n_rows": n_rows,
            "n_cols": n_cols,
            "duplicate_rows": duplicate_rows,
            "profiles": profiles,
            "columns": rel_cols,
            "col_types": col_types,
            "matrix": matrix,
            "relationships": relationships,
            "findings": findings,
            "matrix_capped": capped,
            "matrix_note": matrix_note,
        }

    except Exception as e:
        raise HackDataException(e, sys)
