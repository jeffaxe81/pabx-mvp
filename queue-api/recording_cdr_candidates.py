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
from recordings import _recording_directory_fd
import os
from recording_access import (TENANT, _valid_filename, _reject_duplicate_json_keys,
                              read_regular_file_secure)

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
    data = read_regular_file_secure(path, CDR_LIMIT_BYTES)
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
            row = json.loads(
                line, object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    ValueError("número JSON não finito")),
            )
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
    channel = event.get("DestinationChannel")
    if not isinstance(channel, str):
        return None
    match = CHANNEL_RE.fullmatch(channel)
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
    directory_fd = _recording_directory_fd(recordings_dir)
    if directory_fd is None:
        raise ValueError("diretório de gravações inválido")
    by_call = defaultdict(list)
    for raw in cdr_events:
        valid = corroborate_cdr(raw)
        if valid is not None:
            by_call[valid["match"]].append(valid)

    rows = []
    ambiguous = unmatched = skipped = 0
    try:
        with os.scandir(directory_fd) as entries:
            names = sorted(entry.name for entry in entries)
        for name in names:
            if not _valid_filename(name):
                skipped += 1
                continue
            try:
                metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except (OSError, TypeError, ValueError):
                skipped += 1
                continue
            if not stat.S_ISREG(metadata.st_mode):
                skipped += 1
                continue
            filename = RECORDING_RE.fullmatch(name)
            if filename is None:
                skipped += 1
                continue
            parts = filename.groupdict()
            key = (parts["date"] + "-" + parts["hour"], parts["caller"], parts["destination"])
            matches = by_call.get(key, [])
            if len(matches) > 1:
                ambiguous += 1
                continue
            if not matches or (parts["tag"] is not None and parts["tag"] != matches[0]["tenant"]):
                unmatched += 1
                continue
            match = matches[0]
            rows.append({
                "filename": name, "tenant": match["tenant"],
                "owner_extension": match["owner_extension"],
                "source_ref": match["source_ref"],
            })
    finally:
        os.close(directory_fd)
    # Uma mesma prova CDR não pode classificar dois arquivos distintos
    # automaticamente. Nesses casos nenhum deles vira candidato;
    # exige-se revisão humana da correlação origem/áudio.
    by_source = defaultdict(list)
    for row in rows:
        by_source[row["source_ref"]].append(row)
    repeated_refs = {ref for ref, matches in by_source.items() if len(matches) > 1}
    if repeated_refs:
        ambiguous += sum(row["source_ref"] in repeated_refs for row in rows)
        rows = [row for row in rows if row["source_ref"] not in repeated_refs]
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
