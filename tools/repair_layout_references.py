"""One-shot mechanical path migration; scientific result data are not rewritten."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
from urllib.parse import unquote, quote

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config/layout_migration_20260929.json"
MOVES = sorted(json.loads(PLAN.read_text(encoding="utf-8-sig"))["moves"], key=lambda m: -len(m["from"]))


def remap(path: str) -> str:
    for move in MOVES:
        if path == move["from"] or path.startswith(move["from"] + "/"):
            return move["to"] + path[len(move["from"]):]
    return path


def map_literal(value: str) -> str:
    normalized = value.replace("\\", "/")
    prefix = ROOT.as_posix() + "/"
    if normalized.startswith(prefix):
        mapped = prefix + remap(normalized[len(prefix):])
    elif re.match(r"^[A-Za-z]:/", normalized):
        return value
    else:
        mapped = remap(normalized)
    if "\\" in value and "/" not in value:
        mapped = mapped.replace("/", "\\")
    return mapped


def rewrite_joins(text: str) -> str:
    """Collapse literal project-root joins, excluding external backup roots/HERE."""
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def offset(line, byte_column):
        return starts[line - 1] + len(lines[line - 1].encode("utf-8")[:byte_column].decode("utf-8"))

    def flatten(node):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
            previous = flatten(node.left)
            if previous:
                return previous[0], previous[1] + [node.right.value]
        if isinstance(node, ast.Name) and node.id in {"ROOT", "PROJECT_ROOT", "project_root"}:
            return node.id, []
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Path" and len(node.args) == 1 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            return "Path", [node.args[0].value]
        return None

    changes = []
    for node in ast.walk(tree):
        result = flatten(node)
        if not result or not result[1]:
            continue
        base, parts = result
        old = "/".join(parts)
        new = map_literal(old)
        if new == old:
            continue
        start = offset(node.lineno, node.col_offset)
        end = offset(node.end_lineno, node.end_col_offset)
        replacement = f"Path({new!r})" if base == "Path" else f"{base} / {new!r}"
        changes.append((start, end, replacement))
    # Parents win over nested expressions; apply edits back to front.
    selected = []
    covered = -1
    for item in sorted(changes, key=lambda c: (c[0], -c[1])):
        if item[0] >= covered:
            selected.append(item)
            covered = item[1]
    for start, end, replacement in reversed(selected):
        text = text[:start] + replacement + text[end:]
    return text


def rewrite_mentions(text: str) -> str:
    variants = {}
    for move in MOVES:
        for sep in ("/", "\\", "\\\\"):
            old = move["from"].replace("/", sep)
            new = move["to"].replace("/", sep)
            # A single-component source such as ``analysis_out`` contains no
            # separator from which to infer a style. Keep the first (POSIX)
            # spelling so generated paths remain portable.
            variants.setdefault(old, new)
    alternatives = "|".join(re.escape(p) for p in sorted(variants, key=len, reverse=True))
    # Match repository-rooted paths, not D:/Lab/results or com.comsol imports.
    pattern = re.compile(r"(?<![\w./\\-])(" + alternatives + r")(?=[/\\])")
    text = pattern.sub(lambda m: variants[m[1]], text)
    for sep in ("/", "\\", "\\\\"):
        prefix = str(ROOT).replace("\\", sep) + sep
        for move in MOVES:
            old = prefix + move["from"].replace("/", sep)
            new = prefix + move["to"].replace("/", sep)
            text = re.sub(re.escape(old) + r"(?=[/\\\"'`<>\s]|$)", lambda _: new, text)
    # This is a directory-valued default, not a scientific label.
    text = text.replace('"analysis_out"', '"analysis/legacy_pipeline"').replace("'analysis_out'", "'analysis/legacy_pipeline'")
    return text


def rewrite_links(text: str, old_name: str, new_name: str) -> str:
    def replace(match):
        raw = match[1]
        angle = raw.startswith("<") and raw.endswith(">")
        target = unquote(raw[1:-1] if angle else raw)
        if re.match(r"^(https?://|mailto:|#|codex:)", target):
            return match[0]
        path, marker, fragment = target.partition("#")
        if re.match(r"^[A-Za-z]:[/\\]", path):
            new = map_literal(path)
        else:
            original = posixpath.normpath(posixpath.join(posixpath.dirname(old_name), path))
            if original.startswith("../"):
                return match[0]
            destination = remap(original)
            new = posixpath.relpath(destination, posixpath.dirname(new_name) or ".")
        if marker:
            new += marker + fragment
        if "%" in raw:
            new = quote(new, safe="/:#%")
        if angle:
            new = "<" + new + ">"
        return "](" + new + ")"
    return re.sub(r"\]\((<[^>\n]+>|[^)\n]+)\)", replace, text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest = ROOT / "local/migration_20260929/reference_updates.json"
    if args.apply and manifest.exists():
        raise SystemExit("References already migrated; refusing a second rewrite.")
    old_paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    rows = []
    for old in old_paths:
        if not old:
            continue
        new = remap(old)
        path = ROOT / new
        if not path.is_file() or new.startswith(("archive/", "local/", "docs/repository/", "tools/")):
            continue
        suffix = path.suffix.lower()
        if suffix not in {".py", ".java", ".ps1", ".sh", ".bat", ".tex", ".md", ".html"}:
            continue
        original = path.read_bytes()
        try:
            text = original.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        if suffix == ".py":
            text = rewrite_joins(text)
        if suffix == ".md":
            text = rewrite_links(text, old, new)
        text = rewrite_mentions(text)
        updated = (b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b"") + text.encode("utf-8")
        if updated == original:
            continue
        rows.append({"old_path": old, "path": new, "old_sha256": hashlib.sha256(original).hexdigest(), "new_sha256": hashlib.sha256(updated).hexdigest()})
        if args.apply:
            backup = ROOT / "local/migration_20260929/before_references" / old
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(original)
            path.write_bytes(updated)
    if args.apply:
        manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"changed_files": len(rows), "applied": args.apply, "files": [r["path"] for r in rows]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
