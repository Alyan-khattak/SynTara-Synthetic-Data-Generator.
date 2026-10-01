# ═══════════════════════════════════════════════════════════════════
# llm.py — model IDs, URLs, limits, cooldowns, prompt file names
# ═══════════════════════════════════════════════════════════════════
# IMP: model IDs confirmed by bake-off (scripts/model_bakeoff.py, 2026-10-01).
#      Both models are open-weight, Apache 2.0, served on Groq.
#      Nothing outside cloud/ should import this module.

LLM_GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

# Bake-off winner (5/5 valid, avg 2.1 s) — openai/gpt-oss-120b, Apache 2.0
LLM_MODEL_SPEC_PRIMARY: str = "openai/gpt-oss-120b"
# Bake-off backup (4/5 valid, avg 1.6 s) — openai/gpt-oss-20b, Apache 2.0
LLM_MODEL_SPEC_BACKUP: str = "openai/gpt-oss-20b"

# ponytail: flat two-model chain; add more open-weight models here if needed
LLM_MODEL_FALLBACK_CHAIN: tuple = (LLM_MODEL_SPEC_PRIMARY, LLM_MODEL_SPEC_BACKUP)

LLM_TIMEOUT_SECONDS: float = 30.0
LLM_MAX_REPAIR_RETRIES: int = 1
LLM_KEY_COOLDOWN_SECONDS: int = 60
LLM_POOL_CALL_SPACING_SECONDS: float = 2.0
LLM_CALLS_PER_QUERY_MAX: int = 4
LLM_CACHE_KEY_ALGORITHM: str = "sha256"
LLM_HTTP_STATUS_RATE_LIMIT: int = 429       # kept for reference; SDK raises RateLimitError now
LLM_CACHE_KEY_DISPLAY_LEN: int = 8          # chars shown in log messages for cache keys
LLM_PROMPT_FILES: dict = {
    "spec": "spec_prompt.txt",
    "pool": "pool_prompt.txt",
    "narrative": "narrative_prompt.txt",
    "repair": "repair_prompt.txt",
}

# ── Jev (TypeSafe AI) ────────────────────────────────────────────────
LLM_JEV_VALID_THRESHOLD: float = 0.40
LLM_JEV_MODEL: str = "jev-1"   # VERIFY: update to latest from docs.typesafe.ai/models
