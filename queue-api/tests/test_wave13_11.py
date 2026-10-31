from pickup import queue_tenant, pickup_matches_queue

def test_pickup_fails_closed_on_oversized_queue_name():
    long_queue = "fila-t" + "1" * 110
    assert queue_tenant(long_queue) is None
    assert not pickup_matches_queue("t1-1001", long_queue)
    assert pickup_matches_queue("t1-1001","fila-t1")
    assert not pickup_matches_queue("t10-1001","fila-t1")
