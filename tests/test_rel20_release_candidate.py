"""REL-20: não fechar RC sem 20/20 e fronteira explícita de produção."""
import importlib.util
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "rel20_rc_validation", ROOT / "scripts/rel20_release_candidate.py"
)
rel20 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rel20)


@pytest.fixture()
def release_tree(tmp_path):
    (tmp_path / "docs").mkdir()
    for file in (
        "RELEASE_VERSION", "docs/release-fechamento-20-entregas.md",
        "docs/rel20-release-candidate.md"
    ):
        shutil.copyfile(ROOT / file, tmp_path / file)
    return tmp_path


def test_rel20_20_itens_e_go_produtivo_bloqueado(release_tree):
    version, errors = rel20.inspect(release_tree)
    assert version == "v0.1.0-rc.1"
    assert errors == []
    assert rel20.main(["--root", str(release_tree)]) == 0


def test_rel20_19_itens_nao_sao_aceitos(release_tree):
    file = release_tree / "docs/release-fechamento-20-entregas.md"
    content = file.read_text()
    assert "- [x] **REL-13" in content
    file.write_text(content.replace("- [x] **REL-13", "- [ ] **REL-13", 1))
    assert "ainda existem entregas pendentes" in rel20.inspect(release_tree)[1]


def test_rel20_ids_duplicados_bloqueiam(release_tree):
    file = release_tree / "docs/release-fechamento-20-entregas.md"
    content = file.read_text()
    assert "- [x] **REL-20" in content
    file.write_text(content.replace("- [x] **REL-20", "- [x] **REL-19", 1))
    assert any("IDs" in x for x in rel20.inspect(release_tree)[1])


def test_rel20_nao_aceita_versao_que_nao_seja_rc(release_tree):
    (release_tree / "RELEASE_VERSION").write_text("v1.0.0\n")
    assert any("versão" in x for x in rel20.inspect(release_tree)[1])


def test_rel20_sem_declaracao_de_no_go_nao_passa(release_tree):
    file = release_tree / "docs/rel20-release-candidate.md"
    content = file.read_text()
    file.write_text(content.replace("GO operacional: BLOQUEADO", "GO operacional: AUTORIZADO"))
    assert any("termo de aceite" in x for x in rel20.inspect(release_tree)[1])


def test_rel20_versao_ou_documentacao_ausente_bloqueiam(release_tree):
    (release_tree / "RELEASE_VERSION").unlink()
    assert "artefato obrigatório ausente" in rel20.inspect(release_tree)[1]


def test_workflow_rc_somente_na_main_e_sem_publishing_ga():
    workflow = (ROOT / ".github/workflows/rel20-rc-tag.yml").read_text()
    assert 'github.ref == ' in workflow
    assert "branches:\n      - main" in workflow
    assert "contents: write" in workflow
    assert "git tag -a" in workflow
    assert "git push origin" in workflow
    assert 'gh release create "$tag" --draft --prerelease' in workflow
    assert "--verify-tag" in workflow
    assert 'gh release create "$tag" --latest' not in workflow
    assert 'GITHUB_SHA' in workflow
