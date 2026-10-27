"""Regressoes do gate estatico. Nao declara isolamento em chamadas reais."""
import json
from pathlib import Path

import pytest
import tenant_isolation_static as gate


@pytest.fixture
def config(tmp_path):
    (tmp_path / "pjsip.conf").write_text(
        "[t1-1001](endpoint-secure)\ncontext=t1-internal\n"
        "subscribe_context=t1-hints\nauth=t1-1001\naors=t1-1001\n"
        "mailboxes=t1-1001@t1\n"
        "[t2-1001](endpoint-secure)\ncontext=t2-internal\n"
        "subscribe_context=t2-hints\nauth=t2-1001\naors=t2-1001\n"
        "mailboxes=t2-1001@t2\n"
    )
    (tmp_path / "queues.conf").write_text(
        "[fila-t1]\nmember => PJSIP/t1-1001\n"
        "[fila-t2]\nmember => PJSIP/t2-1001\n"
    )
    (tmp_path / "voicemail.conf").write_text(
        "[t1]\nt1-1001 => SECRET,Teste\n"
        "[t2]\nt2-1001 => SECRET2,Teste\n"
    )
    (tmp_path / "extensions.conf").write_text(
        "[t1-internal]\nexten => 1001,1,Dial(PJSIP/t1-1001,20)\n"
        "[t2-internal]\nexten => 1001,1,Dial(PJSIP/t2-1001,20)\n"
    )
    return tmp_path


def replace(path, original, modified):
    content = path.read_text()
    assert original in content
    path.write_text(content.replace(original, modified, 1))


def test_fixture_clean_but_never_claims_live_or_go(config):
    result = gate.audit(config)
    assert result["success"] is True
    assert result["passed"] == result["total"]
    assert set(result["tenants_in_versioned_config"]) == {"t1", "t2"}
    assert result["scope"] == "versioned_static_base_configs_only"
    for key in ("generated_includes_evaluated", "astdb_and_api_tested",
                "live_tenant_isolation_tested", "sip_rtp_tested",
                "operational_go_authorized"):
        assert result[key] is False
    assert "SECRET" not in json.dumps(result)


@pytest.mark.parametrize("file,old,new,failed", [
    ("pjsip.conf", "context=t1-internal", "context=t2-internal", "context:t1-1001"),
    ("pjsip.conf", "subscribe_context=t1-hints", "subscribe_context=t2-hints", "subscribe:t1-1001"),
    ("pjsip.conf", "auth=t1-1001", "auth=t2-1001", "auth:t1-1001"),
    ("pjsip.conf", "aors=t1-1001", "aors=t2-1001", "aors:t1-1001"),
    ("pjsip.conf", "mailboxes=t1-1001@t1", "mailboxes=t2-1001@t2", "mailboxes:t1-1001"),
    ("queues.conf", "PJSIP/t1-1001", "PJSIP/t2-1001", "members:fila-t1"),
    ("voicemail.conf", "t1-1001 => SECRET", "t2-1001 => SECRET", "voicemail_boxes:t1"),
    ("extensions.conf", "PJSIP/t1-1001", "PJSIP/t2-1001", "dialplan_literal_refs:t1"),
    ("extensions.conf", "Dial(PJSIP/t1-1001,20)", "VoiceMail(t2-1001@t2,u)", "dialplan_literal_refs:t1"),
    ("extensions.conf", "Dial(PJSIP/t1-1001,20)", "Queue(fila-t2)", "dialplan_literal_refs:t1"),
    ("extensions.conf", "Dial(PJSIP/t1-1001,20)", "Goto(t2-internal,1000,1)", "dialplan_literal_refs:t1"),
    ("extensions.conf", "Dial(PJSIP/t1-1001,20)", "Set(CDR(accountcode)=t2)", "dialplan_literal_refs:t1"),
])
def test_cross_tenant_edges_are_rejected(config, file, old, new, failed):
    replace(config / file, old, new)
    result = gate.audit(config)
    assert not result["success"]
    assert failed in result["failed_checks"]


def test_missing_queues_and_missing_endpoint_fail_closed(config):
    (config / "queues.conf").write_text("[fila-t1]\n")
    (config / "pjsip.conf").write_text("[general]\n")
    result = gate.audit(config)
    assert "has_primary_queue:t1" in result["failed_checks"]
    assert "has_pjsip_endpoint:t1" in result["failed_checks"]


def test_symlinks_missing_files_and_oversized_files_fail_closed(config):
    target = config / "outside.conf"
    target.write_text("[fila-t1]\nmember => PJSIP/t1-1001\n")
    (config / "queues.conf").unlink()
    (config / "queues.conf").symlink_to(target)
    result = gate.audit(config)
    assert result["success"] is False
    assert result["failed_checks"] == ["files_readable_and_safe"]
    (config / "queues.conf").unlink()
    assert gate.audit(config)["success"] is False
    (config / "queues.conf").write_text("A" * (1024 * 1024 + 1))
    assert gate.audit(config)["success"] is False


def test_comments_and_shared_dynamic_variables_not_misclassified(config):
    with (config / "extensions.conf").open("a") as output:
        output.write("; exemplo proibido PJSIP/t9-invasor\n")
    assert gate.audit(config)["success"] is True


def test_cli_fail_closed_does_not_print_config_or_secrets(config, capsys):
    replace(config / "voicemail.conf", "t1-1001 => SECRET", "t2-1001 => PRIVATE_PASSWORD")
    exit_code = gate.main(["--asterisk-root", str(config)])
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert "voicemail_boxes:t1" in report["failed_checks"]
    assert "PRIVATE_PASSWORD" not in json.dumps(report)


def test_real_repository_versioned_static_contexts():
    root = Path(__file__).resolve().parents[2] / "asterisk"
    result = gate.audit(root)
    assert result["success"], result["failed_checks"]
    assert result["live_tenant_isolation_tested"] is False
