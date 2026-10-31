"""100-test cycle 81–90: Asterisk PJSIP and dialplan static contracts."""
from pathlib import Path
from conf_parser import parse_blocks,get_key,get_key_inherited,blocks_by_type

ROOT=Path(__file__).resolve().parents[1]/"asterisk"

def blocks(name):
    return parse_blocks(ROOT/name)

def item(name,section,kind):
    return next(row for row in blocks_by_type(blocks(name),kind)
                if row["name"]==section)

def test_081_udp_sip_transport_exists():
    assert get_key(item("pjsip.conf","transport-udp","transport")["text"],"protocol")=="udp"

def test_082_tls_sip_transport_has_certificate():
    conf=item("pjsip.conf","transport-tls","transport")["text"]
    assert get_key(conf,"cert_file") and get_key(conf,"priv_key_file")

def test_083_websocket_secure_transport_exists():
    assert get_key(item("pjsip.conf","transport-wss","transport")["text"],"protocol")=="wss"

def test_084_secure_sip_extension_requires_srtp():
    all_blocks=blocks("pjsip.conf")
    ext=next(x for x in all_blocks if x["name"]=="t1-1001" and x["template_ref"])
    assert get_key_inherited(ext,"media_encryption",all_blocks)=="sdes"

def test_085_webrtc_extension_uses_dtls():
    all_blocks=blocks("pjsip.conf")
    ext=next(x for x in all_blocks if x["name"]=="t1-recepcao" and x["template_ref"])
    assert get_key_inherited(ext,"media_encryption",all_blocks)=="dtls"

def test_086_identify_trunk_has_fixed_ip_match():
    for name in ("gateway-tdm","gateway-tdm-2"):
        assert get_key(item("pjsip.conf",name,"identify")["text"],"match")

def test_087_trunks_have_distinct_contacts():
    a=get_key(item("pjsip.conf","gateway-tdm","aor")["text"],"contact")
    b=get_key(item("pjsip.conf","gateway-tdm-2","aor")["text"],"contact")
    assert a.startswith("sip:") and b.startswith("sip:") and a!=b

def test_088_t1_t2_calling_contexts_are_distinct():
    a=item("pjsip.conf","t1-1001","endpoint")["text"]
    b=item("pjsip.conf","t2-1001","endpoint")["text"]
    assert get_key(a,"context")=="t1-internal"
    assert get_key(b,"context")=="t2-internal"

def test_089_unknown_did_has_explicit_hangup():
    ingress=next(x["text"] for x in blocks("extensions.conf")
                if x["name"]=="from-tdm-gateway")
    assert "tenant-did/" in ingress and "did-desconhecido" in ingress
    assert "Hangup(21)" in ingress

def test_090_parking_slots_are_isolated_per_company():
    names={x["name"]:x["text"] for x in blocks("res_parking.conf")}
    for tenant in ("t1","t2"):
        section=names["parkinglot-"+tenant]
        assert get_key(section,"context")==tenant+"-internal"
        assert get_key(section,"parkpos")=="76-95"
        assert get_key(section,"comebacktoorigin")=="yes"
