# ═══════════════════════════════════════════════════════════════════
# relational_generator.py — Relational table generation engine
# ═══════════════════════════════════════════════════════════════════
# Implements T-027 / T-028: parent-first generation, FK linkage via
# np.repeat, and zero orphan key guarantees.
# ═══════════════════════════════════════════════════════════════════
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from hackdata.constants import generation as gen_const
from hackdata.components.generators.column_generators import generate_column
from hackdata.entity.spec_entity import Spec, TableSpec
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.seed_utils import make_rng


class RelationalGenerator:
    """Generates relational tables in dependency order.

    Parent tables are generated first. Child tables draw cardinality
    counts per parent and replicate parent primary keys via np.repeat
    to guarantee zero orphan foreign keys.
    """

    def __init__(self, spec: Spec, master_seed: int = gen_const.GEN_DEFAULT_MASTER_SEED, pools: Optional[Dict] = None):
        """
        Parameters
        ----------
        spec : Spec
            Validated multi-table relational specification.
        master_seed : int
            Run-level seed for deterministic generation.
        pools : dict, optional
            Pre-fetched categorical text pools from LLM / assets.
        """
        try:
            self.spec = spec
            self.master_seed = master_seed
            self.pools = pools or {}
        except Exception as e:
            raise HackDataException(e, sys)

    def _sort_tables_by_dependency(self) -> List[TableSpec]:
        """Order tables so parent tables come before child tables."""
        table_map = {t.name: t for t in self.spec.tables}
        ordered: List[TableSpec] = []
        visited = set()

        def visit(table: TableSpec):
            if table.name in visited:
                return
            if table.parent and table.parent.table in table_map:
                parent_table = table_map[table.parent.table]
                visit(parent_table)
            visited.add(table.name)
            ordered.append(table)

        for table in self.spec.tables:
            visit(table)

        return ordered

    def generate_all_tables(self) -> Dict[str, pd.DataFrame]:
        """Generate all tables defined in self.spec in dependency order.

        Returns
        -------
        dict
            {table_name: pd.DataFrame}
        """
        try:
            logging.info(f"RelationalGenerator.generate_all_tables: starting for {len(self.spec.tables)} tables")
            ordered_tables = self._sort_tables_by_dependency()
            generated_tables: Dict[str, pd.DataFrame] = {}

            for table_spec in ordered_tables:
                if table_spec.parent and table_spec.parent.table in generated_tables:
                    # Child table generation
                    parent_table_name = table_spec.parent.table
                    parent_df = generated_tables[parent_table_name]
                    fk_col_name = table_spec.parent.key
                    cardinality = table_spec.parent.cardinality

                    # Primary key column of parent (default "id" or first column)
                    parent_pk_col = "id" if "id" in parent_df.columns else parent_df.columns[0]
                    parent_pks = parent_df[parent_pk_col].values
                    n_parents = len(parent_pks)

                    # Draw children count per parent using seeded rng
                    rng_card = make_rng(self.master_seed, table_spec.name, "cardinality")
                    min_c = cardinality.min_per_parent
                    max_c = cardinality.max_per_parent
                    child_counts = rng_card.integers(min_c, max_c + 1, size=n_parents)

                    # Repeat parent PKs to generate child FK column (zero orphans)
                    fk_values = np.repeat(parent_pks, child_counts)
                    n_child_rows = len(fk_values)

                    existing_cols: Dict[str, pd.Series] = {
                        fk_col_name: pd.Series(fk_values)
                    }

                    # Generate remaining child columns
                    col_dict: Dict[str, pd.Series] = {}
                    for col_spec in table_spec.columns:
                        col_dict[col_spec.name] = generate_column(
                            col_spec=col_spec.model_dump(),
                            n=n_child_rows,
                            master_seed=self.master_seed,
                            table_name=table_spec.name,
                            existing_cols=existing_cols,
                        )
                        existing_cols[col_spec.name] = col_dict[col_spec.name]

                    # Ensure FK column is set in final DataFrame
                    col_dict[fk_col_name] = pd.Series(fk_values)
                    df = pd.DataFrame(col_dict)
                    generated_tables[table_spec.name] = df
                    logging.info(f"RelationalGenerator: generated child table {table_spec.name} ({n_child_rows} rows)")

                else:
                    # Independent / Parent table generation
                    n_rows = table_spec.n_rows
                    existing_cols: Dict[str, pd.Series] = {}
                    col_dict: Dict[str, pd.Series] = {}

                    for col_spec in table_spec.columns:
                        col_dict[col_spec.name] = generate_column(
                            col_spec=col_spec.model_dump(),
                            n=n_rows,
                            master_seed=self.master_seed,
                            table_name=table_spec.name,
                            existing_cols=existing_cols,
                        )
                        existing_cols[col_spec.name] = col_dict[col_spec.name]

                    df = pd.DataFrame(col_dict)
                    generated_tables[table_spec.name] = df
                    logging.info(f"RelationalGenerator: generated parent table {table_spec.name} ({n_rows} rows)")

            return generated_tables

        except HackDataException:
            raise
        except Exception as e:
            raise HackDataException(e, sys)
