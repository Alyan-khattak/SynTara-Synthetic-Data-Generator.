# ═══════════════════════════════════════════════════════════════════
# spec_builder.py — query/template → validated spec + value pools
# ═══════════════════════════════════════════════════════════════════
# Position in pipeline:
#
#     GenerationRequest
#          │
#          ▼  (this component)
#     SpecBuilderArtifact
#          │  spec.json   ← validated Spec written to artifact dir
#          │  pools.json  ← {table: {col: [values]}} for "pool" columns
#          ▼
#     FeasibilityChecker
#
# IMP: the only file that decides WHERE the spec comes from (cache,
#      LLM, template, or user override). Everything downstream gets
#      the same typed artifact regardless of source.
###==============================================================
"""
SpecBuilder

    GenerationRequest  ──▶  [SpecBuilder]  ──▶  SpecBuilderArtifact
                                  │
                                  ├─ load_template()   (template path)
                                  ├─ ask_llm_for_spec() (query path)
                                  ├─ validate_spec()
                                  └─ fetch_pools()
"""

import json
import os
import re
import sys
from typing import Dict

from pydantic import ValidationError

from hackdata.cloud.llm_client import ask_json, ask_text
from hackdata.cloud.jev_client import route_query
from hackdata.constants import generation as gen_const, paths as paths_const, llm as llm_const
from hackdata.entity.artifact_entity import SpecBuilderArtifact
from hackdata.entity.config_entity import SpecBuilderConfig
from hackdata.entity.request_entity import GenerationRequest
from hackdata.entity.spec_entity import Spec
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.utils import (
    ensure_dir,
    read_yaml_file,
    write_json_file,
)


class SpecBuilder:
    """
    Converts a GenerationRequest into a validated Spec artifact on disk.

    Parameters
    ----------
    config  : SpecBuilderConfig — paths for spec.json and pools.json
    request : GenerationRequest — caller's intent (query, template, or override)
    """

    def __init__(self, config: SpecBuilderConfig, request: GenerationRequest):
        try:
            self.config = config
            self.request = request
        except Exception as e:
            raise HackDataException(e, sys)

    # ─────────────────────────────────────────────────────────────────
    # LOAD TEMPLATE
    # ─────────────────────────────────────────────────────────────────

    def load_template(self) -> dict:
        """Load a pre-built YAML template from data_assets/templates/.

        The template file name is taken from ``request.template``.  A ".yaml"
        suffix is appended if the caller did not include it.

        Returns
        -------
        dict
            Raw dict from the YAML file; must pass ``validate_spec()`` next.

        # DRY RUN: request.template = "ecommerce"
        #   path = "data_assets/templates/ecommerce.yaml"
        #   → read_yaml_file(path)  →  dict matching Spec schema
        """
        try:
            logging.info(f"SpecBuilder.load_template: loading template={self.request.template}")

            name = self.request.template
            # IMP: tolerate callers who omit the extension
            if not name.endswith(".yaml"):
                name = name + ".yaml"

            path = os.path.join(
                paths_const.DATA_ASSETS_DIR,
                paths_const.TEMPLATES_ASSETS_DIR,
                name,
            )
            spec_dict = read_yaml_file(path)
            logging.info(f"SpecBuilder.load_template: done path={path}")
            return spec_dict
        except Exception as e:
            raise HackDataException(e, sys)

    # ─────────────────────────────────────────────────────────────────
    # ASK LLM
    # ─────────────────────────────────────────────────────────────────

    def ask_llm_for_spec(self) -> dict:
        """Call the LLM to generate a spec for request.query.

        ask_json handles the full reliability chain (cache → Groq key
        rotation → model fallback → offline_fallback), so this method
        only needs to package the call.

        Returns
        -------
        dict
            Validated spec dict (already passed through Spec Pydantic model
            inside ask_json).

        Raises
        ------
        HackDataException
            On Pydantic ValidationError or total LLM+offline failure.

        # DRY RUN: request.query = "100 customers with name and age"
        #   variables = {"query": "100 customers ...", "module": "tabular", "n_rows": 1000}
        #   ask_json("spec", variables, Spec)
        #   → spec dict with tables[0].name = "customers", n_rows = 100
        """
        try:
            logging.info(
                f"SpecBuilder.ask_llm_for_spec: query='{self.request.query}' "
                f"module={self.request.module} n_rows={self.request.n_rows}"
            )
            variables = {
                "query": self.request.query,
                "module": self.request.module,
                "n_rows": self.request.n_rows,
                "locale": self.request.locale,
            }
            spec_dict = ask_json("spec", variables, Spec)
            logging.info("SpecBuilder.ask_llm_for_spec: done")
            return spec_dict
        except ValidationError as ve:
            # IMP: ValidationError from Pydantic means the LLM returned
            #      a structurally wrong spec that the repair path could not fix.
            raise HackDataException(ve, sys)
        except Exception as e:
            raise HackDataException(e, sys)

    # ─────────────────────────────────────────────────────────────────
    # VALIDATE SPEC
    # ─────────────────────────────────────────────────────────────────

    def validate_spec(self, spec_dict: dict) -> Spec:
        """Parse and validate a raw dict into a Spec Pydantic model.

        Parameters
        ----------
        spec_dict : dict
            Raw spec dictionary from LLM, template, or user override.

        Returns
        -------
        Spec
            Validated model; all vocabulary checks have passed.

        Raises
        ------
        HackDataException
            When the dict fails Pydantic validation (bad generator name,
            unknown rule, etc.); the error message names the failing field.
        """
        try:
            logging.info("SpecBuilder.validate_spec: validating spec")  # noqa: hardcode
            spec = Spec(**spec_dict)
            total_rows = sum(t.n_rows for t in spec.tables)
            logging.info(
                f"SpecBuilder.validate_spec: valid — "
                f"tables={len(spec.tables)} total_rows={total_rows}"
            )
            return spec
        except ValidationError as ve:
            raise HackDataException(ve, sys)
        except Exception as e:
            raise HackDataException(e, sys)

    # ─────────────────────────────────────────────────────────────────
    # FETCH POOLS
    # ─────────────────────────────────────────────────────────────────

    def fetch_pools(self, spec: Spec) -> dict:
        """Ask the LLM for value pools for every column where gen == "pool".

        IMP: returns {} immediately (no LLM call) when no "pool" columns exist.
        This is the common case for simple tabular specs.

        Pool size is validated against GEN_POOL_SIZE_MIN / GEN_POOL_SIZE_MAX.
        If the LLM returns an invalid or empty response for a column, that
        column gets an empty list (graceful degradation — the generator will
        handle the missing pool at runtime).

        Parameters
        ----------
        spec : Spec
            Validated spec to scan for pool columns.

        Returns
        -------
        dict
            Nested dict: {table_name: {col_name: [values]}}.
            Tables or columns with no pool columns are omitted.

        # DRY RUN: spec has "customers.city" with gen="pool"
        #   ask_text("pool", {"column": "city", "context": "customers table — 100 rows"})
        #   → '["Karachi", "Lahore", ...]'
        #   → parsed list of length 250 (within [200, 300]) → stored
        """
        try:
            logging.info("SpecBuilder.fetch_pools: scanning spec for pool columns")  # noqa: hardcode

            pools: Dict[str, Dict[str, list]] = {}

            for table in spec.tables:
                for col in table.columns:
                    if col.gen != "pool":
                        continue

                    # IMP: context gives the LLM enough information to produce
                    #      semantically relevant pool values for this column.
                    context = (
                        f"{table.name} table — {table.n_rows} rows; "
                        f"query: {self.request.query}"
                    )
                    logging.info(
                        f"SpecBuilder.fetch_pools: requesting pool "
                        f"table={table.name} col={col.name}"
                    )
                    raw = ask_text("pool", {"column": col.name, "context": context}, expect_json=True)

                    values: list = []
                    if raw:
                        try:
                            # Strip markdown code fences the model sometimes wraps around JSON
                            clean = re.sub(r"^```(?:json)?\s*\n?", "", raw.strip(), flags=re.IGNORECASE)
                            clean = re.sub(r"\n?```\s*$", "", clean)
                            parsed = json.loads(clean)
                            if isinstance(parsed, list):
                                n = len(parsed)
                                # IMP: validate pool size bounds; log a warning
                                #      but still store whatever the LLM gave us
                                #      so the generator can work with it.
                                if n < gen_const.GEN_POOL_SIZE_MIN or n > gen_const.GEN_POOL_SIZE_MAX:
                                    logging.info(  # noqa: hardcode
                                        f"SpecBuilder.fetch_pools: pool size {n} outside "
                                        f"[{gen_const.GEN_POOL_SIZE_MIN}, "
                                        f"{gen_const.GEN_POOL_SIZE_MAX}] "
                                        f"for {table.name}.{col.name}"
                                    )
                                values = parsed
                            else:
                                logging.info(  # noqa: hardcode
                                    f"SpecBuilder.fetch_pools: non-list JSON for "
                                    f"{table.name}.{col.name} — skipping"
                                )
                        except json.JSONDecodeError:
                            logging.info(  # noqa: hardcode
                                f"SpecBuilder.fetch_pools: JSON parse error for "
                                f"{table.name}.{col.name} — storing empty pool"
                            )

                    pools.setdefault(table.name, {})[col.name] = values

            if not pools:
                logging.info("SpecBuilder.fetch_pools: no pool columns — skipping LLM calls")  # noqa: hardcode
            else:
                logging.info(f"SpecBuilder.fetch_pools: done — {len(pools)} table(s) with pools")

            return pools
        except Exception as e:
            raise HackDataException(e, sys)

    # ─────────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ─────────────────────────────────────────────────────────────────

    def initiate_spec_builder(self) -> SpecBuilderArtifact:
        """Run the full spec-building stage and write outputs to disk.

        Decision tree:
            spec_override set  → validate user-provided dict directly
            template set       → load YAML template, then validate
            otherwise          → ask LLM (with offline fallback)

        Returns
        -------
        SpecBuilderArtifact
            Paths to spec.json and pools.json, source label, unsupported list.

        Raises
        ------
        HackDataException
            On any unrecoverable failure (bad template path, validation error, etc.)
        """
        try:
            logging.info("SpecBuilder.initiate_spec_builder: started")  # noqa: hardcode
            ensure_dir(self.config.spec_builder_dir)

            # ── decide spec source ──────────────────────────────────
            if self.request.spec_override:
                # IMP: user-provided dict — validate, no LLM call
                spec = self.validate_spec(self.request.spec_override)
                source = "user_edit"

            elif self.request.template:
                # Pre-built YAML template; semantics are guaranteed offline
                spec_dict = self.load_template()
                spec = self.validate_spec(spec_dict)
                source = "llm"  # templates count as offline-validated LLM output

            else:
                # Query mode: Jev routes first (fast, cheap), then LLM.
                # IMP: route_query returns (None, None) when JEV_API_KEY absent —
                #      the pipeline continues unchanged in that case.
                valid_prob, jev_module = route_query(
                    self.request.query, self.request.module
                )

                if valid_prob is not None and valid_prob < llm_const.LLM_JEV_VALID_THRESHOLD:
                    # Jev is confident this is NOT a data-gen request — skip LLM.
                    # ponytail: offline spec is generic; upgrade to error response if UX requires it.
                    logging.info(
                        f"SpecBuilder: Jev validity={valid_prob:.3f} below threshold "
                        f"{llm_const.LLM_JEV_VALID_THRESHOLD} — using offline fallback"
                    )
                    from hackdata.cloud.offline_fallback import build_offline_spec
                    spec_dict = build_offline_spec(self.request.query, self.request.module)
                    source = "offline"
                else:
                    if jev_module and jev_module != self.request.module:
                        logging.info(
                            f"SpecBuilder: Jev suggests module={jev_module} "
                            f"but request has module={self.request.module} — keeping request"
                        )
                    spec_dict = self.ask_llm_for_spec()
                    source = "llm"

                spec = self.validate_spec(spec_dict)

            # ── fetch pool values ───────────────────────────────────
            pools = self.fetch_pools(spec)

            # ── persist to disk ─────────────────────────────────────
            write_json_file(self.config.spec_file_path, spec.model_dump())
            write_json_file(self.config.pools_file_path, pools)

            logging.info(
                f"SpecBuilder.initiate_spec_builder: done — "
                f"tables={len(spec.tables)} source={source}"
            )
            return SpecBuilderArtifact(
                spec_file_path=self.config.spec_file_path,
                pools_file_path=self.config.pools_file_path,
                spec_source=source,
                unsupported=[],
            )
        except Exception as e:
            raise HackDataException(e, sys)


# ─────────────────────────────────────────────────────────────────────
# SELF-CHECK (ponytail: smallest test that fails if the logic breaks)
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys
    _sys.path.insert(0, ".")

    from hackdata.entity.config_entity import RunConfig, SpecBuilderConfig
    from hackdata.entity.request_entity import GenerationRequest

    rc = RunConfig()
    config = SpecBuilderConfig(rc)
    request = GenerationRequest(
        module="tabular",
        mode="query",
        query="100 customer records with name and age",
    )

    builder = SpecBuilder(config, request)
    artifact = builder.initiate_spec_builder()

    assert artifact.spec_file_path.endswith("spec.json"), "spec path wrong"
    assert artifact.pools_file_path.endswith("pools.json"), "pools path wrong"
    assert artifact.spec_source in ("llm", "user_edit", "offline"), "bad source"

    with open(artifact.spec_file_path) as f:
        spec = json.load(f)
    assert "tables" in spec and len(spec["tables"]) > 0, "no tables in spec"

    print("spec_file_path:", artifact.spec_file_path)
    print("spec_source:", artifact.spec_source)
    print("tables:", [t["name"] for t in spec["tables"]])
    print("T-013 PASS")
