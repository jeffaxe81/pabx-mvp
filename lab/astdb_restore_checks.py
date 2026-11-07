"""Restauração lógica de chaves AstDB REAL no Asterisk descartável.

Não há backup de SQLite produtivo: esta é prova limitada de exportação
lógica, exclusão e reimportação, com isolamento por tenant. Todos os
valores são efêmeros e jamais incluídos no relatório de CI.
"""
import re
import secrets

TENANTS = ("t1", "t2", "t3")
KEYS = ("ramal-1001", "policy-routing")
METRICS = ("empty_before", "written", "snapshot_exact",
           "deleted", "restored_exact", "tenant_isolated", "cleanup")


def required_astdb_restore_checks():
    return ({f"astdb_{name}:{tenant}" for tenant in TENANTS for name in METRICS}
            | {"astdb_no_external_calls"})


def astdb_token_from_cli(raw):
    """Nunca aceitar descrição, múltiplos valores ou saída não-AstDB."""
    if not isinstance(raw, str) or len(raw) > 4096:
        return None
    matched = re.findall(r"(?m)^Value:\s*([0-9a-f]{32})\s*$", raw)
    return matched[0] if len(matched) == 1 and raw.count("Value:") == 1 else None


def exercise_astdb_restore(container, report):
    from .asterisk_lab import cli

    checks = report["checks"]
    checks.update({name: False for name in required_astdb_restore_checks()})
    report["real_astdb_logical_restore_tested"] = False
    report["astdb_restore_cases"] = {}
    families = {t: "axe-backup-lab-" + t for t in TENANTS}
    originals = {
        t: {k: secrets.token_hex(16) for k in KEYS} for t in TENANTS
    }
    created = []
    try:
        for tenant in TENANTS:
            report["phase"] = "astdb-restore:" + tenant
            family = families[tenant]
            empty = all(astdb_token_from_cli(cli(
                container, "database get " + family + " " + key
            )) is None for key in KEYS)
            checks[f"astdb_empty_before:{tenant}"] = empty
            if not empty:
                raise ValueError("família AstDB de recuperação ocupada")
            for key, value in originals[tenant].items():
                cli(container, "database put " + family + " " + key + " " + value)
                created.append((family, key))
            checks[f"astdb_written:{tenant}"] = all(
                astdb_token_from_cli(cli(
                    container, "database get " + family + " " + key
                )) == value for key, value in originals[tenant].items()
            )
            if not checks[f"astdb_written:{tenant}"]:
                raise ValueError("gravação AstDB de staging não conferiu")
            # Snapshot lógico recolhido do próprio runtime, não de fixture.
            snapshot = {key: astdb_token_from_cli(cli(
                container, "database get " + family + " " + key
            )) for key in KEYS}
            checks[f"astdb_snapshot_exact:{tenant}"] = (
                snapshot == originals[tenant]
                and len(set(snapshot.values())) == len(KEYS)
            )
            if not checks[f"astdb_snapshot_exact:{tenant}"]:
                raise ValueError("snapshot AstDB não consistente")
            for key in KEYS:
                cli(container, "database del " + family + " " + key)
            checks[f"astdb_deleted:{tenant}"] = all(
                astdb_token_from_cli(cli(
                    container, "database get " + family + " " + key
                )) is None for key in KEYS
            )
            if not checks[f"astdb_deleted:{tenant}"]:
                raise ValueError("AstDB não foi realmente esvaziada")
            # Reimportar exatamente o snapshot observado no Asterisk.
            for key, value in snapshot.items():
                cli(container, "database put " + family + " " + key + " " + value)
            checks[f"astdb_restored_exact:{tenant}"] = all(
                astdb_token_from_cli(cli(
                    container, "database get " + family + " " + key
                )) == snapshot[key] for key in KEYS
            )
            if not checks[f"astdb_restored_exact:{tenant}"]:
                raise ValueError("recuperação lógica AstDB divergente")
            checks[f"astdb_tenant_isolated:{tenant}"] = all(
                astdb_token_from_cli(cli(
                    container, "database get " + families[other] + " " + key
                )) != originals[tenant][key]
                for other in TENANTS if other != tenant for key in KEYS
            )
            # Os dados exatos não saem do runner; somente resultados.
            report["astdb_restore_cases"][tenant] = {
                "write_verified": checks[f"astdb_written:{tenant}"],
                "snapshot_verified": checks[f"astdb_snapshot_exact:{tenant}"],
                "logical_restore_verified": checks[f"astdb_restored_exact:{tenant}"],
                "isolated": checks[f"astdb_tenant_isolated:{tenant}"],
            }
        channels = cli(container, "core show channels concise")
        checks["astdb_no_external_calls"] = not any(
            line.startswith(("PJSIP/", "Local/"))
            for line in channels.splitlines()
        )
    finally:
        for family, key in created:
            cli(container, "database del " + family + " " + key)
        for tenant in TENANTS:
            family = families[tenant]
            checks[f"astdb_cleanup:{tenant}"] = all(
                astdb_token_from_cli(cli(
                    container, "database get " + family + " " + key
                )) is None for key in KEYS
            )
    report["real_astdb_logical_restore_tested"] = all(
        checks[name] is True for name in required_astdb_restore_checks()
    )
    if not report["real_astdb_logical_restore_tested"]:
        raise ValueError("recuperação lógica AstDB parcial ou insegura")
