# ═══════════════════════════════════════════════════════════════════
# prompt_loader.py — loads prompt templates from data_assets/prompts/
# ═══════════════════════════════════════════════════════════════════
# IMP: callers pass a prompt NAME (key in LLM_PROMPT_FILES), never a
#      raw filename — keeps the asset layout hidden and prevents traversal.
###==============================================================
import os
import sys

from hackdata.constants import llm as llm_const, paths as paths_const, messages
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


def load_prompt(prompt_name: str) -> str:
    """Load a prompt template from data_assets/prompts/.

    Parameters
    ----------
    prompt_name : str
        A key in LLM_PROMPT_FILES — e.g. "spec", "pool", "narrative", "repair".

    Returns
    -------
    str
        Raw UTF-8 file contents of the prompt template.

    Raises
    ------
    HackDataException
        If prompt_name is not in LLM_PROMPT_FILES, or the file does not exist.

    # IMP: use a name, not a filename — this prevents directory traversal and
    #      lets us rename files without touching callers.
    # DRY RUN: load_prompt("spec")
    #   filename = LLM_PROMPT_FILES["spec"]  → "spec_prompt.txt"
    #   path     = data_assets/prompts/spec_prompt.txt
    #   → read and return file contents
    """
    try:
        logging.info(f"load_prompt: loading '{prompt_name}'")

        if prompt_name not in llm_const.LLM_PROMPT_FILES:
            raise FileNotFoundError(
                messages.MSG_UNKNOWN_PROMPT_NAME.format(
                    name=prompt_name,
                    known=list(llm_const.LLM_PROMPT_FILES.keys()),
                )
            )

        filename = llm_const.LLM_PROMPT_FILES[prompt_name]
        path = os.path.join(
            paths_const.DATA_ASSETS_DIR,
            paths_const.PROMPTS_DIR,
            filename,
        )

        if not os.path.exists(path):
            raise FileNotFoundError(
                messages.MSG_PROMPT_NOT_FOUND.format(name=prompt_name, path=path)
            )

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        logging.info(f"load_prompt: done — {len(content)} chars")
        return content

    except Exception as e:
        raise HackDataException(e, sys)
