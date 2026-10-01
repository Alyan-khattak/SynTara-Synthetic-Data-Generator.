# ═══════════════════════════════════════════════════════════════════
# canonical_io.py — deterministic CSV, JSON and SQL writers
# ═══════════════════════════════════════════════════════════════════
# IMP: "canonical" means the output is byte-for-byte identical for
#      the same logical data regardless of dict insertion order or
#      DataFrame column order.  This is required so SHA-256 checksums
#      remain reproducible across runs (TRD 8.4).
#
#   canonical = fixed column order (sorted) + sorted by first column (PK)
#             + no index + no timestamp metadata + fixed encoding/terminator
###==============================================================
import json
import sys
from typing import Dict

import pandas as pd

from hackdata.constants import export
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.utils import ensure_dir


def write_csv_canonical(df: pd.DataFrame, path: str) -> None:
    """Write a DataFrame to CSV in canonical (reproducible) form.

    Columns are sorted alphabetically; rows are sorted by the first
    column (assumed PK) so the file checksum is stable.

    Parameters
    ----------
    df : pd.DataFrame
        The data to write; must not be mutated.
    path : str
        Destination file path.

    # DRY RUN: df with columns ["amount", "id", "name"]
    #   sorted cols → ["amount", "id", "name"]  (already sorted)
    #   sort rows by "amount" (first col after sort)
    #   write with lineterminator="\n", encoding="utf-8", index=False
    """
    try:
        logging.info(f"write_csv_canonical: writing {path}")
        # Sort columns for a stable column order; copy to avoid mutating caller
        ordered_cols = sorted(df.columns.tolist())
        out = df[ordered_cols].copy()
        # Sort by the first column (PK proxy) for row-level stability
        out = out.sort_values(by=ordered_cols[0], ignore_index=True)
        ensure_dir(__import__("os").path.dirname(path))
        out.to_csv(
            path,
            index=False,
            lineterminator=export.EXP_CSV_LINE_TERMINATOR,
            encoding=export.EXP_CSV_ENCODING,
        )
        logging.info(f"write_csv_canonical: done — {path}")
    except Exception as e:
        raise HackDataException(e, sys)


def write_json_canonical(obj: object, path: str) -> None:
    """Write any JSON-serialisable object to a file with sorted keys.

    Parameters
    ----------
    obj : object
        JSON-serialisable Python object.
    path : str
        Destination file path.
    """
    try:
        logging.info(f"write_json_canonical: writing {path}")
        import os
        ensure_dir(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, sort_keys=True, indent=export.EXP_JSON_INDENT, ensure_ascii=False)
        logging.info(f"write_json_canonical: done — {path}")
    except Exception as e:
        raise HackDataException(e, sys)


def write_sql_dump(tables: Dict[str, pd.DataFrame], spec: dict, path: str) -> None:
    """Write a simple SQL dump with CREATE TABLE and INSERT statements.

    One INSERT per row for clarity (not a bulk insert).
    Dialect: EXP_SQL_DIALECT ("postgresql").

    Parameters
    ----------
    tables : Dict[str, pd.DataFrame]
        Mapping of table_name → DataFrame.
    spec : dict
        The generation spec; used to read column types when available.
        If a table is not in the spec, types are inferred from the DataFrame.
    path : str
        Destination .sql file path.

    # DRY RUN: tables = {"orders": df_orders}
    #   → "-- HackDataV2 SQL dump (postgresql)\n"
    #   → "CREATE TABLE IF NOT EXISTS orders (\n  id BIGINT, ...\n);\n"
    #   → "INSERT INTO orders (id, ...) VALUES (1, ...);\n"  × n_rows
    """
    try:
        logging.info(f"write_sql_dump: writing {path} ({export.EXP_SQL_DIALECT})")
        import os
        ensure_dir(os.path.dirname(path))

        lines = [f"-- HackDataV2 SQL dump ({export.EXP_SQL_DIALECT})\n\n"]

        for table_name, df in tables.items():
            # Sort columns for canonical order
            cols = sorted(df.columns.tolist())
            df_out = df[cols].copy()

            # --- BUILD CREATE TABLE ---
            col_defs = []
            for col in cols:
                dtype = df_out[col].dtype
                if str(dtype).startswith("int"):
                    sql_type = "BIGINT"
                elif str(dtype).startswith("float"):
                    sql_type = "DOUBLE PRECISION"
                elif str(dtype) == "bool":
                    sql_type = "BOOLEAN"
                else:
                    sql_type = "TEXT"
                col_defs.append(f"    {col} {sql_type}")

            lines.append(f"CREATE TABLE IF NOT EXISTS {table_name} (\n")
            lines.append(",\n".join(col_defs) + "\n);\n\n")

            # --- BUILD INSERT ROWS ---
            for _, row in df_out.iterrows():
                values = []
                for col in cols:
                    val = row[col]
                    if val is None or (isinstance(val, float) and __import__("math").isnan(val)):
                        values.append("NULL")
                    elif isinstance(val, bool):
                        values.append("TRUE" if val else "FALSE")
                    elif isinstance(val, (int, float)):
                        values.append(str(val))
                    else:
                        # Escape single quotes for SQL safety
                        escaped = str(val).replace("'", "''")
                        values.append(f"'{escaped}'")
                col_list = ", ".join(cols)
                val_list = ", ".join(values)
                lines.append(f"INSERT INTO {table_name} ({col_list}) VALUES ({val_list});\n")

            lines.append("\n")

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        logging.info(f"write_sql_dump: done — {path}")
    except Exception as e:
        raise HackDataException(e, sys)
