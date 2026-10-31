"""Atribuição conservadora de tenant a eventos AMI de monitoramento.

Somente identificadores completos derivados do AMI (fila ou channel
provisionado) são usados. Origem não atribuível nunca aparece na API.
"""
import re

from pickup import queue_tenant

_TENANT = re.compile(r"^t[1-9][0-9]*$")
_EXTENSION = re.compile(r"^(t[1-9][0-9]*)-[a-zA-Z0-9][a-zA-Z0-9-]*$")
_CHANNEL = re.compile(r"^PJSIP/(t[1-9][0-9]*-[a-zA-Z0-9][a-zA-Z0-9-]*)-[0-9a-fA-F]{8,}$")


def extension_tenant(extension):
    if not isinstance(extension, str) or len(extension) > 96:
        return None
    match = _EXTENSION.fullmatch(extension)
    return match.group(1) if match else None


def channel_tenant(channel):
    if not isinstance(channel, str) or len(channel) > 192:
        return None
    match = _CHANNEL.fullmatch(channel)
    return extension_tenant(match.group(1)) if match else None


def monitoring_event_tenant(event):
    """Queue events -> Queue; DialEnd/QualityStats -> AMI Channel.

    If optional AccountCode and channel/queue disagree, deny.
    An optional missing AccountCode is not a reason to fabricate tenant.
    """
    if not isinstance(event, dict):
        return None
    event_name = event.get("Event")
    if event_name == "QueueCallerAbandon":
        tenant = queue_tenant(event.get("Queue"))
    elif event_name == "DialEnd":
        tenant = channel_tenant(event.get("Channel"))
    elif event_name == "UserEvent" and event.get("UserEvent") == "QualityStats":
        tenant = channel_tenant(event.get("Channel"))
    else:
        return None
    if tenant is None:
        return None
    codes = [event[key] for key in ("AccountCode", "Accountcode") if key in event]
    if any(not isinstance(code, str) or not _TENANT.fullmatch(code)
           or code != tenant for code in codes):
        return None
    return tenant


def scoped_monitoring_entries(entries, tenant):
    if not isinstance(tenant, str) or not _TENANT.fullmatch(tenant):
        return []
    if not isinstance(entries, list):
        return []
    return [
        dict(entry) for entry in entries
        if isinstance(entry, dict) and entry.get("tenant") == tenant
    ]
