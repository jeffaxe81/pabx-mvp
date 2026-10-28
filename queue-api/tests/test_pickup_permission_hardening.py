"""Negativas do pickup quando o principal está malformado."""
from queue_access import may_pickup


def test_pickup_only_same_tenant_and_authorized_role():
    assert may_pickup({"tenant": "t1", "role": "agent", "extension": "t1-1001"}, "t1-1001")
    assert not may_pickup({"tenant": "t1", "role": "agent", "extension": "t1-1001"}, "t1-1002")
    assert may_pickup({"tenant": "t1", "role": "supervisor"}, "t1-1002")
    assert not may_pickup({"tenant": "t1", "role": "admin"}, "t10-1002")


def test_pickup_malformed_roles_fail_closed_without_exception():
    for role in ([], {}, ["admin"], {"name": "agent"}, None, 42):
        assert not may_pickup({"tenant": "t1", "role": role}, "t1-1001")
    for principal in ([], None, {"tenant": "t01", "role": "admin"}, {"tenant": "t1", "role": "root"}):
        assert not may_pickup(principal, "t1-1001")
