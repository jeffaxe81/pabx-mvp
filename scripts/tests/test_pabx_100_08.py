"""100-test cycle 71–80: offline voicemail PIN audit, not live authentication."""
import json
from voicemail_pin_audit import audit_voicemail_text,audit_voicemail_files

GOOD="[t1]\nt1-1001 => 93847261,Operator\n"

def test_071_strong_pin_in_local_tenant_is_accepted():
    report=audit_voicemail_text(GOOD)
    assert report["ok"] and report["mailboxes"]==1

def test_072_legacy_four_digit_pin_is_rejected():
    assert not audit_voicemail_text(GOOD.replace("93847261","1234"))["ok"]

def test_073_sequential_pin_is_rejected():
    assert not audit_voicemail_text(GOOD.replace("93847261","12345678"))["ok"]

def test_074_repeated_digit_pin_is_rejected():
    assert not audit_voicemail_text(GOOD.replace("93847261","11111111"))["ok"]

def test_075_mailbox_cross_tenant_is_detected():
    report=audit_voicemail_text(GOOD.replace("[t1]","[t2]"))
    assert not report["ok"] and report["cross_tenant"]==1

def test_076_prefix_confusion_t1_vs_t10_is_rejected():
    report=audit_voicemail_text(GOOD.replace("t1-1001","t10-1001"))
    assert not report["ok"] and report["cross_tenant"]==1

def test_077_reused_pin_across_mailboxes_is_detected():
    src=GOOD+"t1-1002 => 93847261,Another\n"
    assert audit_voicemail_text(src)["reused_pins"]==1

def test_078_audit_report_never_prints_pin_or_name():
    report=audit_voicemail_text(GOOD)
    serialized=json.dumps(report)
    assert "93847261" not in serialized and "Operator" not in serialized

def test_079_voicemail_file_audit_refuses_symlinks(tmp_path):
    path=tmp_path/"voicemail.conf"
    path.write_text(GOOD)
    link=tmp_path/"shortcut.conf"
    link.symlink_to(path)
    assert not audit_voicemail_files([link])["ok"]
    assert audit_voicemail_files([path])["ok"]

def test_080_voicemail_multi_file_audit_detects_reuse(tmp_path):
    a=tmp_path/"t1.conf"
    b=tmp_path/"t2.conf"
    a.write_text(GOOD)
    b.write_text(GOOD.replace("[t1]","[t2]").replace("t1-1001","t2-1001"))
    result=audit_voicemail_files([a,b])
    assert not result["ok"] and result["reused_pins"]==1
