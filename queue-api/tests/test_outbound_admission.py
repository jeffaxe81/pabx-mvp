"""CTI Originate admission: 20 checks of concurrency, tenant and retries."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from outbound_admission import OriginateAdmission

T1 = "t1"
T10 = "t10"
EXT1 = "t1-recepcao"
EXT10 = "t10-recepcao"
NUMBER = "11999998888"
KEY = "CRM-REQUEST-0001"


def guard(**kwargs):
    return OriginateAdmission(**kwargs)


def reserve(g, tenant=T1, ext=EXT1, number=NUMBER, key=None):
    return g.reserve(tenant, ext, number, key)


def test_valid_originate_returns_opaque_ticket_and_no_customer_data():
    g = guard()
    status, ticket = reserve(g)
    assert status == "reserved" and type(ticket) is int
    assert g.finish(ticket, "accepted")
    assert "11999998888" not in str(g.snapshot())


@pytest.mark.parametrize("tenant,ext,number,key", [
    ("t01", EXT1, NUMBER, None),
    (T1, EXT10, NUMBER, None),
    ("t1;rm", EXT1, NUMBER, None),
    (T1, "t1-\nInjected", NUMBER, None),
    (T1, EXT1, "555", None),
    (T1, EXT1, NUMBER, "tiny"),
    (T1, EXT1, NUMBER, "bad request id"),
    (T1, EXT1, NUMBER, []),
    (T1, EXT1, NUMBER, True),
])
def test_bad_identity_number_or_request_id_fails_closed(tenant, ext, number, key):
    assert guard().reserve(tenant, ext, number, key) == ("unavailable", None)


def test_request_id_duplicate_after_success_does_not_originate_again():
    g = guard()
    state, ticket = reserve(g, key=KEY)
    assert state == "reserved"
    g.finish(ticket, "accepted")
    assert reserve(g, key=KEY) == ("duplicate", None)


def test_pending_same_request_is_not_submitted_twice():
    g = guard()
    assert reserve(g, key=KEY)[0] == "reserved"
    assert reserve(g, key=KEY) == ("pending", None)


def test_request_id_with_other_number_conflicts_even_after_acceptance():
    g = guard()
    _, ticket = reserve(g, key=KEY)
    g.finish(ticket, "accepted")
    assert reserve(g, number="11988887777", key=KEY) == ("conflict", None)


def test_request_id_with_other_extension_conflicts():
    g = guard()
    status, ticket = reserve(g, key=KEY)
    assert status == "reserved"
    g.finish(ticket, "accepted")
    assert reserve(g, ext="t1-recepcao-2", key=KEY) == ("conflict", None)


def test_same_request_id_in_other_tenant_is_isolated():
    g = guard()
    assert reserve(g, key=KEY)[0] == "reserved"
    assert reserve(g, tenant=T10, ext=EXT10, key=KEY)[0] == "reserved"


def test_timeout_preserves_uncertain_instead_of_false_success():
    g = guard()
    _, ticket = reserve(g, key=KEY)
    g.finish(ticket, "uncertain")
    assert reserve(g, key=KEY) == ("pending", None)


def test_explicit_rejection_allows_retry_with_same_key():
    g = guard()
    _, ticket = reserve(g, key=KEY)
    g.finish(ticket, "rejected")
    assert reserve(g, key=KEY)[0] == "reserved"


def test_process_local_idempotency_expires_after_ttl():
    clock = [1000.0]
    g = guard(idempotency_seconds=10, clock=lambda: clock[0])
    _, ticket = reserve(g, key=KEY)
    g.finish(ticket, "accepted")
    clock[0] = 1011.0
    assert reserve(g, key=KEY)[0] == "reserved"


def test_backward_clock_clears_windows_conservatively():
    clock = [1000.0]
    g = guard(per_extension_per_minute=1, clock=lambda: clock[0])
    assert reserve(g)[0] == "reserved"
    clock[0] = 900.0
    # Um relógio regressivo bloqueia novas originações, sem limpar
    # contadores para permitir burst indevido.
    assert reserve(g)[0] == "unavailable"


def test_tenant_rate_limit_blocks_burst():
    g = guard(per_tenant_per_minute=2, per_extension_per_minute=2)
    for ext in ("t1-recepcao", "t1-recepcao-2"):
        status, ticket = reserve(g, ext=ext)
        assert status == "reserved"
        g.finish(ticket, "accepted")
    assert reserve(g, ext="t1-1001") == ("limited", None)


def test_extension_rate_limit_is_independent_per_extension():
    g = guard(per_tenant_per_minute=3, per_extension_per_minute=1)
    _, first = reserve(g)
    g.finish(first, "accepted")
    assert reserve(g) == ("limited", None)
    assert reserve(g, ext="t1-1001")[0] == "reserved"


def test_other_tenant_not_limited_by_first_tenant_burst():
    g = guard(per_tenant_per_minute=1, per_extension_per_minute=1)
    assert reserve(g)[0] == "reserved"
    assert reserve(g, ext="t1-1001") == ("limited", None)
    assert reserve(g, tenant=T10, ext=EXT10)[0] == "reserved"


def test_rate_window_expires_at_sixty_seconds():
    clock = [1000.0]
    g = guard(per_tenant_per_minute=1, per_extension_per_minute=1,
              clock=lambda: clock[0])
    _, ticket = reserve(g)
    g.finish(ticket, "accepted")
    clock[0] = 1059
    assert reserve(g)[0] == "limited"
    clock[0] = 1060
    assert reserve(g)[0] == "reserved"


def test_global_inflight_limit_blocks_simultaneous_originate():
    g = guard(max_inflight=1)
    assert reserve(g)[0] == "reserved"
    assert reserve(g, tenant=T10, ext=EXT10)[0] == "limited"


def test_finishing_request_releases_inflight_capacity():
    g = guard(max_inflight=1)
    _, first = reserve(g)
    assert g.finish(first, "accepted")
    assert reserve(g, tenant=T10, ext=EXT10)[0] == "reserved"


def test_duplicate_finish_is_noop():
    g = guard()
    _, ticket = reserve(g)
    assert g.finish(ticket, "accepted")
    assert g.finish(ticket, "accepted") is False
    assert g.snapshot()["inflight"] == 0


def test_malformed_clock_cannot_authorize_origination():
    for clock in (lambda: float("nan"), lambda: float("inf"),
                  lambda: None, lambda: -1, lambda: "1"):
        assert reserve(guard(clock=clock)) == ("unavailable", None)


@pytest.mark.parametrize("params", [
    {"per_tenant_per_minute": 0},
    {"per_extension_per_minute": True},
    {"per_tenant_per_minute": 1, "per_extension_per_minute": 2},
    {"max_inflight": -1},
    {"idempotency_seconds": 10001},
])
def test_invalid_limits_are_rejected(params):
    with pytest.raises(ValueError):
        guard(**params)


def test_parallel_identical_idempotency_only_reserves_once():
    g = guard(max_inflight=40)
    with ThreadPoolExecutor(max_workers=12) as workers:
        rows = list(workers.map(lambda _: reserve(g, key=KEY), range(40)))
    assert sum(result == "reserved" for result, _ in rows) == 1
    assert all(result in {"reserved", "pending"} for result, _ in rows)


def test_invalid_finish_state_does_not_modify_reservation():
    g = guard()
    _, ticket = reserve(g, key=KEY)
    with pytest.raises(ValueError):
        g.finish(ticket, "made-up")
    assert reserve(g, key=KEY) == ("pending", None)
