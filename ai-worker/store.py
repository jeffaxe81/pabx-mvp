"""
Armazena o resultado do processamento de IA (transcrição, resumo,
sentimento) de cada gravação. JSONL, mesmo padrão de call_log.jsonl
(queue-api/reports.py) e survey.jsonl (queue-api/survey.py).
"""
import json
from pathlib import Path


class TranscriptStore:
    def __init__(self, path):
        self.path = Path(path)

    def append(self, record: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_all(self) -> list:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def find_by_filename(self, filename: str):
        return next((r for r in self.load_all() if r.get("filename") == filename), None)

    def already_processed(self, filename: str) -> bool:
        return self.find_by_filename(filename) is not None
