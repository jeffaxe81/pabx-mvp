"""AMI TCP client: one socket reader, ActionID correlation, bounded frames.

A single reader owns recv().  HTTP requests only write requests and wait for
their own ActionID; callbacks run on a separate worker, so a callback may
originate another AMI action without deadlocking the socket reader.
"""
import queue
import secrets
import socket
import threading
import time

from ami_protocol import parse_ami_blocks, build_action

MAX_AMI_FRAME_BYTES = 128 * 1024
MAX_AMI_EVENTS_QUEUED = 1024
DEFAULT_ACTION_TIMEOUT = 5


class AMIClient:
    def __init__(self, host, port, username, secret, on_event=None):
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self.on_event = on_event
        self._sock = None
        self._buffer = b""
        self._running = False
        self._send_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending = {}
        self._event_queue = queue.Queue(maxsize=MAX_AMI_EVENTS_QUEUED)
        self._reader_thread = None
        self._events_thread = None

    def _fail_pending(self, error):
        with self._pending_lock:
            items = list(self._pending.values())
            self._pending.clear()
        for waiter in items:
            waiter["error"] = error
            waiter["ready"].set()

    def connect_and_login(self, timeout=5):
        if self._running:
            raise ConnectionError("AMI already connected")
        self._sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self._buffer = b""
        try:
            self._sock.settimeout(1.0)
            deadline = time.monotonic() + timeout
            # Asterisk sends a plain-text banner line before AMI frames.
            # Preserve any already-read post-banner bytes for the reader.
            while b"\n" not in self._buffer:
                if len(self._buffer) >= MAX_AMI_FRAME_BYTES:
                    raise ConnectionError("AMI banner too large")
                if time.monotonic() >= deadline:
                    raise TimeoutError("AMI banner timeout")
                try:
                    chunk = self._sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    raise ConnectionError("AMI disconnected before banner")
                self._buffer += chunk
            banner, self._buffer = self._buffer.split(b"\n", 1)
            if not banner.strip().startswith(b"Asterisk Call Manager/"):
                raise ConnectionError("Invalid AMI banner")
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_loop, name="ami-reader", daemon=True)
            self._events_thread = threading.Thread(target=self._process_events, name="ami-events", daemon=True)
            self._reader_thread.start()
            self._events_thread.start()
            reply = self.send_action({
                "Action": "Login", "Username": self.username, "Secret": self.secret,
            }, timeout=timeout)
            if reply.get("Response") != "Success":
                raise ConnectionError("AMI login rejected")
        except Exception:
            self.stop()
            raise

    def _dispatch_frame(self, frame):
        parsed = parse_ami_blocks(frame.decode("utf-8", errors="replace"))
        if len(parsed) != 1:
            raise ConnectionError("Invalid AMI frame")
        block = parsed[0]
        if block.get("Event"):
            if self.on_event:
                try:
                    self._event_queue.put_nowait(block)
                except queue.Full as exc:
                    raise ConnectionError("AMI event queue exhausted") from exc
            return
        action_id = block.get("ActionID")
        if not action_id or "Response" not in block:
            # Never treat anonymous frames as successful action replies.
            return
        with self._pending_lock:
            waiter = self._pending.pop(action_id, None)
        if waiter is not None:
            waiter["response"] = block
            waiter["ready"].set()

    def _read_loop(self):
        try:
            while self._running:
                if b"\r\n\r\n" in self._buffer:
                    frame, self._buffer = self._buffer.split(b"\r\n\r\n", 1)
                    if frame:
                        self._dispatch_frame(frame)
                    continue
                if len(self._buffer) >= MAX_AMI_FRAME_BYTES:
                    raise ConnectionError("AMI frame too large")
                try:
                    chunk = self._sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                self._buffer += chunk
                if len(self._buffer) > MAX_AMI_FRAME_BYTES:
                    raise ConnectionError("AMI incoming buffer too large")
        except (OSError, ConnectionError):
            # A broken event stream must fail actions closed. Caller can
            # reconnect explicitly instead of guessing whether AMI accepted.
            pass
        finally:
            self._running = False
            self._fail_pending(ConnectionError("AMI event stream interrupted"))

    def _process_events(self):
        while self._running or not self._event_queue.empty():
            try:
                event = self._event_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                if self.on_event:
                    self.on_event(event)
            except Exception:
                # An application event callback must not kill the AMI reader.
                # Never log raw events, which may include customer numbers.
                print("[AMI] event handler error")
            finally:
                self._event_queue.task_done()

    def _send_action_and_wait(self, fields: dict, timeout=DEFAULT_ACTION_TIMEOUT) -> dict:
        if not self._running or self._sock is None:
            raise ConnectionError("AMI is not connected")
        action_id = fields.get("ActionID") or "axe-queue-" + secrets.token_hex(12)
        if not isinstance(action_id, str) or not 1 <= len(action_id) <= 128:
            raise ValueError("Invalid AMI ActionID")
        action = build_action({**fields, "ActionID": action_id}).encode("utf-8")
        waiter = {"ready": threading.Event(), "response": None, "error": None}
        with self._pending_lock:
            if action_id in self._pending:
                raise ConnectionError("Duplicate AMI ActionID")
            self._pending[action_id] = waiter
        try:
            with self._send_lock:
                if not self._running:
                    raise ConnectionError("AMI connection closed")
                self._sock.sendall(action)
            if not waiter["ready"].wait(timeout):
                raise TimeoutError("AMI action response timeout")
            if waiter["error"] is not None:
                raise waiter["error"]
            if waiter["response"] is None:
                raise ConnectionError("AMI action reply missing")
            return waiter["response"]
        finally:
            with self._pending_lock:
                self._pending.pop(action_id, None)

    def send_action(self, fields: dict) -> dict:
        return self._send_action_and_wait(fields)

    def redirect_channel(self, channel: str, context: str, exten: str = "s", priority: int = 1) -> dict:
        return self.send_action({
            "Action": "Redirect", "Channel": channel, "Context": context,
            "Exten": exten, "Priority": str(priority),
        })

    def block_number(self, number: str) -> dict:
        return self.send_action({
            "Action": "DBPut", "Family": "blocklist", "Key": number, "Val": "1",
        })

    def pause_member(self, interface: str, paused: bool, reason: str = "") -> dict:
        action = {"Action": "QueuePause", "Interface": interface,
                  "Paused": "true" if paused else "false"}
        if reason:
            action["Reason"] = reason
        return self.send_action(action)

    def start_event_loop(self):
        """Compatibility: event processing starts with connect_and_login()."""
        if not self._running:
            raise ConnectionError("AMI is not connected")

    def stop(self):
        self._running = False
        self._fail_pending(ConnectionError("AMI client stopped"))
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sock.close()
