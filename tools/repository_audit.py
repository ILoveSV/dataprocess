"""Check Git candidates without modifying data, staging files, or running analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = "docs/repository/sync_manifest_20260928.json"
BLOCKED_SUFFIXES = {
    ".tdms", ".tdms_index", ".npy", ".npz", ".pkl", ".pickle", ".joblib",
    ".h5", ".hdf5", ".mph", ".class", ".pptx", ".ppt", ".docx", ".doc",
    ".wav", ".m4a", ".mp3", ".mp4", ".mov", ".avi", ".pem", ".key",
}
TEXT_SUFFIXES = {
    ".py", ".ps1", ".sh", ".bat", ".md", ".txt", ".json", ".yaml",
    ".yml", ".toml", ".ini", ".tex", ".bib", ".java", ".lua", ".csv",
    ".html", ".js", ".gitignore",
}
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b"),
)


def git_paths(*args: str) -> list[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z", *args], cwd=ROOT)
    return [part.decode("utf-8") for part in raw.split(b"\0") if part]


def path_errors(path: str, size: int) -> list[str]:
    p = Path(path)
    reasons = []
    if p.suffix.lower() in BLOCKED_SUFFIXES or ".mph." in p.name:
        reasons.append("local-only artifact")
    if p.name == ".env" or (p.name.startswith(".env.") and p.name != ".env.example"):
        reasons.append("environment file")
    if {".ssh", "__pycache__", "build", "tmp", ".codex_tmp"}.intersection(p.parts):
        reasons.append("private/cache/build directory")
    if p.name == "COMPLETE" and p.parts[0] == "results":
        reasons.append("partial archive must not claim completeness")
    limit = 2 * 1024**2 if p.parts[0] == "analysis_out" else 25 * 1024**2
    if size > limit:
        reasons.append(f"file exceeds {limit // 1024**2} MiB review limit")
    return reasons


def audit(include_untracked: bool) -> dict:
    paths = set(git_paths("--cached"))
    if include_untracked:
        paths.update(git_paths("--others", "--exclude-standard"))
    rows, issues = [], []
    for name in sorted(paths):
        if name == DEFAULT_MANIFEST:
            continue  # A manifest cannot contain its own content hash.
        path = ROOT / name
        if not path.is_file():
            continue  # Deletions are reviewed through Git's staged diff.
        size = path.stat().st_size
        reasons = path_errors(name, size)
        if reasons:
            issues.append({"path": name, "reasons": reasons})
            continue
        data = path.read_bytes()
        if path.suffix.lower() in TEXT_SUFFIXES or path.name == ".gitignore":
            if any(pattern.search(data) for pattern in SECRET_PATTERNS):
                issues.append({"path": name, "reasons": ["possible embedded credential; value not printed"]})
        rows.append({"path": name, "bytes": size, "sha256": hashlib.sha256(data).hexdigest()})
    groups = {}
    for row in rows:
        group = row["path"].split("/")[0] if "/" in row["path"] else "(root)"
        totals = groups.setdefault(group, {"files": 0, "bytes": 0})
        totals["files"] += 1
        totals["bytes"] += row["bytes"]
    return {
        "scope": "current working-tree content of indexed files" + (" plus unignored new files" if include_untracked else ""),
        "manifest_self_excluded": DEFAULT_MANIFEST,
        "limits": "25 MiB per file; 2 MiB under analysis_out; raw/binary archives excluded",
        "security_limit": "High-confidence credential-pattern scan only; not a guarantee of absence of sensitive content.",
        "file_count": len(rows), "total_bytes": sum(r["bytes"] for r in rows),
        "groups": groups, "issues": issues, "files": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-only", action="store_true", help="Check indexed paths only; contents are read from disk.")
    parser.add_argument("--write-manifest", action="store_true", help="Write a reproducible path/size/SHA-256 inventory after successful checks.")
    args = parser.parse_args()
    result = audit(not args.index_only)
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, ensure_ascii=False, indent=2))
    if result["issues"]:
        return 1
    if args.write_manifest:
        target = ROOT / DEFAULT_MANIFEST
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
