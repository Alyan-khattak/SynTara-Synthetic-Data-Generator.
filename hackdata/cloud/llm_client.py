# ═══════════════════════════════════════════════════════════════════
# llm_client.py — one public interface for all LLM calls
# ═══════════════════════════════════════════════════════════════════
# The ONLY file in the project that imports the groq SDK or knows provider URLs.
# IMP: nothing outside cloud/ may import this module.
###==============================================================
import json
import sys
from typing import Optional, Type

import groq as groq_sdk
from pydantic import BaseModel

from hackdata.constants import llm as llm_const, common, messages, generation as gen_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging
from hackdata.utils.main_utils.hash_utils import sha256_text
from hackdata.utils.main_utils.env_utils import get_groq_keys
from hackdata.cloud.key_pool import KeyPool
from hackdata.cloud.llm_cache import get as cache_get, put as cache_put
from hackdata.cloud.prompt_loader import load_prompt
from hackdata.cloud.offline_fallback import build_offline_spec

# IMP: KeyPool initialised once at module load — reads GROQ_API_KEYS from env.
#      An empty list is fine; next_key() returns None and _try_model skips Groq.
_KEY_POOL: KeyPool = KeyPool(get_groq_keys())


# ════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ════════════════════════════════════════════════════════

def _build_cache_key(prompt_name: str, variables: dict) -> str:
    """Build a stable cache key: sha256 of 'prompt_name|prompt_hash|canonical_json(variables)'.

    Prompt content is hashed so editing a prompt template auto-invalidates
    its cached responses without requiring a manual cache wipe.
    """
    canonical = json.dumps(variables, sort_keys=True, ensure_ascii=False)
    # ponytail: load_prompt is a short file read; acceptable on every cache-key build
    try:
        prompt_text = load_prompt(prompt_name)
        prompt_hash = sha256_text(prompt_text)[:8]
    except Exception:
        prompt_hash = "0"
    return sha256_text(f"{prompt_name}|{prompt_hash}|{canonical}")


def _fill_template(template: str, variables: dict) -> str:
    """Substitute {key} placeholders in a prompt template.

    Uses str.format_map so missing keys raise KeyError (fail-fast).
    """
    return template.format_map(variables)


def _try_model(model: str, messages_list: list, as_json: bool) -> Optional[str]:
    """Try one Groq model, rotating keys on rate-limit or timeout. Return content or None.

    Uses the official groq SDK. All models are served through Groq.

    # DRY RUN: model="openai/gpt-oss-120b", pool has [key1, key2], key1 → 429
    #   groq.Groq(api_key=key1) → RateLimitError → mark_cooldown(key1)
    #   groq.Groq(api_key=key2) → success → return content
    """
    try:
        rf = {"type": "json_object"} if as_json else None
        while True:
            key = _KEY_POOL.next_key()
            if key is None:
                logging.info(f"_try_model: all Groq keys cooling — model={model}")
                return None
            try:
                client = groq_sdk.Groq(api_key=key)
                kwargs = dict(
                    model=model,
                    messages=messages_list,
                    temperature=0,
                    timeout=llm_const.LLM_TIMEOUT_SECONDS,
                )
                if rf is not None:
                    kwargs["response_format"] = rf
                resp = client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content
            except groq_sdk.RateLimitError:
                _KEY_POOL.mark_cooldown(key)
                continue  # try next key
            except groq_sdk.APITimeoutError:
                _KEY_POOL.mark_cooldown(key)
                continue  # timeout treated the same as rate-limit
    except Exception as e:
        raise HackDataException(e, sys)


def _call_with_fallback(
    prompt_name: str,
    messages_list: list,
    as_json: bool,
) -> Optional[str]:
    """Try each model in LLM_MODEL_FALLBACK_CHAIN; return first success or None.

    # DRY RUN: fallback_chain = (model_a, model_b)
    #   model_a → all Groq keys cooling → None
    #   model_b → key2 returns 200 → return content
    """
    for model in llm_const.LLM_MODEL_FALLBACK_CHAIN:
        result = _try_model(model, messages_list, as_json)
        if result is not None:
            logging.info(f"_call_with_fallback: success model={model}")
            return result
    logging.info(f"_call_with_fallback: all models exhausted prompt={prompt_name}")
    return None


def _repair_json(broken_text: str, error_text: str) -> Optional[str]:
    """Ask the LLM to fix broken JSON. Returns repaired string or None.

    # IMP: this is best-effort; a failure here does NOT propagate — the caller
    #      falls through to offline_fallback instead.
    """
    try:
        repair_template = load_prompt("repair")
        filled = _fill_template(
            repair_template,
            {"broken_json": broken_text, "error": error_text},
        )
        return _call_with_fallback("repair", [{"role": "user", "content": filled}], as_json=True)
    except Exception:
        # ponytail: swallow repair failure — caller has the offline path as last resort
        logging.info("_repair_json: repair attempt failed, continuing to offline path")  # noqa: hardcode
        return None


# ════════════════════════════════════════════════════════
# PUBLIC API
# ════════════════════════════════════════════════════════

def ask_json(prompt_name: str, variables: dict, schema: Type[BaseModel]) -> dict:
    """LLM call that returns a validated JSON object.

    Flow:
    1. Build cache key from sha256(prompt_name + '|' + canonical_json(variables))
    2. Check disk cache → return on hit
    3. Load + fill prompt template
    4. Try each model in LLM_MODEL_FALLBACK_CHAIN (rotating Groq keys on rate-limit/timeout)
    5. Parse JSON; on failure, try one repair call (LLM_MAX_REPAIR_RETRIES)
    6. Validate with Pydantic schema; on total LLM failure, use offline_fallback
    7. Cache result and return

    Parameters
    ----------
    prompt_name : str
        Key in LLM_PROMPT_FILES, e.g. "spec".
    variables : dict
        Template substitution variables, e.g. {"query": "100 orders"}.
    schema : Type[BaseModel]
        Pydantic model class for response validation.

    Returns
    -------
    dict
        Validated response as a plain dict (from schema.model_dump()).

    Raises
    ------
    HackDataException
        When all LLMs fail and offline_fallback cannot satisfy the schema.

    # DRY RUN: ask_json("spec", {"query": "100 orders"}, Spec)
    #   cache_key = sha256('spec|{"query": "100 orders"}')
    #   cache miss → load spec_prompt.txt → fill {query}
    #   → POST to Groq → parse JSON → Spec(**result).model_dump()
    #   → cache_put(cache_key, result) → return dict
    """
    try:
        logging.info(f"ask_json: start prompt={prompt_name}")

        # Step 1-2 — cache lookup
        cache_key = _build_cache_key(prompt_name, variables)
        cached = cache_get(cache_key)
        if cached is not None:
            logging.info("ask_json: cache hit")
            return json.loads(cached)

        # Step 3 — build prompt
        template = load_prompt(prompt_name)
        filled = _fill_template(template, variables)
        messages_list = [{"role": "user", "content": filled}]

        # Step 4 — call LLM with model fallback
        raw = _call_with_fallback(prompt_name, messages_list, as_json=True)

        # Step 5 — parse JSON (one repair attempt on failure)
        parsed: Optional[dict] = None
        if raw is not None:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as parse_err:
                logging.info("ask_json: parse error — attempting repair")  # noqa: hardcode
                repaired = _repair_json(raw, str(parse_err))
                if repaired is not None:
                    try:
                        parsed = json.loads(repaired)
                    except json.JSONDecodeError:
                        parsed = None  # repair also produced invalid JSON

        # Step 6 — validate; fall back to offline_fallback if LLM produced nothing
        if parsed is None:
            logging.info("ask_json: LLM failed — using offline_fallback")  # noqa: hardcode
            query = variables.get("query", "")
            offline_dict = build_offline_spec(
                query,
                module=variables.get("module", common.MODULE_TABULAR),
                n_rows=variables.get("n_rows", gen_const.GEN_DEFAULT_N_ROWS),
            )
            try:
                result = schema(**offline_dict).model_dump()
            except Exception as validation_err:
                raise HackDataException(
                    Exception(messages.MSG_LLM_ALL_EXHAUSTED.format(prompt_name=prompt_name)),
                    sys,
                ) from validation_err
        else:
            result = schema(**parsed).model_dump()

        # Step 7 — cache and return
        cache_put(cache_key, json.dumps(result, sort_keys=True, ensure_ascii=False))
        logging.info("ask_json: done")
        return result

    except Exception as e:
        raise HackDataException(e, sys)


def ask_text(prompt_name: str, variables: dict, expect_json: bool = False) -> str:
    """LLM call that returns raw text (no JSON parsing or schema validation).

    Parameters
    ----------
    prompt_name : str
        Key in LLM_PROMPT_FILES, e.g. "narrative".
    variables : dict
        Template substitution variables.
    expect_json : bool
        When True, validate the response as JSON before caching.
        A non-JSON response is returned but not cached so the next call
        re-hits the LLM instead of replaying a bad cached value.

    Returns
    -------
    str
        Raw text from the LLM, or an empty string if all models fail.
    """
    try:
        logging.info(f"ask_text: start prompt={prompt_name}")

        cache_key = _build_cache_key(prompt_name, variables)
        cached = cache_get(cache_key)
        if cached is not None:
            # IMP: validate cached JSON responses — a previously bad response
            #      must not be replayed forever just because it was cached.
            if expect_json:
                try:
                    json.loads(cached)
                except (json.JSONDecodeError, ValueError):
                    logging.info(f"ask_text: cache has invalid JSON for {prompt_name} — evicting")
                    import os as _os
                    from hackdata.cloud.llm_cache import _cache_path
                    try:
                        _os.remove(_cache_path(cache_key))
                    except OSError:
                        pass
                    cached = None

            if cached is not None:
                logging.info("ask_text: cache hit")
                return cached

        template = load_prompt(prompt_name)
        filled = _fill_template(template, variables)
        messages_list = [{"role": "user", "content": filled}]

        raw = _call_with_fallback(prompt_name, messages_list, as_json=False)
        result = raw or ""

        if result:
            # IMP: only cache when response is valid JSON (for expect_json callers)
            if expect_json:
                try:
                    json.loads(result)
                    cache_put(cache_key, result)
                except (json.JSONDecodeError, ValueError):
                    logging.info(f"ask_text: skipping cache — invalid JSON from LLM for {prompt_name}")
            else:
                cache_put(cache_key, result)

        logging.info(f"ask_text: done {len(result)} chars")
        return result

    except Exception as e:
        raise HackDataException(e, sys)
