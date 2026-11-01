"""Regressão: Asterisk de homologação não pode usar :latest nem drift de digest."""
from pathlib import Path
import shutil

from asterisk_image_preflight import (
    IMAGE_RE, compose_asterisk_image, inspect, lab_image, main,
)

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = (
    "andrius/asterisk:22.11.0_debian-trixie@sha256:"
    "d6333b8b331563c5887b98b12da9371ef48317e657d17d81770fe085f335041d"
)


def test_repo_compose_fixado_na_exata_imagem_do_asterisk_ci():
    assert IMAGE_RE.fullmatch(EXPECTED)
    result = inspect(ROOT)
    assert result["ok"], result
    assert lab_image((ROOT / "lab/asterisk_lab.py").read_text()) == EXPECTED
    assert compose_asterisk_image((ROOT / "docker-compose.yml").read_text()) == EXPECTED


def test_tag_mutavel_sem_digest_reprovada(tmp_path, capsys):
    (tmp_path / "lab").mkdir()
    shutil.copyfile(ROOT / "lab/asterisk_lab.py", tmp_path / "lab/asterisk_lab.py")
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  asterisk:\n    image: andrius/asterisk:latest\n"
    )
    assert not inspect(tmp_path)["ok"]
    assert main(["--root", str(tmp_path)]) == 2
    assert "BLOQUEIO" in capsys.readouterr().out


def test_digest_diferente_do_laboratorio_reprovado(tmp_path):
    (tmp_path / "lab").mkdir()
    shutil.copyfile(ROOT / "lab/asterisk_lab.py", tmp_path / "lab/asterisk_lab.py")
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  asterisk:\n    image: " + EXPECTED[:-1] + "a\n"
    )
    assert IMAGE_RE.fullmatch(EXPECTED[:-1] + "a")
    assert inspect(tmp_path)["reason"] == "imagem do compose diverge da imagem de CI"


def test_service_duplicado_ou_imagem_duplicada_bloqueiam():
    for source in (
        "services:\n  asterisk:\n    image: " + EXPECTED + "\n"
        "  asterisk:\n    image: " + EXPECTED + "\n",
        "services:\n  asterisk:\n    image: " + EXPECTED + "\n"
        "    image: " + EXPECTED + "\n",
        "services:\n  queue-api:\n    image: python:3.12\n",
    ):
        try:
            compose_asterisk_image(source)
            assert False, "configuração ambígua passou"
        except ValueError:
            pass


def test_source_lab_nao_executa_codigo_para_descobrir_image():
    source = "IMAGE = __import__('os').system('echo unexpected')\n"
    try:
        lab_image(source)
        assert False, "constante não literal foi executada"
    except ValueError:
        pass
    assert lab_image("IMAGE = (" + repr(EXPECTED) + ")\n") == EXPECTED


def test_preflight_symlink_nao_autoriza(tmp_path):
    (tmp_path / "lab").mkdir()
    shutil.copyfile(ROOT / "lab/asterisk_lab.py", tmp_path / "lab/asterisk_lab.py")
    (tmp_path / "docker-compose.yml").symlink_to(ROOT / "docker-compose.yml")
    assert not inspect(tmp_path)["ok"]
