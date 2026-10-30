"""Proteções operacionais da campanha: 10 entregas e testes negativos."""
import json

import pytest

from campaigns import (
    MAX_ATTEMPTS, create_campaign, find_campaign, load_campaigns,
    mark_contact_calling, mark_contact_result, next_pending_contact,
    sanitize_phone_number, validate_campaign_catalog, validate_campaign_input,
)

INPUT = {
    "tenant": "t1", "name": "Campanha T1", "agent_extension": "t1-recepcao",
    "contacts": ["11999998888", "11988887777"],
}


def setup_campaign(tmp_path):
    path = tmp_path / "campaigns.json"
    ok, error, entry = create_campaign(path, INPUT)
    assert ok, error
    return path, entry


def tamper(path, fn):
    rows = load_campaigns(path)
    fn(rows)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def test_01_refuses_symlink_with_existing_snapshot(tmp_path):
    path, _ = setup_campaign(tmp_path)
    alias = tmp_path / "alias.json"
    alias.symlink_to(path)
    with pytest.raises(ValueError, match="simbolico"):
        load_campaigns(alias)


def test_02_refuses_json_duplicate_fields(tmp_path):
    path, campaign = setup_campaign(tmp_path)
    text = json.dumps(campaign)
    text = text.replace('"id":', '"id": "duplicated", "id":', 1)
    path.write_text("[" + text + "]", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicado"):
        load_campaigns(path)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_03_refuses_non_finite_json_constants(tmp_path, value):
    path, campaign = setup_campaign(tmp_path)
    rows = [campaign]
    text = json.dumps(rows).replace('"attempts": 0', '"attempts": ' + value, 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="finito"):
        load_campaigns(path)


def test_04_refuses_duplicate_campaign_ids_across_tenants(tmp_path):
    path, _ = setup_campaign(tmp_path)
    tamper(path, lambda rows: rows.append({
        **rows[0], "tenant": "t10", "agent_extension": "t10-recepcao",
    }))
    with pytest.raises(ValueError, match="duplicado"):
        load_campaigns(path)
    # Low-level helper also refuses ambiguous lookups.
    rows = json.loads(path.read_text())
    assert find_campaign(rows, rows[0]["id"]) is None


@pytest.mark.parametrize("bad", [None, [], True, {"id": "x"}, [{"id": "bad"}]])
def test_05_refuses_malformed_catalog_shapes(tmp_path, bad):
    path, _ = setup_campaign(tmp_path)
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_campaigns(path)


def test_06_refuses_cross_tenant_agent_reassignment(tmp_path):
    path, _ = setup_campaign(tmp_path)
    tamper(path, lambda rows: rows[0].update(tenant="t10"))
    with pytest.raises(ValueError, match="tenant"):
        load_campaigns(path)


def test_07_refuses_duplicate_phone_in_same_campaign(tmp_path):
    path, _ = setup_campaign(tmp_path)
    tamper(path, lambda rows: rows[0]["contacts"].append(dict(rows[0]["contacts"][0])))
    with pytest.raises(ValueError, match="duplicado"):
        load_campaigns(path)


@pytest.mark.parametrize("status,attempts", [
    ("pendente", MAX_ATTEMPTS), ("pendente", -1), ("pendente", True),
    ("discando", 0), ("unknown", 0), ("atendida", MAX_ATTEMPTS + 1),
])
def test_08_refuses_inconsistent_retry_states(tmp_path, status, attempts):
    path, _ = setup_campaign(tmp_path)
    tamper(path, lambda rows: rows[0]["contacts"][0].update(
        status=status, attempts=attempts,
    ))
    with pytest.raises(ValueError):
        load_campaigns(path)


def test_09_refuses_uncorrelated_dialing_attempt(tmp_path):
    path, campaign = setup_campaign(tmp_path)
    number = campaign["contacts"][0]["number"]
    assert mark_contact_calling(path, campaign["id"], number)[0]
    tamper(path, lambda rows: rows[0]["contacts"][0].update(channel_id="axe-wrong"))
    with pytest.raises(ValueError, match="correlacionavel"):
        load_campaigns(path)


def test_10_ami_unknown_cannot_release_redial(tmp_path):
    path, campaign = setup_campaign(tmp_path)
    number = campaign["contacts"][0]["number"]
    assert mark_contact_calling(path, campaign["id"], number)[0]
    assert mark_contact_result(path, campaign["id"], number, "UNKNOWN")[0] is False
    rows = load_campaigns(path)
    contact = rows[0]["contacts"][0]
    assert contact["status"] == "discando"
    assert next_pending_contact(rows[0])["number"] == "11988887777"


def test_refuses_to_reserve_contact_at_attempt_limit_without_mutating(tmp_path):
    path, campaign = setup_campaign(tmp_path)
    # Simulates direct concurrent caller trying to reserve exhausted
    # pending state; invalid persisted state is rejected before mutation.
    rows = load_campaigns(path)
    rows[0]["contacts"][0]["attempts"] = MAX_ATTEMPTS
    path.write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(ValueError):
        mark_contact_calling(path, campaign["id"], "11999998888")
    assert json.loads(path.read_text())[0]["contacts"][0]["attempts"] == MAX_ATTEMPTS


@pytest.mark.parametrize("number", [
    "call to 11999998888", "+55+11999998888", "11999998888;session=1",
    "11999998888@trunk", "11999998888\nOriginate", "1" * 49,
])
def test_ambiguous_campaign_contacts_not_silently_dialed(number):
    assert sanitize_phone_number(number) is None


def test_valid_multitenant_catalog_and_legacy_readable(tmp_path):
    path, campaign = setup_campaign(tmp_path)
    legacy = {**campaign, "id": "0123456789ab"}
    legacy.pop("tenant")
    multi = {**campaign, "id": "abcdef012345", "tenant": "t10",
             "agent_extension": "t10-recepcao"}
    path.write_text(json.dumps([campaign, legacy, multi]), encoding="utf-8")
    assert validate_campaign_catalog(load_campaigns(path))
    assert len(load_campaigns(path)) == 3


def test_input_rejects_control_names_and_unsafe_agent():
    for data in (
        {**INPUT, "name": "A\r\nContext=INJECTED"},
        {**INPUT, "name": "N" * 101},
        {**INPUT, "agent_extension": "t1-recepcao;\nAction: Command"},
        {**INPUT, "agent_extension": "t10-recepcao", "tenant": "t1"},
    ):
        assert validate_campaign_input(data)[0] is False
