"""Amostras realistas de CLI PJSIP. Sem conexão Docker nesta suíte."""
import asterisk_lab_audit as audit
from test_asterisk_lab_audit import snapshots


def test_realistic_pjsip_option_lowercase_and_spaced_colon():
    sample = snapshots({})
    sample["endpoint:t1"]["output"] = (
        " Endpoint:  t1-1001/1001 Unavailable   0 of inf\n"
        "    InAuth: t1-1001/t1-1001\n"
        "   context                        : t1-internal\n"
        "   direct_media                   : false\n"
    )
    report = audit.check_snapshots(sample, {})
    assert report["checks"]["endpoint_exists:t1"]
    assert report["checks"]["endpoint_context:t1"]


def test_realistic_pjsip_context_case_insensitive():
    sample = snapshots({})
    sample["endpoint:t2"]["output"] = (
        "Endpoint: t2-1001/1001 Unavailable\n"
        "ConTeXt : t2-internal\n"
    )
    report = audit.check_snapshots(sample, {})
    assert report["checks"]["endpoint_context:t2"]


def test_context_mention_outside_property_not_trusted():
    sample = snapshots({})
    sample["endpoint:t1"]["output"] = (
        "Endpoint: t1-1001/1001\n"
        "Unexpected diagnostic: context : t1-internal\n"
        "context : t2-internal\n"
    )
    report = audit.check_snapshots(sample, {})
    assert report["checks"]["endpoint_exists:t1"]
    assert not report["checks"]["endpoint_context:t1"]


def test_cross_tenant_context_with_similar_prefix_rejected():
    sample = snapshots({})
    sample["endpoint:t1"]["output"] = (
        "Endpoint: t1-1001/1001\n"
        "context : t1-internal-other\n"
    )
    report = audit.check_snapshots(sample, {})
    assert not report["checks"]["endpoint_context:t1"]


def test_absent_endpoint_banner_does_not_validate_context_only():
    sample = snapshots({})
    sample["endpoint:t2"]["output"] = "context : t2-internal\n"
    report = audit.check_snapshots(sample, {})
    assert not report["checks"]["endpoint_exists:t2"]
    assert not report["checks"]["endpoint_context:t2"]
