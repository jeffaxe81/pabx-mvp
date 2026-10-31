"""100-test cycle 91–100: Asterisk config atomic staging, filesystem only."""
import stat
import pytest
from conf_publisher import published_conf_batch

def test_091_publish_single_conf_persists_after_commit(tmp_path):
    with published_conf_batch(tmp_path,{"pjsip_dynamic.conf":"[endpoint]\n"}):
        pass
    assert (tmp_path/"pjsip_dynamic.conf").read_text()=="[endpoint]\n"

def test_092_publish_multiple_conf_files(tmp_path):
    with published_conf_batch(tmp_path,{
        "pjsip_dynamic.conf":"sip",
        "voicemail_dynamic_t1.conf":"mailbox",
    }):
        pass
    assert (tmp_path/"pjsip_dynamic.conf").read_text()=="sip"
    assert (tmp_path/"voicemail_dynamic_t1.conf").read_text()=="mailbox"

def test_093_rollback_restores_previous_content(tmp_path):
    path=tmp_path/"pjsip_dynamic.conf"
    path.write_text("original")
    with pytest.raises(RuntimeError):
        with published_conf_batch(tmp_path,{path.name:"updated"}):
            raise RuntimeError("simulate failed reload")
    assert path.read_text()=="original"

def test_094_rollback_removes_newly_created_config(tmp_path):
    path=tmp_path/"pjsip_dynamic.conf"
    with pytest.raises(RuntimeError):
        with published_conf_batch(tmp_path,{path.name:"updated"}):
            raise RuntimeError("simulate failure")
    assert not path.exists()

def test_095_rollback_preserves_original_permissions(tmp_path):
    path=tmp_path/"pjsip_dynamic.conf"
    path.write_bytes(b"old")
    path.chmod(0o600)
    with pytest.raises(RuntimeError):
        with published_conf_batch(tmp_path,{path.name:"new"}):
            raise RuntimeError("simulate failure")
    assert stat.S_IMODE(path.stat().st_mode)==0o600

def test_096_publish_rejects_config_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        with published_conf_batch(tmp_path,{"../manager.conf":"invalid"}):
            pass

def test_097_publish_rejects_wrong_extension(tmp_path):
    with pytest.raises(ValueError):
        with published_conf_batch(tmp_path,{"pjsip_dynamic.ini":"invalid"}):
            pass

def test_098_publish_rejects_binary_contents(tmp_path):
    with pytest.raises(ValueError):
        with published_conf_batch(tmp_path,{"pjsip_dynamic.conf":b"bytes"}):
            pass

def test_099_publish_rejects_symlink_target(tmp_path):
    sensitive=tmp_path/"sensitive.conf"
    sensitive.write_text("private")
    (tmp_path/"pjsip_dynamic.conf").symlink_to(sensitive)
    with pytest.raises(ValueError):
        with published_conf_batch(tmp_path,{"pjsip_dynamic.conf":"replacement"}):
            pass
    assert sensitive.read_text()=="private"

def test_100_staging_files_are_removed_after_commit(tmp_path):
    with published_conf_batch(tmp_path,{"pjsip_dynamic.conf":"value"}):
        pass
    assert not list(tmp_path.glob(".pabx-conf-*"))
