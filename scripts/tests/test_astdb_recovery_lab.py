"""AstDB real: checker sem dados nos logs, negativas e gate obrigatório."""
import pytest

from lab.astdb_restore_checks import (
    astdb_token_from_cli, exercise_astdb_restore, required_astdb_restore_checks,
)


def test_astdb_parser_requires_one_exact_runtime_value():
    good = "a" * 32
    assert astdb_token_from_cli("Value: " + good + "\n") == good
    for bad in (None, {}, "", "Database entry not found.", "Value: bad",
                "Value: " + good + "\nValue: " + good,
                "Value: " + "g" * 32,
                "prefix Value: " + good,
                "Value: " + good + "\nerror Value: x",
                "Value: " + good + " trailing"):
        assert astdb_token_from_cli(bad) is None


def test_astdb_logical_roundtrip_uses_real_cli_interface(monkeypatch):
    import lab.asterisk_lab as runner
    content = {}
    calls = []

    def cli(_container, command):
        calls.append(command.split(" ", 1)[0])
        if command == "core show channels concise":
            return ""
        parts = command.split(" ")
        if parts[:2] == ["database", "get"]:
            value = content.get((parts[2], parts[3]))
            return "Value: " + value + "\n" if value is not None else "Database entry not found.\n"
        if parts[:2] == ["database", "put"]:
            content[(parts[2], parts[3])] = parts[4]
            return "Updated database successfully\n"
        if parts[:2] == ["database", "del"]:
            content.pop((parts[2], parts[3]), None)
            return "Database entry removed.\n"
        raise AssertionError("unexpected Asterisk CLI action")

    monkeypatch.setattr(runner, "cli", cli)
    report = {"checks": {}}
    exercise_astdb_restore("lab-container", report)
    required = required_astdb_restore_checks()
    assert len(required) == 22
    assert set(report["checks"]) == required
    assert all(report["checks"].values())
    assert report["real_astdb_logical_restore_tested"] is True
    assert content == {}
    assert all(set(case) == {
        "write_verified", "snapshot_verified", "logical_restore_verified", "isolated"
    } for case in report["astdb_restore_cases"].values())
    assert "put" not in calls and "database" in calls


def test_astdb_fail_closed_when_deletion_not_performed(monkeypatch):
    import lab.asterisk_lab as runner
    content = {}

    def cli(_container, command):
        if command == "core show channels concise":
            return ""
        parts = command.split(" ")
        if parts[:2] == ["database", "get"]:
            return ("Value: " + content[(parts[2], parts[3])] + "\n"
                    if (parts[2], parts[3]) in content
                    else "Database entry not found.\n")
        if parts[:2] == ["database", "put"]:
            content[(parts[2], parts[3])] = parts[4]
            return "Updated database successfully"
        if parts[:2] == ["database", "del"]:
            return "Database entry removed."  # falha silenciosa, dado presente!
        raise AssertionError("unexpected call")

    monkeypatch.setattr(runner, "cli", cli)
    report = {"checks": {}}
    with pytest.raises(ValueError, match="esvaziada"):
        exercise_astdb_restore("sandbox", report)
    assert report["real_astdb_logical_restore_tested"] is False


def test_astdb_restore_required_in_lab_summary():
    from lab.asterisk_lab import summarize
    base = {"real_runtime", "tls_transport", "wss_transport",
            "container_removed", "checkout_clean", "runtime_mounts",
            "source_label"}
    base.update(
        name + ":" + tenant for tenant in ("t1", "t2", "t3")
        for name in ("context", "register", "contact",
                     "unregister", "wrong_password")
    )
    base |= required_astdb_restore_checks()
    assert summarize({name: True for name in base}, astdb_restore=True)["success"]
    base.remove("astdb_cleanup:t1")
    assert not summarize({name: True for name in base}, astdb_restore=True)["success"]
