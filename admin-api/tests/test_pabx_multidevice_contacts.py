"""Aceite da capacidade PABX de registro SIP multidispositivo (1..3)."""
from pathlib import Path
import math

import pytest

from store import (
    add_extension, update_extension, load_store, save_store,
    validate_extension_input,
)
from conf_generator import (
    render_all, render_pjsip_dynamic, validate_persisted_extensions,
)

INPUT = {
    "name":"vendas-3", "number":1117, "display_name":"Vendas 3",
    "password":"senha-sip-forte-2026", "tenant":"t1",
}


def test_legacy_remains_single_device_without_schema_breaking():
    valid,error,cleaned=validate_extension_input(INPUT,[])
    assert valid and error is None
    assert "max_contacts" not in cleaned
    generated=render_all([cleaned])
    assert "max_contacts=1" in generated["pjsip_dynamic.conf"]
    assert "remove_existing=yes" in generated["pjsip_dynamic.conf"]


@pytest.mark.parametrize("count", [1,2,3])
def test_valid_contact_limits_do_not_affect_sip_security(count):
    valid,_,cleaned=validate_extension_input({**INPUT,"max_contacts":count},[])
    assert valid
    assert cleaned.get("max_contacts",1)==count
    rendered=render_all([cleaned])["pjsip_dynamic.conf"]
    assert "max_contacts="+str(count) in rendered
    assert "endpoint-secure" in rendered
    assert "context=t1-internal" in rendered
    assert "transport=transport-udp" not in rendered


@pytest.mark.parametrize("bad", [
    True,False,0,-1,4,9,"1","3",1.0,2.5,None,
    math.inf,math.nan,[],{},["2"],"\nmax_contacts=99",
])
def test_invalid_limit_denied_before_persisted_config(bad):
    assert validate_extension_input({**INPUT,"max_contacts":bad},[])[0] is False
    with pytest.raises(ValueError):
        render_pjsip_dynamic([{
            **INPUT,"max_contacts":bad,"voicemail_pin":"98765432",
        }])


def test_create_update_and_restore_single_contact(tmp_path):
    path=tmp_path/"extensions.json"
    ok,_,added=add_extension(path,{**INPUT,"max_contacts":3})
    assert ok and added["max_contacts"]==3
    assert load_store(path)[0]["max_contacts"]==3
    updated,err,row=update_extension(path,INPUT["name"],{"max_contacts":2})
    assert updated and row["max_contacts"]==2
    reverted,err,row=update_extension(path,INPUT["name"],{"max_contacts":1})
    assert reverted and "max_contacts" not in row
    assert "max_contacts" not in load_store(path)[0]
    assert "max_contacts=1" in render_all(load_store(path))["pjsip_dynamic.conf"]


def test_invalid_legacy_disk_state_fails_closed(tmp_path):
    path=tmp_path/"extensions.json"
    _,_,valid=add_extension(path,INPUT)
    bad={**valid,"max_contacts":True}
    save_store(path,[bad])
    ok,err,_=update_extension(path,INPUT["name"],{"display_name":"Novo"})
    assert not ok and "cadastro" in err
    with pytest.raises(ValueError):
        render_all(load_store(path))


def test_multi_tenant_devices_stay_in_separate_contexts(tmp_path):
    first={**INPUT,"max_contacts":3}
    second={**INPUT,"tenant":"t2","name":"t2-vendas","number":1117,
            "max_contacts":2}
    ok,_,row1=add_extension(tmp_path/"t1.json",first)
    ok2,_,row2=add_extension(tmp_path/"t2.json",second)
    assert ok and ok2
    generated=render_all([row1,row2])
    pjsip=generated["pjsip_dynamic.conf"]
    assert "context=t1-internal" in pjsip
    assert "context=t2-internal" in pjsip
    assert "max_contacts=3" in pjsip
    assert "max_contacts=2" in pjsip
    assert row2["name"] not in generated["extensions_dynamic_dial-t1.conf"]
    assert row1["name"] not in generated["extensions_dynamic_dial-t2.conf"]


def test_pending_publish_uses_persisted_validation_before_render():
    raw={**INPUT,"voicemail_pin":"98765432","max_contacts":False}
    with pytest.raises(ValueError):
        validate_persisted_extensions([raw], {"t1","t2"})


def test_admin_form_offers_devices_and_serializes_integer():
    page=(Path(__file__).resolve().parents[2]/"admin"/"index.html").read_text(encoding="utf-8")
    assert 'id="formMaxContacts"' in page
    assert '<option value="1">' in page
    assert '<option value="2">' in page
    assert '<option value="3">' in page
    assert "max_contacts: Number(el('formMaxContacts').value)" in page
    assert "String(ext.max_contacts || 1)" in page
    assert "el('formMaxContacts').value = '1'" in page
