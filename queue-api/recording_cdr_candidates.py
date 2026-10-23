"""Gera APENAS propostas de catálogo a partir de evidências CDR AMI.

NÃO publica políticas de acesso. Exige acordo entre AccountCode,
DestinationContext, DestinationChannel e campos exatos do arquivo.
CDR sem vínculo confiável ou disputado entre tenants não é elegível.
"""
import argparse
import json
import re
import stat
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from recording_catalog import SOURCE_REF, EXTENSION
from recording_access import TENANT, _valid_filename

CDR_LIMIT_BYTES = 4 * 1024 * 1024
CDR_LIMIT_ROWS = 10000
RECORDING_RE = re.compile(
    r"^(?P<date>\d{8})-(?P<hour>\d{6})-(?P<caller>\d{3,15})-"
    r"(?:(?P<tag>t[1-9][0-9]*)-)?(?P<destination>\d{3,6})\.(?:wav|gsm|mp3)$"
)
UNIQUE_ID = re.compile(r"^[0-9]{10,14}\.[0-9]{1,12}$")
CHANNEL_RE = re.compile(r"^PJSIP/(?P<operator>t[1-9][0-9]*-[a-z0-9_-]+)-[a-fA-F0-9]+$")


def load_raw_cdr(path):
    """Aceita somente exportação local JSONL regular, sem links ou conteúdo gigante."""
    source = Path(path)
    info = source.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > CDR_LIMIT_BYTES:
        raise ValueError("CDR deve ser arquivo regular e até 4 MiB")
    data = source.read_bytes()
    if len(data) > CDR_LIMIT_BYTES:
        raise ValueError("CDR ultrapassa limite")
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("CDR sem codificação UTF-8") from exc
    lines = text.splitlines()
    if not lines or len(lines) > CDR_LIMIT_ROWS:
        raise ValueError("CDR vazio ou excede 10000 registros")
    events = []
    for line_no, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"linha CDR {line_no} contém JSON inválido") from exc
        if not isinstance(row, dict):
            raise ValueError(f"linha CDR {line_no} não é objeto")
        events.append(row)
    return events


def corroborate_cdr(event):
    """Não usa tenant enviado em parâmetro, nome de arquivo ou prefixo isolado."""
    if not isinstance(event, dict) or event.get("Event") != "Cdr":
        return None
    if event.get("Disposition") != "ANSWERED":
        return None
    tenant = event.get("AccountCode")
    if not isinstance(tenant, str) or not TENANT.fullmatch(tenant):
        return None
    if event.get("DestinationContext") != tenant + "-internal":
        return None
    match = CHANNEL_RE.fullmatch(event.get("DestinationChannel") or "")
    if not match:
        return None
    operator = match["operator"]
    if not operator.startswith(tenant + "-") or not EXTENSION.fullmatch(operator):
        return None
    source_ref = event.get("UniqueID")
    if not isinstance(source_ref, str) or not UNIQUE_ID.fullmatch(source_ref):
        return None
    ref = "CDR:" + source_ref
    if not SOURCE_REF.fullmatch(ref):
        return None
    caller = event.get("CallerIDNum")
    dest = event.get("Destination")
    if not isinstance(caller, str) or not re.fullmatch(r"\d{3,15}", caller):
        return None
    if not isinstance(dest, str) or not re.fullmatch(r"\d{3,6}", dest):
        return None
    timestamp = event.get("StartTime")
    if not isinstance(timestamp, str):
        return None
    try:
        parsed = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        if parsed.strftime("%Y-%m-%d %H:%M:%S") != timestamp:
            return None
    except ValueError:
        return None
    return {
        "match": (parsed.strftime("%Y%m%d-%H%M%S"), caller, dest),
        "tenant": tenant,
        "owner_extension": operator,
        "source_ref": ref,
    }


def propose_candidates(recordings_dir, cdr_events):
    """Retorna (manifesto, resumo). Ambiguidades são sempre descartadas."""
    root = Path(recordings_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("diretório de gravações inválido")
    by_call = defaultdict(list)
    for raw in cdr_events:
        valid = corroborate_cdr(raw)
        if valid is not None:
            by_call[valid["match"]].append(valid)

    rows = []
    ambiguous = unmatched = skipped = 0
    for audio in sorted(root.iterdir(), key=lambda item: item.name):
        if audio.is_symlink() or not audio.is_file() or not _valid_filename(audio.name):
            skipped += 1
            continue
        filename = RECORDING_RE.fullmatch(audio.name)
        if filename is None:
            skipped += 1
            continue
        parts = filename.groupdict()
        key = (parts["date"] + "-" + parts["hour"], parts["caller"], parts["destination"])
        matches = by_call.get(key, [])
        # Arquivos com tag de tenant também são descartados se houver
        # evidências contraditórias de outra empresa para a mesma chamada.
        if len(matches) > 1:
            ambiguous += 1
            continue
        if not matches or (parts["tag"] is not None and parts["tag"] != matches[0]["tenant"]):
            unmatched += 1
            continue
        match = matches[0]
        rows.append({
            "filename": audio.name, "tenant": match["tenant"],
            "owner_extension": match["owner_extension"],
            "source_ref": match["source_ref"],
        })
    return rows, {
        "proposed": len(rows), "ambiguous": ambiguous,
        "without_evidence": unmatched, "unsupported": skipped,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Propostas de vínculo áudio/CDR; não concede acesso")
    parser.add_argument("--recordings-dir", required=True)
    parser.add_argument("--cdr-jsonl", required=True, help="exportação CDR AMI de origem confiável")
    parser.add_argument("--output", required=True, help="arquivo JSONL novo para revisão")
    args = parser.parse_args(argv)
    output = Path(args.output)
    try:
        if output.is_symlink() or output.exists():
            raise ValueError("o destino precisa ser novo; não sobrescreve arquivos")
        events = load_raw_cdr(args.cdr_jsonl)
        candidates, summary = propose_candidates(args.recordings_dir, events)
        # O manifesto contém nomes e números telefônicos: somente
        # arquivo criado com permissão 0600; nunca imprimir dados no log.
        import os
        descriptor = os.open(str(output), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            for candidate in candidates:
                handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, ValueError) as exc:
        parser.exit(2, "Proposta recusada: " + str(exc) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
