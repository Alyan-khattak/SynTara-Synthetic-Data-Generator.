#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════
# model_bakeoff.py — compare Groq open-weight models for this project
# ═══════════════════════════════════════════════════════════════════
# Sends 5 realistic spec-generation requests to each candidate model,
# records valid-schema rate, latency, and errors.
# Results written to docs/model_bakeoff.md.
#
# Usage: python scripts/model_bakeoff.py
###==============================================================
import json
import os
import sys
import time
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
# Ensure project root on path for hackdata imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import groq
from pydantic import ValidationError

from hackdata.entity.spec_entity import Spec

# ── Config ────────────────────────────────────────────────────────
CANDIDATES = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
]

# 5 realistic requests covering this project's main use cases
REQUESTS = [
    {
        "name": "ecommerce_tabular",
        "query": "100 e-commerce orders with order_id, customer_name, amount, status, and date",
        "module": "tabular",
        "n_rows": 100,
        "locale": "en_PK",
    },
    {
        "name": "banking_relational",
        "query": "50 bank customers each with 1-5 transactions, include customer_id, name, account_type, and transaction amount",
        "module": "relational",
        "n_rows": 50,
        "locale": "en_PK",
    },
    {
        "name": "hr_employees",
        "query": "200 employee records with name, department, salary, hire_date, and performance_score",
        "module": "tabular",
        "n_rows": 200,
        "locale": "en_PK",
    },
    {
        "name": "invoices",
        "query": "30 invoice documents with invoice_id, recipient, amount, due_date, and payment_status",
        "module": "documents",
        "n_rows": 30,
        "locale": "en_PK",
    },
    {
        "name": "product_inventory",
        "query": "150 product inventory records with sku, name, category, price, and stock_quantity",
        "module": "tabular",
        "n_rows": 150,
        "locale": "en_PK",
    },
]

PROMPT_TEMPLATE = open(
    os.path.join(os.path.dirname(__file__), "..", "data_assets", "prompts", "spec_prompt.txt"),
    encoding="utf-8",
).read()

# Build JSON schema from the Spec Pydantic model for strict mode
_SPEC_SCHEMA = Spec.model_json_schema()
# Groq strict mode requires additionalProperties: false recursively,
# but the spec uses extra="forbid" already so the schema is close.
# IMP: remove $defs references that confuse strict mode — fall back to
#      json_object if strict mode is rejected.


def _get_client() -> groq.Groq:
    keys_raw = os.getenv("GROQ_API_KEYS", "")
    keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
    if not keys:
        raise SystemExit("GROQ_API_KEYS not set in .env")
    return groq.Groq(api_key=keys[0])


def _call_model(
    client: groq.Groq,
    model: str,
    prompt: str,
) -> tuple[Optional[dict], float, str]:
    """Return (parsed_dict_or_None, latency_seconds, mode_used).

    Tries json_schema strict first; falls back to json_object.
    """
    t0 = time.perf_counter()
    mode = "json_schema"

    # Try strict JSON schema mode
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "Spec",
                    "schema": _SPEC_SCHEMA,
                    "strict": True,
                },
            },
            timeout=30,
        )
    except groq.BadRequestError:
        # Model doesn't support json_schema strict — fall back
        mode = "json_object"
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
            timeout=30,
        )

    latency = time.perf_counter() - t0
    content = resp.choices[0].message.content or ""

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None, latency, mode + " (json_parse_error)"

    return parsed, latency, mode


def run_bakeoff() -> dict:
    client = _get_client()
    results = {}

    for model in CANDIDATES:
        print(f"\n── {model} ──────────────────────────")
        valid = 0
        latencies = []
        errors = []
        mode_used = "json_schema"

        for req in REQUESTS:
            prompt = PROMPT_TEMPLATE.format(
                query=req["query"],
                module=req["module"],
                n_rows=req["n_rows"],
                locale=req["locale"],
            )

            try:
                parsed, lat, mode = _call_model(client, model, prompt)
                mode_used = mode  # record last used mode
                latencies.append(lat)

                if parsed is None:
                    errors.append(f"{req['name']}: json parse error")
                    print(f"  FAIL ({lat:.1f}s) {req['name']}: json parse error")
                    continue

                # Validate against Spec Pydantic schema
                try:
                    Spec(**parsed)
                    valid += 1
                    print(f"  PASS ({lat:.1f}s) {req['name']}  [{mode}]")
                except ValidationError as ve:
                    err = str(ve).split("\n")[0]
                    errors.append(f"{req['name']}: schema error — {err}")
                    print(f"  FAIL ({lat:.1f}s) {req['name']}: schema error — {err}")

            except Exception as exc:
                errors.append(f"{req['name']}: {exc}")
                latencies.append(0)
                print(f"  ERROR {req['name']}: {exc}")

        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        print(f"  → valid {valid}/5  avg_lat {avg_lat:.1f}s  mode={mode_used}")
        results[model] = {
            "valid_rate": f"{valid}/5",
            "valid_count": valid,
            "avg_latency_s": round(avg_lat, 2),
            "mode": mode_used,
            "errors": errors,
        }

    return results


def pick_models(results: dict) -> tuple[str, str]:
    # Sort by valid_count desc, then avg_latency asc
    ranked = sorted(
        results.items(),
        key=lambda kv: (-kv[1]["valid_count"], kv[1]["avg_latency_s"]),
    )
    primary = ranked[0][0]
    backup = ranked[1][0] if len(ranked) > 1 else ranked[0][0]
    return primary, backup


def write_markdown(results: dict, primary: str, backup: str) -> None:
    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "model_bakeoff.md")

    lines = [
        "# Model Bake-off Results\n",
        "Candidates run against 5 realistic spec-generation requests "
        "from this project's main feature.\n",
        "| Model | Valid/5 | Avg latency (s) | Mode | Notes |",
        "|---|---|---|---|---|",
    ]
    for model, r in results.items():
        tag = ""
        if model == primary:
            tag = " **← PRIMARY**"
        elif model == backup:
            tag = " ← backup"
        errs = "; ".join(r["errors"]) if r["errors"] else "none"
        lines.append(
            f"| `{model}` | {r['valid_rate']} | {r['avg_latency_s']} "
            f"| {r['mode']} | errors: {errs}{tag} |"
        )

    lines += [
        "",
        f"**Primary model chosen:** `{primary}`  ",
        f"**Backup model:** `{backup}`",
        "",
        "## Licence notes",
        "- `openai/gpt-oss-20b` and `openai/gpt-oss-120b`: Apache 2.0 "
        "(VERIFY at https://huggingface.co/openai/gpt-oss-20b)",
        "- `qwen/qwen3.8-27b`: Qwen License "
        "(VERIFY at https://huggingface.co/Qwen/Qwen3.8-27B)",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nResults written to {path}")


if __name__ == "__main__":
    print("Running model bakeoff...")
    results = run_bakeoff()
    primary, backup = pick_models(results)
    print(f"\nPrimary: {primary}")
    print(f"Backup:  {backup}")
    write_markdown(results, primary, backup)
    # Print summary for reference by the next step
    print("\nSummary JSON:")
    print(json.dumps({"primary": primary, "backup": backup, "results": results}, indent=2))
