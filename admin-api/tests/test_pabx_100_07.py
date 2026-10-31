"""100-test cycle 61–70: PBX DID/tenant routing input and static conflict."""
import pytest
from tenants import (parse_static_inbound_dids,validate_tenant_creation_input,
                     validate_tenant_removal,generate_tenant_credentials)

BASE={"tenant_id":"t3","did":"5511900003333","display_name":"Empresa Teste"}

def validate(changes=None,existing=None,reserved=()):
    return validate_tenant_creation_input({**BASE,**(changes or {})},
              [] if existing is None else existing,reserved)

def test_061_new_tenant_with_did_is_valid():
    ok,_,item=validate()
    assert ok and item==BASE

def test_062_tenant_t1_is_reserved():
    assert not validate({"tenant_id":"t1"})[0]

def test_063_tenant_t2_is_reserved():
    assert not validate({"tenant_id":"t2"})[0]

def test_064_tenant_identifier_path_injection_denied():
    assert not validate({"tenant_id":"t3/../../secret"})[0]

def test_065_did_must_contain_eight_to_fifteen_digits():
    for did in ("1234567","9"*16,""):
        assert not validate({"did":did})[0]

def test_066_did_formatting_normalized_before_registry():
    ok,_,item=validate({"did":"+55 (11) 90000-3333"})
    assert ok and item["did"]=="5511900003333"

def test_067_duplicate_did_other_tenant_denied():
    existing=[{"tenant_id":"t4","did":"5511900003333"}]
    assert not validate(existing=existing)[0]

def test_068_static_did_conflict_is_rejected():
    dialplan="[from-tdm-gateway]\nexten => 5511900003333,1,Set(TENANT=t1)\n"
    reserved=parse_static_inbound_dids(dialplan)
    assert "5511900003333" in reserved
    assert not validate(reserved=reserved)[0]

def test_069_removal_cannot_delete_static_tenant():
    for tenant in ("t1","t2"):
        assert not validate_tenant_removal(tenant,[])[0]

def test_070_tenant_credentials_are_separate_and_distinct():
    credentials=generate_tenant_credentials("t3")
    assert set(credentials)=={"t3-recepcao","t3-recepcao-2"}
    assert credentials["t3-recepcao"]!=credentials["t3-recepcao-2"]
    assert all(len(value)>=24 for value in credentials.values())
