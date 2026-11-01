#!/usr/bin/env python3
"""Triagem reproduzivel do roadmap; indicios nao sao homologacao."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
EXTENSIONS = {".py", ".sh", ".conf", ".ini", ".js", ".ts", ".tsx", ".jsx", ".sql"}
PATTERN = re.compile(r"\*\*(AXEF-\d{4})\*\*\s*[—-]\s*(.*?)\.\s*\*\*Status:")


def scan():
    roadmap = (ROOT / "docs/roadmap-100-funcionalidades-candidatas.md").read_text(encoding="utf-8")
    candidates = PATTERN.findall(roadmap)
    if len(candidates) != 100:
        raise ValueError(f"Esperados 100 candidatos; encontrados {len(candidates)}")
    sources = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in EXTENSIONS:
            continue
        if any(part in EXCLUDED for part in path.relative_to(ROOT).parts):
            continue
        if path.stat().st_size > 2_000_000:
            continue
        try:
            sources.append((str(path.relative_to(ROOT)), path.read_text(encoding="utf-8").lower()))
        except (OSError, UnicodeError):
            continue
    results = []
    for key, title in candidates:
        tokens = [t.lower() for t in re.findall(r"[A-Za-zÀ-ÿ0-9]+", title) if len(t) >= 6]
        matches = []
        for path, text in sources:
            if tokens and sum(token in text for token in tokens) >= min(2, len(tokens)):
                matches.append(path)
        results.append({"id": key, "titulo": title, "status": "REVISAR_MANUALMENTE", "indicios": matches[:12]})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--saida", help="Arquivo JSON opcional")
    args = parser.parse_args()
    result = scan()
    report = json.dumps({"total": len(result), "candidatos": result}, ensure_ascii=False, indent=2)
    if args.saida:
        Path(args.saida).write_text(report + "\n", encoding="utf-8")
    else:
        print(report)


if __name__ == "__main__":
    main()
