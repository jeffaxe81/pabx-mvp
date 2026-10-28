#!/usr/bin/env python3
"""Gate offline de homologação: evidencia decisões, não executa telefonia.

Recebe um registro preenchido por operador e calcula cobertura. Nunca
interprete aprovação declarada como prova automática de chamada real.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCENARIOS = (
    ("sip_tls_transport", "Transporte SIP/TLS e certificado confiável"),
    ("sip_registration", "Registro SIP de dois ramais autorizados"),
    ("internal_call", "Chamada interna completa"),
    ("rtp_two_way", "RTP com áudio nos dois sentidos"),
    ("srtp_encryption", "SRTP ativo e negociado"),
    ("did_known", "DID conhecido roteado ao tenant correto"),
    ("did_unknown", "DID desconhecido rejeitado"),
    ("tenant_isolation", "Isolamento entre tenants e gravações"),
    ("queue_ura", "URA, filas e tempo de espera"),
    ("attended_transfer", "Transferência assistida e retorno"),
    ("recordings", "Gravações recuperáveis e autorização de acesso"),
    ("backup_restore", "Backup, restauração e integridade"),
    ("failover", "Contingência e recuperação testadas"),
)
VALID_STATES = {"pending", "passed", "failed", "blocked"}


def reject_duplicate_keys(pairs):
    """Objetos JSON com chaves repetidas não podem contar como evidência."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON de homologação com chave duplicada")
        result[key] = value
    return result
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
MAX_HOMOLOGATION_BYTES = 1024 * 1024


def summarize(payload):
    """Falha fechado em dados incompletos, estados ou evidências inválidos."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("schema_version deve ser 1")
    commit = payload.get("source_commit")
    if not isinstance(commit, str) or not SHA_RE.fullmatch(commit):
        raise ValueError("source_commit deve ser um SHA Git completo de 40 hex")
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        raise ValueError("checks deve ser um objeto JSON")
    expected = {key for key, _ in SCENARIOS}
    if set(checks) != expected:
        raise ValueError("checks deve conter exatamente os 13 cenários previstos")

    rows = []
    counts = {name: 0 for name in VALID_STATES}
    for key, title in SCENARIOS:
        record = checks[key]
        if not isinstance(record, dict):
            raise ValueError(f"{key}: registro inválido")
        state = record.get("status")
        if state not in VALID_STATES:
            raise ValueError(f"{key}: status desconhecido")
        evidence = record.get("evidence", "")
        if not isinstance(evidence, str) or len(evidence) > 180:
            raise ValueError(f"{key}: referência de evidência inválida")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in evidence):
            raise ValueError(f"{key}: evidência com caracteres de controle")
        if state == "passed" and not evidence.strip():
            raise ValueError(f"{key}: aprovação requer referência de evidência")
        counts[state] += 1
        rows.append({"id": key, "title": title, "status": state,
                     "evidence": evidence.strip()})
    total = len(SCENARIOS)
    return {
        "schema_version": 1,
        "source_commit": commit.lower(),
        "total": total,
        "counts": counts,
        "coverage_percent": round(counts["passed"] * 100 / total, 1),
        "gate_ready": counts["passed"] == total,
        "real_calls_executed_by_this_tool": False,
        "checks": rows,
    }


def to_markdown(report):
    """Relatório textual, com IDs de evidência, sem credenciais."""
    lines = [
        "# Gate de homologação AXE PABX",
        "",
        f"Commit: \x60{report['source_commit']}\x60",
        f"Cobertura declarada: **{report['coverage_percent']:.1f}%** "
        f"({report['counts']['passed']}/{report['total']})",
        f"Decisão: **{'APTO PARA REVISÃO DE GO' if report['gate_ready'] else 'BLOQUEADO'}**",
        "",
        "| Cenário | Estado | Referência de evidência |",
        "|---|---|---|",
    ]
    for item in report["checks"]:
        evidence = item["evidence"].replace("|", "\\|")
        title = item["title"].replace("|", "\\|")
        lines.append(f"| {title} | {item['status']} | {evidence or '—'} |")
    lines += ["", "Apenas registra informações fornecidas pelo operador; "
              "não executa chamadas nem verifica a autenticidade das evidências."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True,
                        help="Registro JSON de resultados preenchido no laboratório")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        source = Path(args.file)
        if source.is_symlink() or not source.is_file():
            raise ValueError("arquivo de evidências ausente ou link simbólico")
        if source.stat().st_size > MAX_HOMOLOGATION_BYTES:
            raise ValueError("arquivo de evidências excede limite seguro")
        payload = json.loads(source.read_text(encoding="utf-8"),
                             object_pairs_hook=reject_duplicate_keys)
        report = summarize(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"Registro de homologação inválido: {exc}", file=sys.stderr)
        return 2
    if args.format == "markdown":
        sys.stdout.write(to_markdown(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["gate_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
