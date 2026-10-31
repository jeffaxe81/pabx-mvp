"""AXE PABX puro: 1.000 canais PJSIP distintos e evidência de mailbox."""
import pytest
from lab.voicemail_checks import inspected_voicemail_channel

@pytest.mark.parametrize("case",[pytest.param(i,id=f"AXE-{i+8001:05d}") for i in range(1000)])
def test_voicemail_1000_correlated_channels_and_foreign_owners(case):
    suffix=f"{case+1:08x}"
    own=(f"PJSIP/t1-1001-{suffix}!t1-internal!*97!5!Up!"
         "VoiceMailMain!t1-1001@t1!123.1")
    if case<500:
        result=inspected_voicemail_channel(own,"t1-1001","t1")
        assert result=={"exact":True,"no_foreign":True}
    else:
        foreign=(f"PJSIP/t2-1001-{suffix}!t2-internal!*97!5!Up!"
                 "VoiceMailMain!t1-1001@t1!123.2")
        result=inspected_voicemail_channel(own+"\n"+foreign,"t1-1001","t1")
        assert result=={"exact":True,"no_foreign":False}
