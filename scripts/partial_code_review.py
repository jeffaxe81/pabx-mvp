#!/usr/bin/env python3
"""Auditoria local de escopos parciais: código, não telefonia nem GO.

Inspeciona símbolos Python e referências a testes no checkout. A CI
executa os testes existentes separadamente; este script não verifica os
resultados remotos da CI nem executa serviços, mídia ou chamadas reais.
"""
import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs/quality/homologacao-parciais-codigo.json"
EXPECTED_IDS = {
    "PABX-PARTIAL-IDENTITY",
    "PABX-PARTIAL-RECORDINGS",
    "PABX-PARTIAL-PROVISIONING",
    "PABX-PARTIAL-AI",
}
MAX_BYTES = 128 * 1024
CODE_STATUS = "CODE_ONLY_ACCEPTED_WITH_LIMITATIONS"
OP_STATUS = "PENDING_REAL_ENVIRONMENT"


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON possui chaves duplicadas")
        result[key] = value
    return result


def read_register(path=REGISTER):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("cadastro ausente ou inseguro")
    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("JSON nao finito"))
    )


def local_source(root, path):
    if not isinstance(path, str) or not path or not path.endswith(".py"):
        raise ValueError("referencia Python invalida")
    rel = PurePosixPath(path)
    if rel.is_absolute() or ".." in rel.parts or "\\" in path:
        raise ValueError("caminho inseguro")
    candidate = Path(root) / path
    if candidate.is_symlink() or not candidate.is_file() or candidate.stat().st_size > MAX_BYTES:
        raise ValueError("arquivo de evidencia ausente ou inseguro")
    if not candidate.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("evidencia fora do checkout")
    return candidate


def validate(register, root=ROOT):
    """Aceita somente trechos existentes, nunca afirma integração completa."""
    if not isinstance(register, dict) or register.get("schema_version") != 1:
        raise ValueError("versao de cadastro invalida")
    if register.get("project") != "AXE PABX" or register.get("baseline_reference") != "main":
        raise ValueError("origem do projeto invalida")
    if register.get("review_method") != "AST_SYMBOLS_AND_EXISTING_AUTOMATED_TEST_REFERENCES":
        raise ValueError("metodo de verificacao desconhecido")
    if register.get("code_review_status") != CODE_STATUS or register.get("operational_homologation_status") != OP_STATUS:
        raise ValueError("estado de homologacao indevido")
    for forbidden in ("real_tests_executed_by_this_register",
                      "production_deployed_by_this_register", "operational_go_authorized"):
        if register.get(forbidden) is not False:
            raise ValueError("declaracao operacional nao comprovada")
    if register.get("source_go_registry") != "docs/quality/provas-operacionais-diferidas.json":
        raise ValueError("registro GO ausente")
    excluded = register.get("excluded_not_implemented")
    if (not isinstance(excluded, list) or len(excluded) < 2
            or any(not isinstance(s, str) or not s.strip() for s in excluded)):
        raise ValueError("escopo nao implementado deve ser explicito")
    items = register.get("items")
    if not isinstance(items, list) or len(items) != len(EXPECTED_IDS):
        raise ValueError("frentes parciais incompletas")
    seen = set()
    output = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("frente invalida")
        name = item.get("id")
        if name in seen or name not in EXPECTED_IDS:
            raise ValueError("frente ausente ou duplicada")
        seen.add(name)
        if item.get("code_review_status") != CODE_STATUS or item.get("operational_status") != OP_STATUS:
            raise ValueError("frente indevidamente homologada")
        for key in ("title", "code_scope"):
            val = item.get(key)
            if not isinstance(val, str) or not val.strip() or len(val) > 400:
                raise ValueError("escopo incompleto")
        gaps = item.get("pending_implementation")
        if (not isinstance(gaps, list) or len(gaps) < 1
                or any(not isinstance(g, str) or not g.strip() or len(g) > 400 for g in gaps)):
            raise ValueError("faltam lacunas explicitas")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("ausencia de evidencia de codigo")
        for entry in evidence:
            if not isinstance(entry, dict) or set(entry) != {"path", "symbol"}:
                raise ValueError("referencia de codigo incorreta")
            symbol = entry["symbol"]
            if not isinstance(symbol, str) or not symbol.isidentifier():
                raise ValueError("simbolo Python invalido")
            source = local_source(root, entry["path"])
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=entry["path"])
            names = {
                node.name for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }
            if symbol not in names:
                raise ValueError("simbolo citado nao existe no codigo")
        tests = item.get("existing_test_files")
        if not isinstance(tests, list) or not tests:
            raise ValueError("revisao sem testes unitarios referenciados")
        for path in tests:
            source = local_source(root, path)
            if not source.name.startswith("test_"):
                raise ValueError("arquivo nao e teste")
            ast.parse(source.read_text(encoding="utf-8"), filename=path)
        output.append({"id": name, "code_review": CODE_STATUS, "operational": OP_STATUS,
                       "sources_checked": len(evidence),
                       "test_files_referenced": len(tests),
                       "gaps_remaining": len(gaps)})
    if seen != EXPECTED_IDS:
        raise ValueError("frentes esperadas nao encontradas")
    return {
        "project": "AXE PABX",
        "total_code_scopes_reviewed": len(output),
        "code_only_review_percent": 100,
        "code_review_scope": "STATIC_SOURCE_SYMBOLS_AND_TEST_REFERENCES_ONLY",
        "existing_tests_executed_by_this_tool": False,
        "real_environment_tests_executed": False,
        "full_functionality_homologated": False,
        "operational_go_authorized": False,
        "pending_operational_review": len(output),
        "items": output,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, default=REGISTER)
    args = parser.parse_args(argv)
    try:
        report = validate(read_register(args.register))
    except (OSError, ValueError, SyntaxError, UnicodeError, json.JSONDecodeError) as exc:
        print("Revisao de codigo invalida: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
