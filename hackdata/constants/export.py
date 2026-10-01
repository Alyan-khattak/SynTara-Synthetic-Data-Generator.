# ═══════════════════════════════════════════════════════════════════
# export.py — formats, SQL dialect, hash algorithm
# ═══════════════════════════════════════════════════════════════════

EXP_FORMATS: tuple = ("csv", "json", "sql", "pdf")
EXP_SQL_DIALECT: str = "postgresql"                # ASSUMED; change if target DB differs
EXP_HASH_ALGORITHM: str = "sha256"
EXP_HASH_FILE_CHUNK_BYTES: int = 65536  # 64 KB; keeps RAM flat on large files
EXP_CSV_LINE_TERMINATOR: str = "\n"
EXP_CSV_ENCODING: str = "utf-8"
EXP_JSON_INDENT: int = 2
