"""Live socketpair regression for a single AMI reader and correlated replies."""
import concurrent.futures
import socket
import threading
import time

import pytest

from ami_client import AMIClient, MAX_AMI_FRAME_BYTES
from ami_protocol import parse_ami_blocks


def frames(sock):
    """Receive full AMI frames in a worker simulating a real Asterisk."""
    buf = b""
    while True:
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                return
            buf += chunk
        raw, buf = buf.split(b"\r\n\r\n", 1)
        if raw:
            yield parse_ami_blocks(raw.decode() + "\r\n\r\n")[0]


def reply(sock, action, message="ok", response="Success"):
    frame = ("Response: " + response + "\r\nActionID: " + action["ActionID"]
             + "\r\nMessage: " + message + "\r\n\r\n")
    sock.sendall(frame.encode())


def connected(on_event=None):
    a, b = socket.socketpair()
    a.settimeout(0.1)
    b.settimeout(3)
    client = AMIClient("127.0.0.1", 5038, "test", "secret", on_event=on_event)
    client._sock = a
    client._running = True
    client._reader_thread = threading.Thread(target=client._read_loop, daemon=True)
    client._events_thread = threading.Thread(target=client._process_events, daemon=True)
    client._reader_thread.start()
    client._events_thread.start()
    return client, b


def test_split_response_and_unrelated_event_do_not_steal_reply():
    events = []
    client, server = connected(on_event=lambda event: events.append(event))
    try:
        def responder():
            action = next(frames(server))
            server.sendall(b"Event: PeerStatus\r\nPeer: t1-1001\r\n\r\n")
            blob = ("Response: Success\r\nActionID: " + action["ActionID"]
                    + "\r\nMessage: correct\r\n\r\n").encode()
            for chunk in (blob[:5], blob[5:23], blob[23:]):
                server.sendall(chunk)
        thread = threading.Thread(target=responder)
        thread.start()
        result = client.send_action({"Action": "Ping"})
        thread.join(3)
        assert result["Message"] == "correct"
        assert client._event_queue.join() is None
        assert [e["Event"] for e in events] == ["PeerStatus"]
    finally:
        client.stop()
        server.close()


def test_concurrent_replies_out_of_order_are_correlated_by_action_id():
    client, server = connected()
    try:
        def responder():
            source = frames(server)
            first, second = next(source), next(source)
            reply(server, second, second["Action"])
            reply(server, first, first["Action"])
        thread = threading.Thread(target=responder)
        thread.start()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(client.send_action, {"Action": "Ping"})
            f2 = pool.submit(client.send_action, {"Action": "QueueStatus"})
            assert f1.result(timeout=3)["Message"] == "Ping"
            assert f2.result(timeout=3)["Message"] == "QueueStatus"
        thread.join(3)
    finally:
        client.stop()
        server.close()


def test_event_handler_can_send_ami_action_without_reader_deadlock():
    done = threading.Event()
    result = {}
    client = None

    def callback(event):
        result["reply"] = client.send_action({"Action": "Ping"})["Response"]
        done.set()

    client, server = connected(on_event=callback)
    try:
        def responder():
            source = frames(server)
            first = next(source)
            server.sendall(b"Event: QueueCallerJoin\r\nQueue: t1\r\n\r\n")
            reply(server, first)
            followup = next(source)
            reply(server, followup)
        thread = threading.Thread(target=responder)
        thread.start()
        assert client.send_action({"Action": "QueueStatus"})["Response"] == "Success"
        assert done.wait(3)
        assert result["reply"] == "Success"
        thread.join(3)
    finally:
        client.stop()
        server.close()


def test_stale_or_unknown_action_id_cannot_authorize_originate():
    client, server = connected()
    try:
        def responder():
            action = next(frames(server))
            server.sendall(b"Response: Success\r\nActionID: unrelated\r\n\r\n")
        thread = threading.Thread(target=responder)
        thread.start()
        with pytest.raises(TimeoutError):
            client._send_action_and_wait({"Action": "Originate", "ActionID": "1" * 32}, timeout=0.15)
        thread.join(3)
    finally:
        client.stop()
        server.close()


def test_disconnected_socket_fails_outstanding_action_closed():
    client, server = connected()
    try:
        def responder():
            next(frames(server))
            server.shutdown(socket.SHUT_RDWR)
            server.close()
        thread = threading.Thread(target=responder)
        thread.start()
        with pytest.raises(ConnectionError):
            client.send_action({"Action": "Originate"})
        thread.join(3)
        assert client._running is False
    finally:
        client.stop()


def test_oversized_incoming_frame_fails_pending_request():
    client, server = connected()
    try:
        def responder():
            next(frames(server))
            server.sendall(b"A" * (MAX_AMI_FRAME_BYTES + 8192))
        thread = threading.Thread(target=responder)
        thread.start()
        with pytest.raises(ConnectionError):
            client.send_action({"Action": "Originate"})
        thread.join(3)
    finally:
        client.stop()
        server.close()


def test_fragmented_login_banner_and_post_banner_event(monkeypatch):
    a, server = socket.socketpair()
    a.settimeout(0.1)
    server.settimeout(3)
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: a)
    seen = []
    client = AMIClient("host", 5038, "queue-api", "safe-password", on_event=seen.append)
    try:
        def responder():
            server.sendall(b"Asterisk Call Man")
            server.sendall(b"ager/5.0\r\nEvent: PeerStatus\r\nPeer: t1\r\n\r\n")
            action = next(frames(server))
            assert action["Action"] == "Login"
            assert action["Secret"] == "safe-password"
            reply(server, action)
        thread = threading.Thread(target=responder)
        thread.start()
        client.connect_and_login(timeout=2)
        client.start_event_loop()
        client._event_queue.join()
        assert [x["Event"] for x in seen] == ["PeerStatus"]
        thread.join(3)
    finally:
        client.stop()
        server.close()


def test_duplicate_action_id_is_rejected_without_sending_twice():
    client, server = connected()
    try:
        first_received = threading.Event()
        def responder():
            first = next(frames(server))
            first_received.set()
            time.sleep(0.25)
            reply(server, first)
        worker = threading.Thread(target=responder)
        worker.start()
        result = {}
        def first_request():
            result["first"] = client._send_action_and_wait({"Action": "Ping", "ActionID": "a" * 32}, timeout=2)
        call = threading.Thread(target=first_request)
        call.start()
        assert first_received.wait(2)
        with pytest.raises(ConnectionError, match="Duplicate"):
            client.send_action({"Action": "Originate", "ActionID": "a" * 32})
        call.join(3)
        worker.join(3)
        assert result["first"]["Response"] == "Success"
    finally:
        client.stop()
        server.close()
