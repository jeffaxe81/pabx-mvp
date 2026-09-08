from agi_protocol import parse_agi_env, build_record_command, build_set_variable_command, build_stream_file_command, parse_agi_response


# ---------- parse_agi_env ----------

def test_parse_agi_env_basic():
    lines = ["agi_channel: PJSIP/t1-recepcao-00000001", "agi_uniqueid: 1700000000.5", "agi_callerid: 5511999998888"]
    env = parse_agi_env(lines)
    assert env["agi_channel"] == "PJSIP/t1-recepcao-00000001"
    assert env["agi_uniqueid"] == "1700000000.5"
    assert env["agi_callerid"] == "5511999998888"


def test_parse_agi_env_ignores_malformed_lines():
    lines = ["agi_channel: PJSIP/x-1", "linha sem dois pontos", ""]
    env = parse_agi_env(lines)
    assert env == {"agi_channel": "PJSIP/x-1"}


def test_parse_agi_env_empty_input():
    assert parse_agi_env([]) == {}


# ---------- build_record_command ----------

def test_build_record_command_includes_filename_and_format():
    cmd = build_record_command("/var/spool/asterisk/monitor/intake-123", audio_format="wav")
    assert '"/var/spool/asterisk/monitor/intake-123"' in cmd
    assert "wav" in cmd
    assert cmd.startswith("RECORD FILE")


def test_build_record_command_includes_escape_digit_and_timeout():
    cmd = build_record_command("arquivo", escape_digits="#", timeout_ms=5000)
    assert '"#"' in cmd
    assert "5000" in cmd


# ---------- build_set_variable_command ----------

def test_build_set_variable_command():
    cmd = build_set_variable_command("INTENT_DESTINO", "1010")
    assert cmd == 'SET VARIABLE INTENT_DESTINO "1010"'


# ---------- build_stream_file_command ----------

def test_build_stream_file_command_basic():
    cmd = build_stream_file_command("custom/tts-abc123")
    assert cmd == 'STREAM FILE "custom/tts-abc123" ""'


def test_build_stream_file_command_with_escape_digits():
    cmd = build_stream_file_command("custom/tts-abc123", escape_digits="#")
    assert cmd == 'STREAM FILE "custom/tts-abc123" "#"'


# ---------- parse_agi_response ----------

def test_parse_agi_response_basic():
    result = parse_agi_response("200 result=1")
    assert result["code"] == 200
    assert result["result"] == "1"


def test_parse_agi_response_with_parenthetical_extra():
    result = parse_agi_response("200 result=1 (timeout)")
    assert result["code"] == 200
    assert result["result"] == "1"


def test_parse_agi_response_malformed_does_not_crash():
    result = parse_agi_response("isso não é uma resposta AGI válida")
    assert result["code"] is None
    assert result["result"] is None


def test_parse_agi_response_empty_string():
    result = parse_agi_response("")
    assert result["code"] is None
