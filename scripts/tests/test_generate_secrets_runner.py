"""
Teste de integração do generate_secrets.py - roda contra arquivos
TEMPORÁRIOS (nunca contra o repositório real, que precisa continuar
com os placeholders visíveis pra qualquer pessoa que clonar o
projeto saber que precisa rodar o gerador antes do deploy).
"""
from pathlib import Path

import generate_secrets


def test_runner_replaces_placeholders_across_multiple_files(tmp_path, monkeypatch, capsys):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text('AMI_SECRET: "troque_esta_senha_ami"\n', encoding="utf-8")

    manager = tmp_path / "manager.conf"
    manager.write_text("secret = troque_esta_senha_ami\n", encoding="utf-8")

    monkeypatch.setattr(generate_secrets, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(generate_secrets, "TARGET_FILES", [compose, manager])

    generate_secrets.main()

    compose_content = compose.read_text(encoding="utf-8")
    manager_content = manager.read_text(encoding="utf-8")

    assert "troque_esta_senha_ami" not in compose_content
    assert "troque_esta_senha_ami" not in manager_content

    # O segredo aplicado nos dois arquivos precisa ser IDÊNTICO -
    # senão o queue-api nunca conseguiria autenticar no AMI.
    compose_secret = compose_content.split('"')[1]
    manager_secret = manager_content.split("=")[1].strip()
    assert compose_secret == manager_secret


def test_runner_does_nothing_when_no_placeholders_left(tmp_path, monkeypatch, capsys):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text('AMI_SECRET: "ja-foi-trocado-antes"\n', encoding="utf-8")

    monkeypatch.setattr(generate_secrets, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(generate_secrets, "TARGET_FILES", [compose])

    generate_secrets.main()

    captured = capsys.readouterr()
    assert "Nenhum placeholder" in captured.out
    assert compose.read_text(encoding="utf-8") == 'AMI_SECRET: "ja-foi-trocado-antes"\n'


def test_runner_skips_missing_files_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_secrets, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(generate_secrets, "TARGET_FILES", [tmp_path / "nao-existe.conf"])

    generate_secrets.main()  # não deveria lançar exceção nenhuma
