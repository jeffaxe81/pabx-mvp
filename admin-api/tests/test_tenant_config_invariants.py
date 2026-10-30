"""Twenty PJSIP/tenant prepublication controls on actual generator output."""
from pathlib import Path

import pytest

from tenant_provisioning import build_tenant_files
from tenant_config_invariants import (
    CHECK_LABELS, inspect_generated_tenant_files, validate_generated_tenant_files,
)

TENANT = "t3"
SIP = {"t3-recepcao": "A" * 32, "t3-recepcao-2": "B" * 32}
PINS = {"t3-1001": "24681357", "t3-recepcao": "58269417",
        "t3-recepcao-2": "73918264"}


def generated():
    return build_tenant_files(Path("/unmounted/test/asterisk"), TENANT, SIP, PINS)


def section(files, name):
    return next(path for path in files if path.parent.name == name)


def check(files, tid=TENANT):
    return {item["id"]: item["ok"] for item in inspect_generated_tenant_files(files, tid)}


def test_all_twenty_invariants_pass_on_actual_tenant_generator():
    files = generated()
    checks = check(files)
    assert len(CHECK_LABELS) == len(checks) == 20
    assert len({item[0] for item in CHECK_LABELS}) == 20
    assert all(checks.values())
    assert validate_generated_tenant_files(files, TENANT) is True


@pytest.mark.parametrize("rule,subdir,before,after", [
    ("TP-05", "pjsip_tenants",
     "[t3-recepcao](endpoint-webrtc)", "[t30-recepcao](endpoint-webrtc)"),
    ("TP-06", "pjsip_tenants",
     "[t3-recepcao-2](endpoint-webrtc)", "[t30-recepcao-2](endpoint-webrtc)"),
    ("TP-07", "pjsip_tenants",
     "context=t3-internal", "context=t30-internal"),
    ("TP-08", "pjsip_tenants",
     "\nauth=t3-recepcao\n", "\nauth=t30-recepcao\n"),
    ("TP-09", "pjsip_tenants",
     "\naors=t3-recepcao\n", "\naors=t30-recepcao\n"),
    ("TP-10", "pjsip_tenants",
     "mailboxes=t3-recepcao@t3", "mailboxes=t3-recepcao@t30"),
    ("TP-11", "queues_tenants",
     "[fila-t3-en]", "[fila-t30-en]"),
    ("TP-12", "queues_tenants",
     "\nmember => PJSIP/t3-recepcao\n", "\nmember => PJSIP/t30-recepcao\n"),
    ("TP-13", "queues_tenants",
     "monitor-type = mixmonitor", "monitor-type = none"),
    ("TP-14", "extensions_tenants",
     "[t3-hints]", "[t30-hints]"),
    ("TP-15", "extensions_tenants",
     "Queue(${FILA_IDIOMA},c,,,", "NoOp(${FILA_IDIOMA},c,,,"),
    ("TP-16", "extensions_tenants",
     "PJSIP_ENDPOINT(${VM_ENDPOINT},context)", "PJSIP_ENDPOINT(xxx,context)"),
    ("TP-17", "extensions_tenants",
     "DB(blocklist-t3/", "DB(blocklist-t30/"),
    ("TP-18", "extensions_tenants",
     "#include generated/extensions_dynamic_hints-t3.conf",
     "#include generated/extensions_dynamic_hints-t30.conf"),
    ("TP-19", "voicemail_tenants",
     "t3-1001 => ", "t30-1001 => "),
    ("TP-20", "parking_tenants",
     "parkpos = 76-95", "parkpos = 60-70"),
])
def test_template_drift_rejected_with_specific_rule_id(rule, subdir, before, after):
    files = generated()
    path = section(files, subdir)
    assert before in files[path], (rule, before)
    files[path] = files[path].replace(before, after)
    checks = check(files)
    assert checks[rule] is False
    with pytest.raises(ValueError, match=rule):
        validate_generated_tenant_files(files, TENANT)


def test_reject_unsupported_tenant_id():
    files = generated()
    checks = check(files, "t01")
    assert checks["TP-01"] is False
    with pytest.raises(ValueError, match="TP-01"):
        validate_generated_tenant_files(files, "t01")


def test_reject_missing_file():
    files = generated()
    files.pop(section(files, "parking_tenants"))
    checks = check(files)
    assert checks["TP-02"] is False
    assert checks["TP-03"] is False
    with pytest.raises(ValueError, match="TP-02"):
        validate_generated_tenant_files(files, TENANT)


def test_reject_filename_or_directory_swapping():
    files = generated()
    target = section(files, "pjsip_tenants")
    contents = files.pop(target)
    files[target.parent.parent / "queues_tenants" / "t3-pjsip.conf"] = contents
    assert check(files)["TP-03"] is False


def test_reject_control_characters_in_generated_sip_config():
    files = generated()
    target = section(files, "pjsip_tenants")
    files[target] = files[target] + "\x00"
    assert check(files)["TP-04"] is False


def test_reject_oversized_generated_config():
    files = generated()
    target = section(files, "pjsip_tenants")
    files[target] = files[target] + "a" * (256 * 1024)
    assert check(files)["TP-04"] is False


def test_prepublication_validation_precedes_all_io_and_ami(monkeypatch):
    import tenant_provisioning
    def corrupted_tenant_queues(tid):
        return "[wrong-queue]\n"
    monkeypatch.setattr(tenant_provisioning, "render_tenant_queues",
                        corrupted_tenant_queues)
    with pytest.raises(ValueError, match="TP-11"):
        tenant_provisioning.build_tenant_files(
            Path("/does-not-exist"), TENANT, SIP, PINS
        )


def test_invalid_files_never_echo_sip_secrets_or_voicemail_pin():
    files = generated()
    target = section(files, "pjsip_tenants")
    files[target] = files[target].replace("context=t3-internal",
                                         "context=t30-internal")
    with pytest.raises(ValueError) as caught:
        validate_generated_tenant_files(files, TENANT)
    message = str(caught.value)
    assert "A" * 32 not in message
    assert "B" * 32 not in message
    assert "24681357" not in message
