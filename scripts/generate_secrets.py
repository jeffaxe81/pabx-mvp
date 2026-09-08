#!/usr/bin/env python3
"""
Roda a geração de segredos de verdade, aplicando nos arquivos reais
do projeto (backlog #50). Ver secrets_generator.py pra lógica pura,
e docs/manual-50 pra explicação completa e avisos.

Uso:
    python3 scripts/generate_secrets.py

PASSO OBRIGATÓRIO antes de qualquer deploy real - sem isso, o sistema
sobe com as mesmas senhas que estão públicas no repositório do
GitHub.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from secrets_generator import generate_strong_secret, find_placeholders, replace_all_placeholders  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent

# Arquivos que podem conter placeholders "troque_esta_senha_*" -
# alguns segredos aparecem em mais de um arquivo (ex: AMI_SECRET
# precisa bater entre docker-compose.yml e manager.conf) - por isso
# o mapa de segredo é construído uma vez só e aplicado em todos.
TARGET_FILES = [
    PROJECT_ROOT / "docker-compose.yml",
    PROJECT_ROOT / "asterisk" / "manager.conf",
    PROJECT_ROOT / "asterisk" / "pjsip.conf",
]


def main():
    print("Lendo arquivos e coletando placeholders...")
    all_placeholders = set()
    contents = {}
    for path in TARGET_FILES:
        if not path.exists():
            print(f"  aviso: {path} não encontrado, pulando")
            continue
        text = path.read_text(encoding="utf-8")
        contents[path] = text
        all_placeholders |= find_placeholders(text)

    if not all_placeholders:
        print("Nenhum placeholder 'troque_esta_senha_*' encontrado - já foi rodado antes, ou os arquivos já têm segredos próprios.")
        return

    print(f"Encontrados {len(all_placeholders)} placeholders distintos:")
    for p in sorted(all_placeholders):
        print(f"  - {p}")

    secret_map = {placeholder: generate_strong_secret() for placeholder in all_placeholders}

    print("\nAplicando novos segredos...")
    for path, text in contents.items():
        new_text = replace_all_placeholders(text, secret_map)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(f"  atualizado: {path.relative_to(PROJECT_ROOT)}")

    print("""
=====================================================
PRONTO. Leia com atenção antes de continuar:

1. Os arquivos alterados (docker-compose.yml, manager.conf,
   pjsip.conf) agora contêm segredos REAIS, não mais placeholders.

2. NAO comite essa alteracao de volta pra um repositorio publico -
   isso publicaria os novos segredos exatamente como os antigos
   estavam publicados. Se este e um repositorio publico (ex: GitHub),
   pare aqui e decida: repositorio privado, arquivo .gitignore pros
   arquivos alterados, ou algum mecanismo de secrets do seu ambiente
   de producao (nao coberto por este script).

3. ADMIN_PASSWORD_HASH (senha do painel de administracao) usa um
   mecanismo DIFERENTE (hash, nao texto plano) - nao foi tocado por
   este script. Gere com:
   python3 -c "from auth import hash_password; print(hash_password('sua-senha-aqui'))"
   (rodando de dentro de admin-api/) e cole o resultado no lugar de
   ADMIN_PASSWORD_HASH no docker-compose.yml.

4. Guarde os segredos gerados em algum lugar seguro (gerenciador de
   senhas) - nao ha como recupera-los depois, so gerar novos.
=====================================================
""")


if __name__ == "__main__":
    main()
