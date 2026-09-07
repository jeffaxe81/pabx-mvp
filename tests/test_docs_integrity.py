"""
Auditoria de coerência da documentação (achada numa revisão manual -
ver git log): garante que os manuais se referenciam corretamente uns
aos outros, e que o índice bate com os arquivos que existem de
verdade. Sem isso, é fácil um manual novo referenciar outro pelo nome
errado (como aconteceu com manual-00) e ninguém perceber até alguém
clicar no link quebrado.
"""
import re
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"
README = DOCS_DIR / "README.md"


def all_manual_files():
    return {f.name for f in DOCS_DIR.glob("manual-*.md")}


def test_every_manual_linked_in_readme_exists():
    content = README.read_text(encoding="utf-8")
    linked_files = set(re.findall(r"\(manual-\d+-[a-z0-9-]+\.md\)", content))
    linked_files = {f.strip("()") for f in linked_files}

    missing = linked_files - all_manual_files()
    assert not missing, f"README.md linka manuais que não existem: {missing}"


def test_every_existing_manual_is_listed_in_readme():
    content = README.read_text(encoding="utf-8")
    orphans = [f for f in all_manual_files() if f not in content]
    assert not orphans, f"Manuais existem mas não estão no índice: {orphans}"


def test_manual_numbering_has_no_gaps_or_duplicates():
    numbers = sorted(int(re.match(r"manual-(\d+)-", f).group(1)) for f in all_manual_files())
    assert len(numbers) == len(set(numbers)), "Há números de manual duplicados"
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), (
        f"Numeração dos manuais tem buraco(s): {numbers}"
    )


def test_cross_references_between_manuals_point_to_real_files():
    """
    Todo manual que cita 'manual-NN' (referência cruzada em texto,
    não em link markdown) precisa apontar pra um manual que existe -
    esse foi o erro real encontrado na auditoria que motivou este
    teste: um manual novo citando 'docs/manual-02-webphone.md' quando
    o manual 2 na verdade se chama outra coisa.
    """
    existing = all_manual_files()
    existing_numbers = {int(re.match(r"manual-(\d+)-", f).group(1)) for f in existing}

    for manual_file in existing:
        content = (DOCS_DIR / manual_file).read_text(encoding="utf-8")
        referenced_paths = re.findall(r"manual-\d+-[a-z0-9-]+\.md", content)
        for ref in referenced_paths:
            assert ref in existing, f"{manual_file} referencia '{ref}', que não existe"
