"""Regras comuns dos relatórios locais AXE PABX, sem rede ou APIs públicas.

Dados são tratados apenas após seleção exata do tenant. A ferramenta local
não substitui autenticação, autorização nem auditoria no backend HTTP.
"""
from datetime import date
import json
import math
from pathlib import Path
import re
import stat

TENANT_RE = re.compile(r"t[1-9][0-9]*\Z")
AGENT_RE = re.compile(r"(t[1-9][0-9]*)-[a-z0-9_-]{1,75}\Z")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
MAX_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 20000


def require_tenant(tenant):
    if not isinstance(tenant, str) or not TENANT_RE.fullmatch(tenant):
        raise ValueError("tenant inválido")
    return tenant


def valid_day(value):
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def valid_seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    if value < 0 or value > 31 * 86400:
        return None
    return float(value)


def percent(part, total):
    if (type(part) not in (int, float) or type(total) not in (int, float)
            or not math.isfinite(part) or not math.isfinite(total)
            or total <= 0 or part < 0 or part > total):
        return 0.0
    return round(part * 100 / total, 1)


def tenant_rows(rows, tenant, *, from_agent=False):
    """Não aceita t1 como prefixo de t10; registros sem tenant são ignorados."""
    require_tenant(tenant)
    if not isinstance(rows, list) or len(rows) > MAX_RECORDS:
        raise ValueError("volume ou estrutura de registros inválido")
    selected = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if from_agent:
            agent = row.get("extension")
            match = AGENT_RE.fullmatch(agent) if isinstance(agent, str) else None
            if not match or match.group(1) != tenant:
                continue
        elif row.get("tenant") != tenant:
            continue
        selected.append(dict(row))
    return selected


def _unique_keys(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("campo JSON repetido")
        output[key] = value
    return output


def _parse(line):
    return json.loads(
        line, object_pairs_hook=_unique_keys,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("número JSON inválido"))
    )


def read_local_records(filename, *, collection=False, keyed_entries=False):
    """Entrada local regular, pequena, sem symlink e sem executar comandos."""
    path = Path(filename)
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BYTES:
        raise ValueError("entrada precisa ser arquivo regular com até 16 MiB")
    if any(part.is_symlink() for part in path.parents):
        raise ValueError("diretório com link simbólico não permitido")
    raw = path.read_text(encoding="utf-8")
    if collection or keyed_entries:
        data = _parse(raw)
    else:
        lines = raw.splitlines()
        if len(lines) > MAX_RECORDS:
            raise ValueError("arquivo excede limite de registros")
        data = [_parse(line) for line in lines if line.strip()]
    if keyed_entries:
        if not isinstance(data, dict) or len(data) > MAX_RECORDS:
            raise ValueError("mapa de presenca invalido")
        result = []
        for key, entry in data.items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                raise ValueError("registro de presenca invalido")
            # Somente dados técnicos. Nunca carregar notas livres, que
            # podem conter dados pessoais, para o pipeline de métricas.
            result.append({"extension": key, "status": entry.get("status"),
                           "updated_at": entry.get("updated_at")})
        return result
    if not isinstance(data, list) or len(data) > MAX_RECORDS:
        raise ValueError("entrada precisa conter lista de registros")
    return data
