# ═══════════════════════════════════════════════════════════════════
# scorecard.py — Synthetic Data Scorecard Aggregation & Export
# ═══════════════════════════════════════════════════════════════════
# Implements T-047: Scorecard aggregation with weights 0.25/0.25/0.30/0.20
# ═══════════════════════════════════════════════════════════════════

import os
import sys
import json
from typing import Dict, Any, Optional

from hackdata.constants import evaluation, paths
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.utils import ensure_dir

class ScorecardAggregator:
    """
    Aggregates Validity, Fidelity, Utility, and Privacy scores into an
    overall synthetic data quality scorecard (0-100) and exports scores.json.
    """
    def __init__(self, run_id: str, run_dir: Optional[str] = None):
        # IMP: accept an explicit run_dir so callers that already know the
        #      artifact directory can avoid re-computing ARTIFACTS_TEMP_DIR + run_id.
        #      Defaults to ARTIFACTS_TEMP_DIR/<run_id> for backward compatibility.
        self.run_id = run_id
        self.artifact_dir = run_dir or os.path.join(paths.ARTIFACTS_TEMP_DIR, run_id)
        self.eval_dir = os.path.join(self.artifact_dir, paths.EVALUATION_DIR_NAME)
        ensure_dir(self.eval_dir)

    def calculate_scorecard(
        self,
        validity_score: float,
        fidelity_score: float,
        utility_score: float,
        privacy_score: float,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Combines metric scores using configuration weights.
        """
        try:
            weights = evaluation.EVAL_WEIGHTS
            
            val_w = weights.get("validity", 0.25)
            fid_w = weights.get("fidelity", 0.25)
            util_w = weights.get("utility", 0.30)
            priv_w = weights.get("privacy", 0.20)
            
            overall_score = (
                val_w * validity_score +
                fid_w * fidelity_score +
                util_w * utility_score +
                priv_w * privacy_score
            )
            overall_score = round(float(overall_score), 2)
            
            scorecard = {
                "overall_score": overall_score,
                "overall": overall_score,       # alias: frontend reads scores.scores.overall
                "validity": round(float(validity_score), 2),
                "fidelity": round(float(fidelity_score), 2),
                "utility": round(float(utility_score), 2),
                "privacy": round(float(privacy_score), 2),
                "weights": weights,
                "details": details or {}
            }
            
            scores_path = os.path.join(self.eval_dir, paths.SCORES_FILE_NAME)
            with open(scores_path, "w", encoding="utf-8") as f:
                json.dump(scorecard, f, indent=2)
                
            logging.info(f"ScorecardAggregator: Saved scores.json with overall_score={overall_score}")
            return scorecard

        except Exception as e:
            raise HackDataException(e, sys)
