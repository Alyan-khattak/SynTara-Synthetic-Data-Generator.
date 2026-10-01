# ═══════════════════════════════════════════════════════════════════
# exporter.py — formats synthetic tables into CSV, JSON, or ZIP
# ═══════════════════════════════════════════════════════════════════
import datetime
import os
import sys
import zipfile
import pandas as pd
from typing import Dict, List, Optional
from hackdata.constants import paths as paths_const, messages as msg_const
from hackdata.exception.exception import HackDataException

class Exporter:
    def __init__(self, run_id: str):
        self.run_id = run_id
        
        # Check temp then saved
        self.run_dir = os.path.join(paths_const.ARTIFACTS_TEMP_DIR, run_id)
        if not os.path.exists(self.run_dir):
            self.run_dir = os.path.join(paths_const.ARTIFACTS_SAVED_DIR, run_id)
            
        if not os.path.exists(self.run_dir):
            raise HackDataException(Exception(f"Run '{run_id}' not found"), sys)
            
        self.export_dir = os.path.join(self.run_dir, paths_const.EXPORT_DIR_NAME)
        os.makedirs(self.export_dir, exist_ok=True)
        
    def export(self, format_type: str) -> str:
        """
        Exports tables in the given format and returns the file path.
        Allowed formats: 'csv' (as zip), 'json' (as zip), 'zip' (default csv zip).
        """
        format_type = format_type.lower()
        if format_type not in ["csv", "json", "zip"]:
            format_type = "csv"
            
        tables_dir = os.path.join(self.run_dir, paths_const.DATA_GENERATION_DIR_NAME, paths_const.TABLES_DIR_NAME)
        dm_csv = os.path.join(self.run_dir, paths_const.SYNTHETIC_DATA_FILE_NAME)
        
        has_tables = os.path.exists(tables_dir) and len(os.listdir(tables_dir)) > 0
        has_dm_csv = os.path.exists(dm_csv)
        
        if not has_tables and not has_dm_csv:
            raise HackDataException(Exception("No table artifacts found to download"), sys)
            
        out_filename = os.path.join(self.export_dir, f"{self.run_id}_export.{format_type}.zip")
        
        with zipfile.ZipFile(out_filename, "w", zipfile.ZIP_DEFLATED) as zf:
            # IMP: NOTICE.txt is always the first entry so it is visible before data files.
            zf.writestr("NOTICE.txt", msg_const.MSG_SYNTHETIC_DATA_NOTICE)

            table_info: List[Dict] = []  # collected for DATA_CARD.md

            if has_tables:
                for root, _, files in os.walk(tables_dir):
                    for file in sorted(files):  # sorted for determinism
                        if not file.endswith(".csv"):
                            continue

                        full_path = os.path.join(root, file)
                        table_name = os.path.splitext(file)[0]
                        df = pd.read_csv(full_path)
                        table_info.append({"name": table_name, "rows": len(df), "columns": list(df.columns)})

                        if format_type == "json":
                            json_str = df.to_json(orient="records")
                            zf.writestr(f"{table_name}.json", json_str)
                        else:
                            zf.write(full_path, f"{table_name}.csv")
            elif has_dm_csv:
                df = pd.read_csv(dm_csv)
                table_info.append({"name": "synthetic_data", "rows": len(df), "columns": list(df.columns)})
                if format_type == "json":
                    json_str = df.to_json(orient="records")
                    zf.writestr("synthetic_data.json", json_str)
                else:
                    zf.write(dm_csv, "synthetic_data.csv")

            # Step D: DATA_CARD.md in every ZIP
            zf.writestr("DATA_CARD.md", self._build_data_card(table_info))

        return out_filename

    def _build_data_card(self, table_info: List[Dict]) -> str:
        """Generate DATA_CARD.md from run metadata + table info.

        Uses a template — no LLM call.  Reads spec.json and run_metadata.json
        if present; falls back gracefully when files are missing.
        """
        import json

        # Load spec for relationships and seed info
        spec_data: dict = {}
        spec_path = os.path.join(
            self.run_dir, paths_const.SPEC_BUILDER_DIR_NAME, paths_const.SPEC_FILE_NAME
        )
        if os.path.exists(spec_path):
            try:
                with open(spec_path) as f:
                    spec_data = json.load(f)
            except Exception:
                pass

        meta: dict = {}
        meta_path = os.path.join(self.run_dir, paths_const.GENERATION_RUN_META_FILE_NAME)
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
            except Exception:
                pass

        module = spec_data.get("module", meta.get("module", "unknown"))
        seed = meta.get("seed", spec_data.get("seed", "—"))
        model_id = meta.get("model_id", spec_data.get("model_id", "not recorded"))
        generated_at = meta.get("generated_at", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

        # Relationships section
        tables_in_spec = spec_data.get("tables", [])
        fk_lines: List[str] = []
        for t in tables_in_spec:
            if t.get("parent"):
                parent = t["parent"]["table"]
                key = t["parent"]["key"]
                fk_lines.append(f"- `{t['name']}.{key}` → `{parent}`")
        relationships = "\n".join(fk_lines) if fk_lines else "none (single table)"

        # Messiness settings from spec columns
        messiness_lines: List[str] = []
        for t in tables_in_spec:
            for col in t.get("columns", []):
                parts = []
                if col.get("null_rate"):
                    parts.append(f"null_rate={col['null_rate']}")
                if col.get("outlier_rate"):
                    parts.append(f"outlier_rate={col['outlier_rate']}")
                if col.get("class_imbalance"):
                    parts.append(f"class_imbalance={col['class_imbalance']}")
                if parts:
                    messiness_lines.append(f"- `{t['name']}.{col['name']}`: {', '.join(parts)}")
        messiness = "\n".join(messiness_lines) if messiness_lines else "none"

        # Tables section
        table_sections: List[str] = []
        for ti in table_info:
            col_list = ", ".join(ti["columns"][:10])
            if len(ti["columns"]) > 10:
                col_list += f", … (+{len(ti['columns']) - 10} more)"
            table_sections.append(
                f"### {ti['name']}\n- Rows: {ti['rows']}\n- Columns: {col_list}"
            )
        tables_md = "\n\n".join(table_sections) if table_sections else "_(no tables)_"

        return f"""# Data Card — HackDataV2 Synthetic Dataset

## Overview

| Field | Value |
|---|---|
| Dataset name | {self.run_id} |
| Module | {module} |
| Generated at | {generated_at} |
| Seed | {seed} |
| Model (spec) | {model_id} |

## Tables

{tables_md}

## Relationships

{relationships}

## Messiness settings

{messiness}

## Limitations

- All values are **synthetic**. They were generated by HackDataV2 and do not represent real people, organisations, transactions or events.
- Names, addresses, IDs and financial figures are fabricated.
- Card numbers (if any) are published processor test cards only — never real payment credentials.
- This dataset is intended for software testing, ML model prototyping and data engineering practice, **not for real decisions**.
- Statistical properties approximate the spec; they are not guaranteed to match any real-world distribution.
"""

    def export_pdf(self) -> str:
        """Render each row of the first documents table as an invoice-style PDF page."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet

            tables_dir = os.path.join(self.run_dir, paths_const.DATA_GENERATION_DIR_NAME, paths_const.TABLES_DIR_NAME)
            dm_csv = os.path.join(self.run_dir, paths_const.SYNTHETIC_DATA_FILE_NAME)

            df = None
            table_name = "documents"
            if os.path.exists(tables_dir):
                for fname in os.listdir(tables_dir):
                    if fname.endswith(".csv"):
                        df = pd.read_csv(os.path.join(tables_dir, fname))
                        table_name = os.path.splitext(fname)[0]
                        break
            if df is None and os.path.exists(dm_csv):
                df = pd.read_csv(dm_csv)

            if df is None or df.empty:
                raise HackDataException(Exception("No data to export as PDF"), sys)

            out_path = os.path.join(self.export_dir, f"{self.run_id}_documents.pdf")
            styles = getSampleStyleSheet()
            story = []

            for idx, row in df.iterrows():
                story.append(Paragraph(f"<b>Document #{idx + 1}</b>", styles["Heading2"]))
                story.append(Spacer(1, 0.3 * cm))

                data = [[str(col), str(val)] for col, val in row.items()]
                t = Table(data, colWidths=[6 * cm, 11 * cm])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f4ff")),
                    ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE",   (0, 0), (-1, -1), 9),
                    ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
                    ("LEFTPADDING",  (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING",   (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
                ]))
                story.append(t)
                story.append(Spacer(1, 0.8 * cm))

            doc = SimpleDocTemplate(out_path, pagesize=A4,
                                    leftMargin=2*cm, rightMargin=2*cm,
                                    topMargin=2*cm, bottomMargin=2*cm)
            doc.build(story)
            return out_path
        except Exception as e:
            raise HackDataException(e, sys)
