import base64

from totp import generate_secret, generate_totp, verify_totp, build_provisioning_uri

# Vetor de teste oficial do RFC 6238 (apêndice B): segredo ASCII
# "12345678901234567890" (20 bytes), SHA1, no timestamp 59 segundos
# (Unix epoch), o código TOTP esperado é "94287082".
# Aqui usamos só os 6 primeiros dígitos porque nossa implementação é
# fixa em 6 dígitos (o padrão real de apps como Google Authenticator).
RFC_SECRET_B32 = base64.b32encode(b"12345678901234567890").decode("ascii")


def test_rfc6238_test_vector_at_timestamp_59():
    """
    Prova que a implementação bate com o algoritmo padrão de verdade,
    não só "consistente consigo mesma".
    """
    code = generate_totp(RFC_SECRET_B32, timestamp=59, digits=8)
    assert code == "94287082"


def test_generate_secret_produces_valid_base32():
    secret = generate_secret()
    assert len(secret) > 0
    # base32 válido não deve lançar exceção ao decodificar (com padding)
    padding = "=" * ((8 - len(secret) % 8) % 8)
    base64.b32decode(secret + padding)


def test_generate_secret_produces_different_values():
    secrets = {generate_secret() for _ in range(10)}
    assert len(secrets) == 10


def test_verify_totp_accepts_correct_code_at_same_instant():
    secret = generate_secret()
    code = generate_totp(secret, timestamp=1_700_000_000)
    assert verify_totp(secret, code, timestamp=1_700_000_000) is True


def test_verify_totp_rejects_wrong_code():
    secret = generate_secret()
    assert verify_totp(secret, "000000", timestamp=1_700_000_000) is False


def test_verify_totp_tolerates_clock_drift_within_window():
    secret = generate_secret()
    code = generate_totp(secret, timestamp=1_700_000_000)
    # 30s depois (1 período) ainda deve ser aceito com window=1
    assert verify_totp(secret, code, timestamp=1_700_000_030, window=1) is True


def test_verify_totp_rejects_code_far_outside_window():
    secret = generate_secret()
    code = generate_totp(secret, timestamp=1_700_000_000)
    # 5 minutos depois - bem fora da janela de tolerância
    assert verify_totp(secret, code, timestamp=1_700_000_300, window=1) is False


def test_verify_totp_rejects_empty_code_or_secret():
    assert verify_totp("", "123456") is False
    assert verify_totp("ABCDEF", "") is False
    assert verify_totp(None, None) is False


def test_verify_totp_handles_malformed_secret_without_crashing():
    assert verify_totp("não é base32 válido!!!", "123456") is False


def test_build_provisioning_uri_format():
    uri = build_provisioning_uri("JBSWY3DPEHPK3PXP", "joao", issuer="PABX Admin")
    assert uri.startswith("otpauth://totp/")
    assert "secret=JBSWY3DPEHPK3PXP" in uri
    assert "issuer=PABX" in uri  # espaço vira '+' ou '%20' no urlencode
