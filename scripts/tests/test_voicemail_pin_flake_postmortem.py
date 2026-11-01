"""Investigação SIP/TLS: amostras aleatórias inválidas não quebram bootstrap."""

from pathlib import Path

import pytest

from lab import asterisk_lab as lab
from lab.voicemail_pin_checks import (
    generate_verified_lab_pin_map, validate_prepared_voicemail,
)

ROOT = Path(__file__).resolve().parents[2]


def test_gerador_rejeita_pins_fracos_repetidos_e_sequenciais_sem_expor_valores():
    attempts = iter([
        "12345678",  # previsível
        "11223344",  # lista de PINs rejeitados
        "23456789",  # sequência que o tenant dinâmico rejeita
        "35679124",  # permitido
        "35679124",  # repetido
        "46791325",  # permitido
    ])
    pins = generate_verified_lab_pin_map(
        ["t1", "t3"], lambda: next(attempts), attempts_per_pin=6)
    assert list(pins) == ["t1", "t3"]
    assert set(pins.values()) == {"35679124", "46791325"}


def test_gerador_falha_fechado_com_limite_sem_publicar_pin():
    with pytest.raises(ValueError, match="PIN seguro único") as err:
        generate_verified_lab_pin_map(
            ["t1"], lambda: "12345678", attempts_per_pin=4)
    assert "12345678" not in str(err.value)
    with pytest.raises(ValueError, match="PIN seguro único"):
        generate_verified_lab_pin_map(
            ["t1", "t2"], lambda: "35679124", attempts_per_pin=2)


@pytest.mark.parametrize("names,limit", [
    ([], 2), (["t1", "t1"], 2),
    (["t1"], 0), (["t1"], 257),
    (["t1"], True), (["t1", 42], 2),
])
def test_entrada_invalida_nao_cria_pins(names, limit):
    with pytest.raises(ValueError):
        generate_verified_lab_pin_map(names, lambda: "35679124", attempts_per_pin=limit)


def test_prepare_regenera_pin_invalido_deterministicamente_sem_docker(tmp_path, monkeypatch):
    original = lab.load_file
    attempts = []

    def inject(name, path):
        module = original(name, path)
        if name == "lab_secrets_generator":
            secure = module.generate_voicemail_pin

            def synthetic():
                attempts.append(True)
                if len(attempts) == 1:
                    return "12345678"  # antiga primeira amostra quebrava o preparo
                if len(attempts) == 2:
                    return "11223344"
                return secure()
            module.generate_voicemail_pin = synthetic
        return module

    monkeypatch.setattr(lab, "load_file", inject)
    stage = {}
    prepared = lab.prepare(ROOT, tmp_path / "private", stage_report=stage)
    static = (prepared["conf"] / "voicemail.conf").read_text()
    dynamic = (prepared["conf"] / "voicemail_tenants/t3.conf").read_text()
    assert validate_prepared_voicemail(static, dynamic)["ok"] is True
    assert " => 12345678," not in static
    assert " => 11223344," not in static
    assert len(attempts) >= 12  # dez mailboxes + duas amostras rejeitadas
    assert stage["phase"] == "staging:tls_certificate_generation"
    assert not any(v in str(stage) for v in ("12345678", "11223344"))


def test_prepare_esgota_tentativas_sem_expor_credencial_nem_subir_container(tmp_path, monkeypatch):
    original = lab.load_file

    def always_weak(name, path):
        module = original(name, path)
        if name == "lab_secrets_generator":
            module.generate_voicemail_pin = lambda: "12345678"
        return module

    monkeypatch.setattr(lab, "load_file", always_weak)
    stage = {}
    with pytest.raises(ValueError, match="PIN seguro único") as err:
        lab.prepare(ROOT, tmp_path / "private", stage_report=stage)
    assert stage["phase"] == "staging:voicemail_pin_generation"
    assert "12345678" not in str(err.value)
