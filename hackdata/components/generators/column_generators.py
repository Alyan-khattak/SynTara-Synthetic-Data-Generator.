# ═══════════════════════════════════════════════════════════════════
# column_generators.py — one generator function per spec "gen" type
# ═══════════════════════════════════════════════════════════════════
# Each gen_<type> produces a pd.Series of n rows from col_spec params.
# The caller (DataGenerator) creates the rng via make_rng(master, table, col)
# and passes it in, so every draw is deterministic and non-global.
#
# IMP: NO np.random.* global calls.  Every draw uses the passed rng.
# IMP: Never mutate existing_cols entries — they belong to the caller.
###==============================================================
import sys
import uuid as _uuid
from datetime import date as _date, timedelta as _timedelta

import numpy as np
import pandas as pd
from faker import Faker

from hackdata.constants import locales as loc_const
from hackdata.constants import spec as spec_const
from hackdata.constants import generation as gen_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.seed_utils import make_rng


# ─────────────────────────── helpers ────────────────────────────

def _seed_faker(rng: np.random.Generator, locale: str = "en") -> Faker:
    """Build a Faker instance seeded deterministically from the column rng.

    IMP: Faker's seed_instance() takes an integer; we pull one from rng so
    faker output is reproducible without using global Faker.seed().
    Falls back to "en" if locale not supported by Faker.
    """
    try:
        fake = Faker(locale)
    except Exception:
        fake = Faker("en")
    fake.seed_instance(int(rng.integers(0, 2 ** 31)))
    return fake


# ──────────────────────── generator functions ───────────────────

def gen_sequence(n: int, col_spec: dict, rng: np.random.Generator = None, **kw) -> pd.Series:
    """Return 1, 2, 3, …, n.  No randomness needed.

    DRY RUN: n=5 → [1, 2, 3, 4, 5]
    """
    return pd.Series(range(1, n + 1), dtype=int)


def gen_uuid(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n UUID4 strings.

    IMP: uuid4 uses OS entropy internally; rng is accepted for a uniform
    interface but not used directly (UUIDs are already unique by design).
    """
    return pd.Series([str(_uuid.uuid4()) for _ in range(n)])


def gen_int_range(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n integers in [min, max].

    Distributions
    -------------
    uniform (default) : rng.integers(min, max+1, n)
    normal            : clipped normal centred at midpoint, std = (max-min)/6

    DRY RUN: n=5, min=1, max=10, dist="uniform"
        rng.integers(1, 11, 5) → e.g. [3, 7, 2, 8, 5]
    """
    lo = int(col_spec["min"]) if col_spec.get("min") is not None else 1
    hi = int(col_spec["max"]) if col_spec.get("max") is not None else 1000
    dist = col_spec.get("dist", "uniform")

    if dist == "normal":
        mid = (lo + hi) / 2.0
        # IMP: sigma = range/6 so ±3σ covers ~all the range
        sigma = max((hi - lo) / 6.0, 1e-9)
        raw = rng.normal(mid, sigma, n)
        values = np.clip(np.round(raw), lo, hi).astype(int)
    else:
        # uniform — default and fallback
        values = rng.integers(lo, hi + 1, size=n)

    return pd.Series(values)


def gen_float_range(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n floats in [min, max].

    Distributions: uniform, normal, lognormal.
    All results are clipped to [min, max].
    """
    lo = float(col_spec["min"]) if col_spec.get("min") is not None else 1.0
    hi = float(col_spec["max"]) if col_spec.get("max") is not None else 1000.0
    dist = col_spec.get("dist", "uniform")

    if dist == "normal":
        mid = (lo + hi) / 2.0
        sigma = max((hi - lo) / 6.0, 1e-9)
        raw = rng.normal(mid, sigma, n)
    elif dist == "lognormal":
        # IMP: use log of midpoint as mu; sigma=0.5 is a reasonable spread.
        #      Result is then clipped so it stays inside [min, max].
        mid = max((lo + hi) / 2.0, 1e-9)
        raw = rng.lognormal(np.log(mid), 0.5, n)
    else:
        raw = rng.uniform(lo, hi, n)

    return pd.Series(np.clip(raw, lo, hi))


def gen_money(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n money values as integer minor units (paise).

    IMP: min/max in col_spec are already in minor units (e.g. 10000 = Rs 100).
    rng.integers keeps results as integers throughout — no float rounding.

    DRY RUN: min=100, max=50000 → Series of n ints in [100, 50000]
    """
    lo = int(col_spec["min"]) if col_spec.get("min") is not None else 100
    hi = int(col_spec["max"]) if col_spec.get("max") is not None else 100000
    if lo > hi:
        lo, hi = hi, lo
    return pd.Series(rng.integers(lo, hi + 1, size=n))


def gen_categorical(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n values sampled from col_spec["values"].

    col_spec["dist"] can be:
    - "uniform" (default) : equal probability for each value
    - dict {value: weight} : weighted sampling

    DRY RUN: values=["A","B","C"], dist="uniform"
        rng.choice(["A","B","C"], n, replace=True) → e.g. ["B","A","C","A","B"]
    """
    values = col_spec.get("values") or []
    if not values:
        # ponytail: LLM omitted values for categorical; fallback keeps generation running
        return pd.Series([f"category_{(i % 5) + 1}" for i in range(n)])
    dist = col_spec.get("dist", "uniform")

    if isinstance(dist, dict):
        # IMP: weights dict may not cover all values; default missing to 1.0
        weights = [float(dist.get(v, 1.0)) for v in values]
        total = sum(weights)
        probs = [w / total for w in weights]
        return pd.Series(rng.choice(values, size=n, replace=True, p=probs))

    return pd.Series(rng.choice(values, size=n, replace=True))


def gen_boolean(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n True/False values.

    col_spec["true_rate"] (default 0.5) controls the P(True).
    """
    true_rate = float(col_spec.get("true_rate", 0.5))
    return pd.Series(rng.random(n) < true_rate)


def gen_date_range(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n date strings (LOC_EXPORT_DATE_FORMAT) in [min, max].

    DRY RUN: min="2023-01-01", max="2023-12-31"
        min_ord = date(2023,1,1).toordinal() = 738521
        max_ord = date(2023,12,31).toordinal() = 738885
        rng.integers(738521, 738886, n) → n ordinals
        → n date strings like "2023-06-15"
    """
    raw_min = col_spec.get("min")
    raw_max = col_spec.get("max")
    # ponytail: LLM sometimes sends integer year (2020) or None — coerce both to ISO string
    def _to_iso(v, fallback: str) -> str:
        if v is None:
            return fallback
        if isinstance(v, (int, float)):
            return f"{int(v)}-01-01"
        return str(v)
    min_val = _to_iso(raw_min, "2020-01-01")
    max_val = _to_iso(raw_max, "2025-12-31")
    min_date = _date.fromisoformat(min_val)
    max_date = _date.fromisoformat(max_val)
    if min_date > max_date:
        min_date, max_date = max_date, min_date
    min_ord = min_date.toordinal()
    max_ord = max_date.toordinal()
    ordinals = rng.integers(min_ord, max_ord + 1, size=n)
    date_fmt = loc_const.LOC_EXPORT_DATE_FORMAT
    return pd.Series([_date.fromordinal(int(o)).strftime(date_fmt) for o in ordinals])


def gen_date_offset(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return dates offset from a reference column by [min_days, max_days].

    IMP: ref column must already exist in existing_cols kwarg (passed by
    generate_column → DataGenerator uses dependency-ordered generation).

    DRY RUN: ref="order_date", min_days=1, max_days=30
        ref_series = existing_cols["order_date"]  → ["2023-01-05", ...]
        offsets = rng.integers(1, 31, n)          → [5, 12, 3, ...]
        → each date + offset days                 → ["2023-01-10", ...]
    """
    existing_cols = kw.get("existing_cols", {})
    ref_name = col_spec.get("ref")
    ref_series = existing_cols.get(ref_name) if ref_name else None
    if ref_series is None:
        # ponytail: ref missing or not yet generated — fall back to plain date_range
        logging.warning(f"gen_date_offset: ref='{ref_name}' not found, falling back to date_range")
        return gen_date_range(n, col_spec, rng, **kw)
    min_days = int(col_spec.get("min_days", 0))
    max_days = int(col_spec.get("max_days", 30))
    offsets = rng.integers(min_days, max_days + 1, size=n)
    date_fmt = loc_const.LOC_EXPORT_DATE_FORMAT

    result = []
    for i, raw in enumerate(ref_series):
        try:
            base = _date.fromisoformat(str(raw))
            result.append((base + _timedelta(days=int(offsets[i]))).strftime(date_fmt))
        except Exception:
            result.append(None)
    return pd.Series(result)


def gen_id(n: int, col_spec: dict, rng: np.random.Generator = None, **kw) -> pd.Series:
    """Alias for gen_sequence — integer surrogate keys starting at 1."""
    return gen_sequence(n, col_spec, rng, **kw)


def gen_email(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n email addresses using example.com (RFC 2606 reserved domain).

    IMP: always uses @example.com — never a real registerable domain — so
    generated addresses cannot be confused with real ones or used to send mail.
    """
    fake = _seed_faker(rng, kw.get("locale", "en"))
    return pd.Series([fake.user_name() + "@example.com" for _ in range(n)])


def gen_phone(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n Pakistan mobile numbers in "+92 3XXXXXXXXXX" format.

    Uses LOC_MOBILE_TEMPLATE = "+92 3{operator}{block1} {block2}":
    - operator : 2 random digits (mobile network prefix, e.g. 00-99)
    - block1   : 4 random digits
    - block2   : 4 random digits
    Total: 10 digits after the leading "3".

    # VERIFY: range 030X–039X covers active Pakistani mobile prefixes;
    #         some 2-digit operator values (e.g. 04, 07) may be unallocated
    #         or map to specific operators. Validate against PSTN allocations
    #         if real-network accuracy is required.

    DRY RUN: rng draws 10 digits → [0,3,1,2,3,4,5,6,7,8]
        operator="03", block1="1234", block2="5678"
        → "+92 30312345 6789"
    """
    template = loc_const.LOC_MOBILE_TEMPLATE
    result = []
    for _ in range(n):
        # IMP: draw all 10 digits at once for vectorised speed at large n
        d = rng.integers(0, 10, size=loc_const.LOC_MOBILE_DIGIT_COUNT).tolist()
        operator = f"{d[0]}{d[1]}"
        block1 = f"{d[2]}{d[3]}{d[4]}{d[5]}"
        block2 = f"{d[6]}{d[7]}{d[8]}{d[9]}"
        result.append(template.format(operator=operator, block1=block1, block2=block2))
    return pd.Series(result)


def gen_text(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n short random sentences using Faker, seeded from rng."""
    fake = _seed_faker(rng, kw.get("locale", "en"))
    return pd.Series([fake.sentence() for _ in range(n)])


def gen_faker(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n values from a named Faker field (allowlist-checked).

    col_spec["faker_field"] must be in SPEC_FAKER_ALLOWLIST.
    IMP: allowlist prevents callers from calling arbitrary Faker methods.
    """
    faker_field = col_spec["faker_field"]
    if faker_field not in spec_const.SPEC_FAKER_ALLOWLIST:
        raise HackDataException(
            ValueError(
                f"gen_faker: '{faker_field}' is not in SPEC_FAKER_ALLOWLIST "
                f"({list(spec_const.SPEC_FAKER_ALLOWLIST)})"
            ),
            sys,
        )
    fake = _seed_faker(rng, kw.get("locale", "en"))
    return pd.Series([getattr(fake, faker_field)() for _ in range(n)])


def gen_national_id(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n Pakistani CNIC-style IDs matching LOC_NATIONAL_ID_PATTERN.

    Pattern "#####-#######-#" with each '#' replaced by a random digit.
    IMP: first digit is always LOC_NATIONAL_ID_FAKE_MARKER ("0") so these
    cannot collide with real CNICs (which never start with 0).

    By default output is masked: "*****-*******-X" where X is the check digit.
    Set col_spec["masked"] = False to get the full synthetic value.

    DRY RUN (masked=True): pattern="#####-#######-#", marker="0"
        digits=[0, 3,4,2,1, 9,8,7,6,5,4,3, 2]  (13 total, first=0)
        full  = "03421-9876543-2"
        masked= "*****-*******-2"
    """
    pattern = loc_const.LOC_NATIONAL_ID_PATTERN
    marker = int(loc_const.LOC_NATIONAL_ID_FAKE_MARKER)
    total_hashes = pattern.count("#")
    masked = col_spec.get("masked", True)

    result = []
    for _ in range(n):
        digits = rng.integers(0, 10, size=total_hashes).tolist()
        digits[0] = marker  # first digit always the fake marker
        d_iter = iter(digits)
        nid = "".join(str(next(d_iter)) if c == "#" else c for c in pattern)
        if masked:
            # Keep structure visible; reveal only the check digit (last segment)
            last_digit = nid.split("-")[-1]
            nid = "*****-*******-" + last_digit
        result.append(nid)
    return pd.Series(result)


def gen_pool(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Sample with replacement from a pre-fetched pool list.

    col_spec["values"] is filled by SpecBuilder from the LLM pool call.
    """
    values = col_spec.get("values") or []
    if not values:
        # ponytail: pool LLM call returned nothing; use faker catch_phrase as generic text fallback
        fake = _seed_faker(rng, kw.get("locale", "en"))
        return pd.Series([fake.catch_phrase() for _ in range(n)])
    return pd.Series(rng.choice(values, size=n, replace=True))


# ───── post-generation stubs (computed by DataGenerator after all cols) ─────

def gen_aggregate(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    # ponytail: stub — aggregate is computed post-generation in DataGenerator
    #           once all source columns exist; return None placeholder here.
    return pd.Series([None] * n)


def gen_conditional(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    # ponytail: stub — conditional segmented values are computed in
    #           components/generators/conditional.py after columns exist.
    return pd.Series([None] * n)


def gen_expr(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    # ponytail: stub — expressions are evaluated by ExpressionEngine
    #           in DataGenerator after all operand columns are available.
    return pd.Series([None] * n)


def gen_card(n: int, col_spec: dict, rng: np.random.Generator, **kw) -> pd.Series:
    """Return n masked payment card numbers drawn from the published test-card list.

    IMP: output is ALWAYS drawn from GEN_CARD_TEST_NUMBERS — a short list of
    processor test cards (Visa/MC/Amex/Discover) published by Stripe and Adyen.
    CVV and expiry are NEVER generated.
    Output is masked to "**** **** **** XXXX [TEST CARD]" where XXXX is the
    last 4 digits of the chosen test card, so the number cannot be used as-is.
    Set col_spec["masked"] = False to get the full test-card number (still a
    published test value, never a real card).

    DRY RUN (masked=True, n=2):
        rng.integers picks indices [0, 2]
        cards = ["4111111111111111", "378282246310005"]
        → ["**** **** **** 1111 [TEST CARD]", "**** **** **** 0005 [TEST CARD]"]
    """
    masked = col_spec.get("masked", True)
    cards = gen_const.GEN_CARD_TEST_NUMBERS
    suffix_len = gen_const.GEN_CARD_MASK_SUFFIX_LEN

    # IMP: draw indices within the test-card list; never invent card numbers.
    indices = rng.integers(0, len(cards), size=n)
    result = []
    for idx in indices:
        card = cards[int(idx)]
        if masked:
            suffix = card[-suffix_len:]
            result.append("**** **** **** " + suffix + " [TEST CARD]")
        else:
            # Full test-card number — still a published test value, not real.
            result.append(card + " [TEST CARD]")
    return pd.Series(result)


# ─────────────────────── dispatch map + public API ──────────────

GENERATOR_MAP: dict = {
    "sequence":    gen_sequence,
    "uuid":        gen_uuid,
    "int_range":   gen_int_range,
    "float_range": gen_float_range,
    "money":       gen_money,
    "categorical": gen_categorical,
    "boolean":     gen_boolean,
    "date_range":  gen_date_range,
    "date_offset": gen_date_offset,
    "id":          gen_id,
    "email":       gen_email,
    "phone":       gen_phone,
    "text":        gen_text,
    "faker":       gen_faker,
    "national_id": gen_national_id,
    "card":        gen_card,
    "pool":        gen_pool,
    "aggregate":   gen_aggregate,
    "conditional": gen_conditional,
    "expr":        gen_expr,
}


def generate_column(
    col_spec: dict,
    n: int,
    master_seed: int,
    table_name: str,
    existing_cols: dict = None,
    locale: str = "en",
) -> pd.Series:
    """Route col_spec to the right generator, seeding from master_seed.

    Parameters
    ----------
    col_spec : dict
        Column specification dict with at least {"name": ..., "gen": ...}.
    n : int
        Number of rows to generate.
    master_seed : int
        Run-level master seed; column rng is derived via make_rng.
    table_name : str
        Table name used as scope key for seed derivation.
    existing_cols : dict, optional
        Already-generated columns {col_name: pd.Series}, needed by
        ref-based generators (date_offset, conditional, expr, aggregate).

    Returns
    -------
    pd.Series
        Generated column values.

    DRY RUN: col_spec={"name":"price","gen":"int_range","min":100,"max":5000},
             n=1000, master_seed=42, table_name="orders"
        rng = make_rng(42, "orders", "price")   ← derive_seed → default_rng
        gen_int_range(1000, col_spec, rng)       → Series of 1000 ints in [100,5000]
    """
    try:
        logging.info(f"generate_column: table={table_name} col={col_spec.get('name')} gen={col_spec.get('gen')} n={n}")
        gen_type = col_spec.get("gen")
        if gen_type is None:
            raise ValueError("col_spec missing 'gen' key")

        fn = GENERATOR_MAP.get(gen_type)
        if fn is None:
            raise ValueError(f"Unknown generator type: '{gen_type}'")

        rng = make_rng(master_seed, table_name, col_spec["name"])
        existing = existing_cols or {}
        return fn(n, col_spec, rng, existing_cols=existing, locale=locale)
    except HackDataException:
        raise
    except Exception as e:
        raise HackDataException(e, sys)
