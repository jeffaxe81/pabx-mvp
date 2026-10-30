"""30 dynamic extension prepublication regressions with actual render_all output."""
import copy

import pytest

from conf_generator import render_all
from dynamic_extension_invariants import (
    inspect_dynamic_extensions, validate_dynamic_extensions, RULES,
)

RECORDS = [
    {"name": "t1-vendas", "number": 1100, "tenant": "t1",
     "display_name": "Equipe A", "password": "secret-A-very-long",
     "voicemail_pin": "93847261", "email": "a@example.com"},
    {"name": "t10-vendas", "number": 1100, "tenant": "t10",
     "display_name": "Equipe B", "password": "secret-B-very-long",
     "voicemail_pin": "83726194", "email": "b@example.com"},
]
TENANTS = {"t1", "t10"}
PJSIP = "pjsip_dynamic.conf"
DIAL = "extensions_dynamic_dial-t1.conf"
HINT = "extensions_dynamic_hints-t1.conf"
VM = "voicemail_dynamic_t1.conf"


def fixture():
    records = copy.deepcopy(RECORDS)
    files = render_all(records, tenant_ids=TENANTS)
    return records, files


def results(records, files, tenants=TENANTS):
    return {item["id"]: item["ok"]
            for item in inspect_dynamic_extensions(records, tenants, files)}


def change(files, filename, before, after):
    assert before in files[filename], (filename, before)
    files[filename] = files[filename].replace(before, after)


def test_thirty_gates_pass_on_multitenant_real_generator():
    records, files = fixture()
    status = results(records, files)
    assert len(RULES) == len(status) == 30
    assert list(status) == [f"DE-{i:02d}" for i in range(1, 31)]
    assert all(status.values())
    assert validate_dynamic_extensions(records, TENANTS, files)
    assert "secret-A" not in str(inspect_dynamic_extensions(records, TENANTS, files))
    assert "93847261" not in str(inspect_dynamic_extensions(records, TENANTS, files))


def test_empty_tenant_without_extensions_is_supported():
    files = render_all([], tenant_ids={"t1", "t10"})
    assert all(results([], files).values())


@pytest.mark.parametrize("rule,filename,before,after", [
    ("DE-09", PJSIP, "; ARQUIVO GERADO AUTOMATICAMENTE", "; CONFIGURACAO MANUAL"),
    ("DE-10", PJSIP, "[t1-vendas](endpoint-secure)", "[t1-vendas](endpoint-other)"),
    ("DE-12", PJSIP, "context=t1-internal", "context=t10-internal"),
    ("DE-13", PJSIP, "subscribe_context=t1-hints", "subscribe_context=t10-hints"),
    ("DE-14", PJSIP, "auth=t1-vendas", "auth=t10-vendas"),
    ("DE-15", PJSIP, "aors=t1-vendas", "aors=t10-vendas"),
    ("DE-16", PJSIP, "callerid=Equipe A <1100>", "callerid=Equipe X <1100>"),
    ("DE-17", PJSIP, "mailboxes=t1-vendas@t1", "mailboxes=t1-vendas@t10"),
    ("DE-18", PJSIP, "type=auth", "type=wrong"),
    ("DE-19", PJSIP, "username=t1-vendas", "username=t10-vendas"),
    ("DE-20", PJSIP, "password=secret-A-very-long", "password=changed"),
    ("DE-21", PJSIP, "type=aor", "type=wrong"),
    ("DE-22", PJSIP, "max_contacts=1", "max_contacts=3"),
    ("DE-23", PJSIP, "remove_existing=yes", "remove_existing=no"),
    ("DE-24", DIAL, "exten => 1100,1,MixMonitor", "exten => 1101,1,MixMonitor"),
    ("DE-25", DIAL, "MixMonitor(/var/spool/asterisk/monitor/", "NoOp(/var/spool/asterisk/monitor/"),
    ("DE-26", DIAL, "Set(CDR(accountcode)=t1)", "Set(CDR(accountcode)=t10)"),
    ("DE-27", DIAL, "Dial(PJSIP/t1-vendas,20)", "Dial(PJSIP/t10-vendas,20)"),
    ("DE-28", DIAL, "same => n,Hangup()", "same => n,NoOp()"),
    ("DE-29", HINT, "hint,PJSIP/t1-vendas", "hint,PJSIP/t10-vendas"),
    ("DE-30", VM, "t1-vendas => 93847261", "t1-vendas => 11111111"),
])
def test_drift_is_rejected_before_publish(rule, filename, before, after):
    records, files = fixture()
    change(files, filename, before, after)
    status = results(records, files)
    assert not status[rule], rule
    with pytest.raises(ValueError, match=rule):
        validate_dynamic_extensions(records, TENANTS, files)


def test_tenant_set_invalid_de01():
    records, files = fixture()
    assert results(records, files, {"t1", "t01"})["DE-01"] is False


def test_duplicate_endpoints_de02():
    records, files = fixture()
    records.append(copy.deepcopy(records[0]))
    assert results(records, files)["DE-02"] is False


def test_duplicate_extension_number_inside_tenant_de03():
    records, files = fixture()
    records.append({**records[0], "name": "t1-segundo"})
    assert results(records, files)["DE-03"] is False


def test_missing_generated_config_de04():
    records, files = fixture()
    files.pop(DIAL)
    assert results(records, files)["DE-04"] is False


def test_wrong_filename_de05():
    records, files = fixture()
    files["extensions_dynamic_dial-t01.conf"] = files.pop(DIAL)
    assert results(records, files)["DE-05"] is False


def test_nontext_file_de06():
    records, files = fixture()
    files[PJSIP] = b"not-utf8"
    assert results(records, files)["DE-06"] is False


def test_control_character_de07():
    records, files = fixture()
    files[PJSIP] += "\r"
    assert results(records, files)["DE-07"] is False


def test_oversized_generated_file_de08():
    records, files = fixture()
    files[PJSIP] += "x" * (2 * 1024 * 1024)
    assert results(records, files)["DE-08"] is False


def test_injected_foreign_endpoint_de11():
    records, files = fixture()
    files[PJSIP] += "\n\n[t20-backdoor](endpoint-secure)\ncontext=t20-internal\n"
    assert results(records, files)["DE-11"] is False


def test_t1_and_t10_never_cross_share_dynamic_dial_hints_or_mailbox():
    records, files = fixture()
    assert "t10-vendas" not in files[DIAL]
    assert "t10-vendas" not in files[HINT]
    assert "t10-vendas => " not in files[VM]
    assert "t1-vendas" not in files["extensions_dynamic_dial-t10.conf"]
    assert "t1-vendas" not in files["extensions_dynamic_hints-t10.conf"]


def test_render_all_fails_before_publication_when_generator_is_corrupted(monkeypatch):
    import conf_generator
    original = conf_generator.render_extensions_dynamic_hints

    def corrupt(rows):
        return original(rows).replace("hint,PJSIP/t1-vendas", "hint,PJSIP/t10-vendas")

    monkeypatch.setattr(conf_generator, "render_extensions_dynamic_hints", corrupt)
    with pytest.raises(ValueError, match="DE-29"):
        render_all(RECORDS, tenant_ids=TENANTS)


def test_failed_gate_does_not_echo_customer_or_password():
    records, files = fixture()
    files[PJSIP] = files[PJSIP].replace("context=t1-internal", "context=t20-internal")
    with pytest.raises(ValueError) as caught:
        validate_dynamic_extensions(records, TENANTS, files)
    message = str(caught.value)
    for word in ("secret-A-very-long", "93847261", "Equipe A", "a@example.com"):
        assert word not in message
