"""Voicemail runtime evidence must not mask a simultaneous cross-tenant mailbox."""
from lab.voicemail_checks import inspected_voicemail_channel

def row(ep, mailbox, suffix="00000001"):
    tenant=ep.split("-",1)[0]
    return f"PJSIP/{ep}-{suffix}!{tenant}-internal!*97!5!Up!VoiceMailMain!{mailbox}!123.1"

def test_voicemail_observer_accepts_two_legitimate_tenant_channels():
    text=row("t1-1001","t1-1001@t1")+"\n"+row("t2-1001","t2-1001@t2")
    assert inspected_voicemail_channel(text,"t1-1001","t1")=={"exact":True,"no_foreign":True}

def test_voicemail_observer_flags_other_tenant_reading_t1_mailbox():
    text=row("t1-1001","t1-1001@t1")+"\n"+row("t2-1001","t1-1001@t1")
    assert inspected_voicemail_channel(text,"t1-1001","t1")=={"exact":True,"no_foreign":False}

def test_voicemail_observer_flags_cross_tenant_context_in_other_leg():
    text=row("t1-1001","t1-1001@t1")+"\n"+(
        "PJSIP/t2-1001-00000002!t1-internal!*97!5!Up!VoiceMailMain!t2-1001@t2!")
    assert not inspected_voicemail_channel(text,"t1-1001","t1")["no_foreign"]

def test_voicemail_observer_still_rejects_wrong_target_mailbox():
    assert inspected_voicemail_channel(row("t1-1001","t2-1001@t2"),
                                       "t1-1001","t1")=={"exact":False,"no_foreign":False}
