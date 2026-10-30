"""Admission control (memory only) for CRM click-to-call Asterisk Originate.

Guarantees are per Python process, NOT distributed across PABX instances.
Never stores a dialed number, token, CallerID, audio or request payload.
"""
from collections import deque, OrderedDict
import hashlib
import hmac
import math
import re
import threading
import time

_TENANT = re.compile(r"t[1-9][0-9]*\Z")
_EXTENSION = re.compile(r"t[1-9][0-9]*-[a-z0-9][a-z0-9_-]{0,79}\Z")
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{12,96}\Z")


class OriginateAdmission:
    """Bounded, synchronized, fail-closed admission for HTTP Originate.

    reserve -> (status, opaque internal ticket):
      reserved / duplicate / pending / conflict / limited / unavailable.
    finish(ticket, outcome) with outcome accepted/rejected/uncertain.
    """

    def __init__(self, per_tenant_per_minute=30, per_extension_per_minute=10,
                 max_inflight=50, idempotency_seconds=180, clock=None):
        if (any(type(n) is not int or n < 1 or n > 10000
                for n in (per_tenant_per_minute, per_extension_per_minute,
                          max_inflight, idempotency_seconds))
                or per_extension_per_minute > per_tenant_per_minute):
            raise ValueError("limites de originação inválidos")
        self.per_tenant = per_tenant_per_minute
        self.per_extension = per_extension_per_minute
        self.max_inflight = max_inflight
        self.ttl = idempotency_seconds
        self.clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._tenant_window = {}
        self._extension_window = {}
        self._requests = OrderedDict()
        self._inflight = {}
        self._sequence = 0
        self._last_time = None

    def _time(self):
        now = self.clock()
        return now if type(now) in (int, float) and math.isfinite(now) and now >= 0 else None

    def _cleanup(self, now):
        # Strict bounded lifetime of both rate and idempotency keys.
        for mapping in (self._tenant_window, self._extension_window):
            for key, q in list(mapping.items()):
                while q and (q[0] > now or now - q[0] >= 60):
                    q.popleft()
                if not q:
                    mapping.pop(key, None)
        for key, row in list(self._requests.items()):
            if now < row["when"] or now - row["when"] >= self.ttl:
                # Pending timeouts have unknown AMI outcome; allow retry
                # only after TTL expires. No false "success" is returned.
                self._requests.pop(key, None)
        for ticket, row in list(self._inflight.items()):
            if now < row["when"] or now - row["when"] >= self.ttl:
                self._inflight.pop(ticket, None)

    def reserve(self, tenant, extension, number, request_id=None):
        if (not isinstance(tenant, str) or _TENANT.fullmatch(tenant) is None
                or not isinstance(extension, str) or _EXTENSION.fullmatch(extension) is None
                or not extension.startswith(tenant + "-")
                or not isinstance(number, str) or not re.fullmatch(r"\+?[0-9]{8,15}", number)
                or request_id is not None and (
                    not isinstance(request_id, str)
                    or _REQUEST_ID.fullmatch(request_id) is None)):
            return "unavailable", None
        now = self._time()
        if now is None:
            return "unavailable", None
        # Digest for process-local comparison; never exposed.
        fingerprint = hashlib.sha256((tenant + "\0" + extension + "\0" + number).encode()).digest()
        key = (tenant, request_id) if request_id is not None else None
        with self._lock:
            if self._last_time is not None and now < self._last_time:
                return "unavailable", None
            self._last_time = now
            self._cleanup(now)
            if key is not None and key in self._requests:
                entry = self._requests[key]
                if not hmac.compare_digest(entry["fingerprint"], fingerprint):
                    return "conflict", None
                if entry["state"] == "accepted":
                    return "duplicate", None
                return "pending", None
            tenant_window = self._tenant_window.get(tenant)
            extension_key = (tenant, extension)
            extension_window = self._extension_window.get(extension_key)
            if len(self._inflight) >= self.max_inflight:
                return "limited", None
            if (tenant_window is not None and len(tenant_window) >= self.per_tenant or
                    extension_window is not None and len(extension_window) >= self.per_extension):
                return "limited", None
            if len(self._tenant_window) >= 1000 and tenant not in self._tenant_window:
                return "limited", None
            if len(self._extension_window) >= 5000 and extension_key not in self._extension_window:
                return "limited", None
            if key is not None and len(self._requests) >= 10000:
                return "limited", None
            self._sequence += 1
            ticket = self._sequence
            self._tenant_window.setdefault(tenant, deque()).append(now)
            self._extension_window.setdefault(extension_key, deque()).append(now)
            self._inflight[ticket] = {"when": now, "key": key}
            if key is not None:
                self._requests[key] = {"fingerprint": fingerprint, "state": "pending", "when": now}
            return "reserved", ticket

    def finish(self, ticket, outcome):
        """Records explicit Success/Error or indeterminate transport failure."""
        if type(ticket) is not int or outcome not in {"accepted", "rejected", "uncertain"}:
            raise ValueError("resultado de originação inválido")
        with self._lock:
            row = self._inflight.pop(ticket, None)
            if row is None:
                return False
            key = row["key"]
            if key is not None and key in self._requests:
                if outcome == "rejected":
                    self._requests.pop(key, None)
                else:
                    self._requests[key]["state"] = outcome
            return True

    def snapshot(self):
        """Counts only; no tenant ids, phone numbers or request ids."""
        now = self._time()
        with self._lock:
            if now is not None:
                self._cleanup(now)
            return {
                "inflight": len(self._inflight),
                "idempotency_entries": len(self._requests),
                "tenant_windows": len(self._tenant_window),
                "extension_windows": len(self._extension_window),
                "operational_homologated": False,
            }
