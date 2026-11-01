"""REL-18: regressões inéditas do preflight de configuração SIP."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from security_config_preflight import inspect


TLS = """[transport-tls]
type=transport
protocol=tls
method=tlsv1_2
cert_file=/etc/asterisk/certs/asterisk.crt
priv_key_file=/etc/asterisk/certs/asterisk.key
"""


def _tree(tmp_path, pjsip=TLS, manager="[api]\\nsecret = senha-forte-irrepetivel\\n",
          compose='services:\\n  queue-api:\\n    environment:\\n      AMI_SECRET: "senha-forte-irrepetivel"\\n'):
    ast = tmp_path / "asterisk"
    (ast / "certs").mkdir(parents=True)
    (ast / "pjsip.conf").write_text(pjsip, encoding="utf-8")
    (ast / "manager.conf").write_text(manager.replace("\\n", "\n"), encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text(compose.replace("\\n", "\n"), encoding="utf-8")
    (ast / "certs/asterisk.crt").write_text("certificado-ficticio", encoding="utf-8")
    (ast / "certs/asterisk.key").write_text("chave-ficticia", encoding="utf-8")
    (ast / "certs/asterisk.key").chmod(0o600)
    (ast / "manager.conf").chmod(0o600)
    return tmp_path


def test_config_minima_segura_nao_gera_bloqueios(tmp_path):
    assert inspect(_tree(tmp_path)) == []


def test_tls_em_comentario_nao_comprova_transporte(tmp_path):
    tree = _tree(tmp_path, pjsip="; method=tlsv1_2\n[transport-udp]\ntype=transport\nprotocol=udp\n")
    assert any("transporte TLS SIP" in m for m in inspect(tree))


def test_tls_em_secao_errada_nao_comprova_transport_tls(tmp_path):
    tree = _tree(tmp_path, pjsip="[outra-secao]\nmethod=tlsv1_2\nprotocol=tls\ntype=transport\n")
    assert any("transporte TLS SIP" in m for m in inspect(tree))


def test_ami_secret_yaml_padrao_e_identificado_sem_vazar_valor(tmp_path):
    tree = _tree(tmp_path, compose="services:\n  queue-api:\n    environment:\n      AMI_SECRET: 'troque_esta_senha_ami'\n")
    findings = inspect(tree)
    assert any("docker-compose.yml" in m and "credencial padrão" in m for m in findings)
    assert all("troque_esta_senha_ami" not in m for m in findings)


def test_credencial_padrao_asterisk_e_identificada(tmp_path):
    tree = _tree(tmp_path, manager="[api]\nsecret = troque_esta_senha_ami\n")
    assert any("asterisk/manager.conf" in m and "credencial padrão" in m for m in inspect(tree))


def test_permissoes_arquivo_sensivel_sao_verificadas(tmp_path):
    tree = _tree(tmp_path)
    (tree / "asterisk/certs/asterisk.key").chmod(0o644)
    assert any("asterisk.key" in m and "permissões" in m for m in inspect(tree))


def test_ausencia_chave_tls_bloqueia_preflight(tmp_path):
    tree = _tree(tmp_path)
    (tree / "asterisk/certs/asterisk.key").unlink()
    assert any("asterisk.key" in m and "ausente" in m for m in inspect(tree))


def test_caminho_inesperado_da_chave_bloqueia_preflight(tmp_path):
    tree = _tree(tmp_path, pjsip=TLS.replace(
        "/etc/asterisk/certs/asterisk.key", "/tmp/segredo.key"
    ))
    assert any("priv_key_file" in m for m in inspect(tree))


def test_comentario_com_credencial_padrao_nao_e_valido(tmp_path):
    tree = _tree(tmp_path, manager="; secret = troque_esta_senha_ami\nsecret = senha-valida\n")
    assert not any("credencial padrão" in m for m in inspect(tree))


def test_arquivo_essencial_ausente_e_reportado(tmp_path):
    tree = _tree(tmp_path)
    (tree / "docker-compose.yml").unlink()
    assert any("docker-compose.yml: arquivo ausente" in m for m in inspect(tree))
