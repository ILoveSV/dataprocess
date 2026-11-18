"""Check the planning cleanup, chapter citations, reading copy, and preview."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit
import zipfile

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
THESIS = ROOT / 'thesis/history/thesis_latex'
SNAPSHOT = ROOT / 'archive/snapshots/thesis_planning_20260926'


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def main():
    manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8-sig"))
    with zipfile.ZipFile(SNAPSHOT / "before_update.zip") as archive:
        for entry in manifest:
            data = archive.read(entry["path"])
            assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["path"]
            if entry["action"] == "retire_after_verification":
                assert not (ROOT / entry["path"]).exists(), entry["path"]
    master = ROOT / "docs/论文总体判断与写作主线.md"
    text = master.read_text(encoding="utf-8")
    chapters = re.findall(r"### 第([一二三四五六])章：([^\n]+)\n(.*?)(?=\n### 第|\n## 5\.)", text, re.S)
    assert len(chapters) == 6
    counts = {f"第{number}章 {title}": len(re.sub(r"\s", "", body)) for number, title, body in chapters}
    assert all(400 <= count <= 500 for count in counts.values()), counts

    source = (THESIS / "chapters/chapter01_introduction.tex").read_text(encoding="utf-8")
    references = (THESIS / "references.tex").read_text(encoding="utf-8")
    keys = re.findall(r"\\bibitem\{([^}]+)\}", references)
    cites = [key for group in re.findall(r"\\cite\{([^}]+)\}", source) for key in group.split(",")]
    assert list(dict.fromkeys(cites)) == keys
    assert len(keys) == 11 and len(set(keys)) == len(keys)
    reading = THESIS / "第一章_绪论_初稿_20260926.md"
    reading_text = reading.read_text(encoding="utf-8")
    assert "\\cite" not in reading_text and "[@" not in reading_text
    assert "## 1.6 本章小结" in reading_text
    assert "\\[11\\] CAWLEY" in reading_text
    reference_part = reading_text.split("## 参考文献\n", 1)[1]
    assert len(re.findall(r"^\\\[\d+\\\] ", reference_part, re.M)) == 11

    active_docs = [
        master, ROOT / "PROJECT_STATE.md", ROOT / "docs/README.md",
        SNAPSHOT / "README.md", THESIS / "README.md", reading,
        THESIS / "第一章_文献核查与待补项_20260926.md",
    ]
    local_links = 0
    for path in active_docs:
        proc = subprocess.run(["pandoc", str(path), "--from=gfm", "--to=json"], check=True, capture_output=True, encoding="utf-8")
        for node in walk(json.loads(proc.stdout)):
            if node.get("t") == "Link":
                url = node["c"][-1][0]
                if not url or url.startswith("#") or urlsplit(url).scheme:
                    continue
                target = (path.parent / unquote(url.split("#", 1)[0])).resolve()
                assert target.exists(), f"Broken local link in {path.name}: {url}"
                local_links += 1

    log = (ROOT / 'local/tmp/pdfs/chapter01_20260926/chapter01_preview.log').read_text(encoding="utf-8", errors="replace")
    for token in ["Overfull \\hbox", "Overfull \\vbox", "Missing character:", "There were undefined references", "! LaTeX Error"]:
        assert token not in log, token
    pdf = ROOT / 'thesis/history/exports/第一章_绪论_初稿_20260926.pdf'
    reader = PdfReader(pdf)
    assert len(reader.pages) == 11
    assert all(len(page.extract_text().strip()) > 100 for page in reader.pages)
    pdf_text = "".join(page.extract_text() for page in reader.pages)
    assert "[?]" not in pdf_text
    assert "ICCP" in pdf_text and "CAWLEY" in pdf_text
    report = {
        "status": "pass",
        "snapshot_entries_sha256_verified": len(manifest),
        "retired_active_plans": sum(item["action"] == "retire_after_verification" for item in manifest),
        "chapter_outline_nonwhitespace_counts": counts,
        "chapter_one_han_characters": len(re.findall(r"[\u4e00-\u9fff]", source)),
        "references": len(keys),
        "checked_local_links": local_links,
        "pdf_pages": len(reader.pages),
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "remaining_typesetting_warnings": "Existing template font fallback, underfull vbox, unused figure/table captions, and local TeX version notices; visually reviewed separately.",
    }
    (SNAPSHOT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
