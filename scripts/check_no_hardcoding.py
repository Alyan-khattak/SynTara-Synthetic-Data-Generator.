#!/usr/bin/env python3
# =============================================================================
# scripts/check_no_hardcoding.py
# =============================================================================
# Enforces TRD section 16: no hard-coded paths, magic numbers, messages,
# layer violations, or external calls outside cloud/.
#
# Usage:  python scripts/check_no_hardcoding.py   (run from repo root)
# Exit:   0 = PASS,  1 = violations found
# Suppress a line with:  # noqa: hardcode  <reason>
###===========================================================================
import ast
import os
import sys
from pathlib import Path

# Directories scanned relative to the repo root.
# Missing directories are silently skipped so the script passes on a partial tree.
SCAN_DIRS = [
    "hackdata/components",
    "hackdata/utils",
    "hackdata/pipeline",
    "hackdata/cloud",
    "api",
]

# Layer order from TRD section 3.  A file may only import from layers at the
# same index or lower (further left).  Higher index = later in the pipeline.
LAYER_ORDER = [
    "hackdata.constants",
    "hackdata.exception",
    "hackdata.logging",
    "hackdata.entity",
    "hackdata.utils",
    "hackdata.cloud",
    "hackdata.components",
    "hackdata.modules",
    "hackdata.pipeline",
    "api",
]

# String patterns that suggest a hard-coded file path
_PATH_PATS = ("/", "\\", ".csv", ".json", ".pkl", ".yaml", ".log")

# Call names whose first positional argument must not be a literal path
_PATH_FUNCS = frozenset(
    ["open", "read_csv", "read_json", "read_pickle", "to_csv", "to_json", "to_pickle", "join"]
)

_OK_NUMS = {0, 1, -1, 2}           # numeric literals that are never magic numbers
_EXTERNAL_LIBS = ("httpx", "requests")
_PROVIDER_URLS = ("api.groq.com", "openrouter.ai")


def _layer_index(rel_path: str) -> int:
    """Return the LAYER_ORDER index for the given relative file path, or -1."""
    # IMP: wrap path in slashes so "api" doesn't match inside "hackdata/api.py"
    fp = "/" + rel_path.replace("\\", "/") + "/"
    for i, layer in enumerate(LAYER_ORDER):
        if "/" + layer.replace(".", "/") + "/" in fp:
            return i
    return -1


def _check_file(abs_path: str, rel_path: str, violations: list) -> None:
    """Append FAIL strings to violations for every rule broken in one Python file."""
    try:
        source = Path(abs_path).read_text(encoding="utf-8")
    except OSError:
        return

    noqa = {i + 1 for i, ln in enumerate(source.splitlines()) if "# noqa: hardcode" in ln}

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError:
        return

    in_cloud = "/hackdata/cloud/" in "/" + rel_path.replace("\\", "/") + "/"
    file_layer = _layer_index(rel_path)

    def fail(lineno: int, msg: str) -> None:
        if lineno not in noqa:
            violations.append(f"FAIL: {rel_path}:{lineno}: {msg}")

    for node in ast.walk(tree):
        ln = getattr(node, "lineno", 0)

        # --- Check 1: literal path strings inside file-I/O function calls ---
        if isinstance(node, ast.Call):
            fname = (
                node.func.id if isinstance(node.func, ast.Name)
                else node.func.attr if isinstance(node.func, ast.Attribute)
                else None
            )
            if fname in _PATH_FUNCS:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if any(p in arg.value for p in _PATH_PATS):
                            fail(arg.lineno, f'hard-coded path literal "{arg.value}"')

        # --- Check 2: magic numbers in Compare, Slice, keyword arg, function default ---
        if isinstance(node, ast.Compare):
            for n in [node.left, *node.comparators]:
                if isinstance(n, ast.Constant) and type(n.value) in (int, float) and n.value not in _OK_NUMS:
                    fail(n.lineno, f"magic number {n.value} in comparison (use a constant)")

        if isinstance(node, ast.Slice):
            for n in filter(None, [node.lower, node.upper, node.step]):
                if isinstance(n, ast.Constant) and type(n.value) in (int, float) and n.value not in _OK_NUMS:
                    fail(n.lineno, f"magic number {n.value} in slice (use a constant)")

        if isinstance(node, ast.keyword):
            n = node.value
            if isinstance(n, ast.Constant) and type(n.value) in (int, float) and n.value not in _OK_NUMS:
                fail(n.lineno, f"magic number {n.value} in keyword arg (use a constant)")

        if isinstance(node, ast.arguments):
            for n in [*node.defaults, *[d for d in node.kw_defaults if d]]:
                if isinstance(n, ast.Constant) and type(n.value) in (int, float) and n.value not in _OK_NUMS:
                    fail(n.lineno, f"magic number {n.value} in function default (use a constant)")

        # --- Check 3: hard-coded messages > 40 chars in raise / logging.* ---
        if isinstance(node, ast.Raise) and node.exc:
            args = node.exc.args if isinstance(node.exc, ast.Call) else [node.exc]
            for arg in args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and len(arg.value) > 40:
                    fail(arg.lineno, "hard-coded message >40 chars in raise (use messages.py)")

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logging"
        ):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and len(arg.value) > 40:
                    fail(arg.lineno, "hard-coded message >40 chars in logging call (use messages.py)")

        # --- Check 4: layer violation — importing from a later layer ---
        if isinstance(node, ast.ImportFrom) and node.module and file_layer >= 0:
            for i, layer in enumerate(LAYER_ORDER):
                if node.module == layer or node.module.startswith(layer + "."):
                    if i > file_layer:
                        fail(ln, f"layer violation: '{node.module}' is layer {i} "
                                 f"but this file is layer {file_layer} ({LAYER_ORDER[file_layer]})")
                    break

        # --- Check 5: external HTTP libraries / provider URLs outside cloud/ ---
        if not in_cloud:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for mod in mods:
                    if any(lib in mod for lib in _EXTERNAL_LIBS):
                        fail(ln, f"external library '{mod}' imported outside hackdata/cloud/")

            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any(u in node.value for u in _PROVIDER_URLS):
                    fail(ln, "hard-coded provider URL outside hackdata/cloud/")


def main() -> None:
    # IMP: run from repo root; __file__ is scripts/check_no_hardcoding.py
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    violations: list = []

    for scan_dir in SCAN_DIRS:
        full_dir = os.path.join(repo_root, scan_dir)
        if not os.path.isdir(full_dir):
            continue  # missing dir = nothing to scan; stays clean until the code lands

        for dirpath, _, filenames in os.walk(full_dir):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                abs_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(abs_path, repo_root)
                _check_file(abs_path, rel_path, violations)

    if violations:
        for v in sorted(violations):
            print(v)
        sys.exit(1)

    print("PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
