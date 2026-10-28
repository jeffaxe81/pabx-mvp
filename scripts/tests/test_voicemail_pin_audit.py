"""Auditoria segura de PINs de voicemail: só indicadores, nenhum segredo."""
import json

from voicemail_pin_audit import audit_voicemail_text, audit_voicemail_files, main


def test_weak_legacy_pin_is_detected_without_disclosing_secrets():
    raw = "[general]\nformat=wav\n[t1]\nt1-1001 => 1234,T1\n"
    report = audit_voicemail_text(raw)
    assert not report["ok"]
    assert report["weak_pins"] == 1
    assert report["mailboxes"] == 1
    assert "1234" not in json.dumps(report)
    assert "t1-1001" not in json.dumps(report)


def test_separate_strong_mailbox_pins_with_correct_tenant_are_accepted():
    raw = "[t1]\nt1-1001 => 93847261,Um\n[t10]\nt10-1001 => 62483597,Dez\n"
    report = audit_voicemail_text(raw)
    assert report["ok"]
    assert report["tenants"] == ["t1", "t10"]
    assert report["mailboxes"] == 2


def test_cross_tenant_mailboxes_are_not_accepted_including_t1_vs_t10():
    for value in (
        "[t1]\nt10-1001 => 93847261,Outra\n",
        "[t10]\nt1-1001 => 93847261,Outra\n",
        "[general]\nt1-1001 => 93847261,Orfao\n",
    ):
        report = audit_voicemail_text(value)
        assert not report["ok"]
        assert report["cross_tenant"] == 1


def test_known_weak_and_invalid_mailbox_fail_closed():
    for password in ("1234", "11111111", "12345678", "87654321", "abc", "00000000", "99999999"):
        report = audit_voicemail_text("[t2]\nt2-1001 => " + password + ",Nome\n")
        assert not report["ok"]
        assert report["weak_pins"] == 1
        assert password not in json.dumps(report)
    assert not audit_voicemail_text("[t1]\ninvalid => 93847261,X\n")["ok"]


def test_missing_or_symlink_config_is_rejected(tmp_path):
    missing = tmp_path / "missing.conf"
    assert not audit_voicemail_files([missing])["ok"]
    real = tmp_path / "valid.conf"
    real.write_text("[t1]\nt1-1001 => 93847261,Nome\n")
    link = tmp_path / "alias.conf"
    link.symlink_to(real)
    assert not audit_voicemail_files([link])["ok"]
    assert audit_voicemail_files([real])["ok"]


def test_cli_reports_only_summary_and_exits_nonzero_on_weak_pin(tmp_path, capsys):
    path = tmp_path / "voicemail.conf"
    path.write_text("[t1]\nt1-1001 => 1234,Alguem\n")
    assert main([str(path)]) == 1
    emitted = capsys.readouterr().out
    assert "1234" not in emitted and "Alguem" not in emitted
    assert json.loads(emitted)["weak_pins"] == 1
    path.write_text("[t1]\nt1-1001 => 93847261,Alguem\n")
    assert main([str(path)]) == 0


def test_reused_pin_in_one_file_or_across_files_is_rejected(tmp_path):
    same_pin = "93847261"
    a = tmp_path / "t1.conf"
    b = tmp_path / "t10.conf"
    a.write_text("[t1]\\nt1-1001 => " + same_pin + ",Um\\n".replace("\\n", "\n"))
    b.write_text("[t10]\\nt10-1001 => " + same_pin + ",Dez\\n".replace("\\n", "\n"))
    report = audit_voicemail_files([a, b])
    assert not report["ok"]
    assert report["reused_pins"] == 1
    assert same_pin not in json.dumps(report)
    assert audit_voicemail_text("[t1]\\nt1-1001 => 93847261,Um\\nt1-1002 => 93847261,Dois\\n".replace("\\n", "\n"))["reused_pins"] == 1
