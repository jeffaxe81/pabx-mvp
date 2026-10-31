"""Bateria PABX puro #21-30: configuração versionada, não é teste SIP em campo."""
from pathlib import Path
from conf_parser import parse_blocks, get_key, get_key_inherited, blocks_by_type

ROOT = Path(__file__).resolve().parents[1] / "asterisk"


def _all(name):
    return parse_blocks(ROOT / name)


def _typed(name, kind):
    return {b["name"]: b for b in blocks_by_type(_all(name), kind)}


def test_21_pjsip_tls_declares_certificate_and_private_key():
    transport = _typed("pjsip.conf", "transport")["transport-tls"]
    assert get_key(transport["text"], "protocol") == "tls"
    assert get_key(transport["text"], "cert_file")
    assert get_key(transport["text"], "priv_key_file")


def test_22_hardended_sip_template_disallows_opportunistic_encryption():
    blocks = _all("pjsip.conf")
    template = next(x for x in blocks if x["name"] == "endpoint-secure")
    assert get_key_inherited(template, "media_encryption", blocks) == "sdes"
    assert get_key(template["text"], "media_encryption_optimistic") == "no"


def test_23_webrtc_template_requires_wss_and_dtls_srtp():
    blocks = _all("pjsip.conf")
    template = next(x for x in blocks if x["name"] == "endpoint-webrtc")
    assert get_key_inherited(template, "transport", blocks) == "transport-wss"
    assert get_key_inherited(template, "media_encryption", blocks) == "dtls"
    assert get_key_inherited(template, "rtcp_mux", blocks) == "yes"


def test_24_base_sip_audio_codecs_have_g711_and_opus():
    blocks = _all("pjsip.conf")
    template = next(x for x in blocks if x["name"] == "endpoint-base")
    codecs = get_key(template["text"], "allow").split(",")
    assert {"ulaw", "alaw", "opus"} <= set(codecs)


def test_25_identical_extension_numbers_use_separate_dialplan_contexts():
    endpoints = _typed("pjsip.conf", "endpoint")
    assert get_key(endpoints["t1-1001"]["text"], "context") == "t1-internal"
    assert get_key(endpoints["t2-1001"]["text"], "context") == "t2-internal"


def test_26_sip_endpoints_bind_to_own_authentication_and_aor():
    endpoints = _typed("pjsip.conf", "endpoint")
    for name in ("t1-1001", "t1-1002", "t2-1001"):
        assert get_key(endpoints[name]["text"], "auth") == name
        assert get_key(endpoints[name]["text"], "aors") == name


def test_27_legacy_gateway_trunks_have_ip_identify_and_aor():
    blocks = _all("pjsip.conf")
    for name in ("gateway-tdm", "gateway-tdm-2"):
        endpoint = next(x for x in blocks if x["name"] == name and get_key(x["text"], "type") == "endpoint")
        assert get_key(endpoint["text"], "context") == "from-tdm-gateway"
        assert get_key(endpoint["text"], "identify_by") == "ip"
        assert any(x["name"] == name and get_key(x["text"], "type") == "identify" for x in blocks)
        assert any(x["name"] == name and get_key(x["text"], "type") == "aor" for x in blocks)


def test_28_inbound_did_unknown_destination_must_hangup():
    contexts = {x["name"]: x["text"] for x in _all("extensions.conf")}
    ingress = contexts["from-tdm-gateway"]
    assert "tenant-did/" in ingress
    assert "did-desconhecido" in ingress
    assert "Hangup(21)" in ingress


def test_29_parking_same_numbers_remain_tenant_scoped():
    lots = {x["name"]: x["text"] for x in _all("res_parking.conf")}
    for tenant in ("t1", "t2"):
        text = lots["parkinglot-" + tenant]
        assert get_key(text, "context") == tenant + "-internal"
        assert get_key(text, "parkext") == "75"
        assert get_key(text, "parkpos") == "76-95"
        assert get_key(text, "comebacktoorigin") == "yes"


def test_30_direct_call_recording_has_tenant_cdr_marker():
    contexts = {x["name"]: x["text"] for x in _all("extensions.conf")}
    for tenant in ("t1", "t2"):
        content = contexts[tenant + "-internal"]
        assert "Set(CDR(accountcode)=" + tenant + ")" in content
        assert "MixMonitor(" in content
