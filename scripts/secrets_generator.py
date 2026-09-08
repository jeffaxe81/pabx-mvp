"""
Geração de segredos fortes pra substituir os placeholders
"troque_esta_senha_*" espalhados no projeto (AMI, SIP) - backlog #50.

IMPORTANTE: rodar isso é um passo OBRIGATÓRIO antes de qualquer deploy
real (ver manual 00, roteiro de implantação). Sem isso, o sistema
sobe com as mesmas senhas que estão públicas no repositório do
GitHub - qualquer pessoa que tenha visto o código sabe essas senhas.

Depois de rodar, os arquivos alterados (pjsip.conf, manager.conf,
docker-compose.yml) passam a conter segredos reais - NÃO comite essa
alteração específica de volta pra um repositório público. Ver aviso
completo no fim da execução do script.

Lógica pura de geração/substituição aqui - a leitura/escrita de
arquivo de verdade fica isolada em run.py, mesmo padrão do resto do
projeto.
"""
import re
import secrets


def generate_strong_secret(length: int = 32) -> str:
    """
    Gera um segredo aleatório forte, só com caracteres seguros pra
    usar dentro de um arquivo .conf sem precisar escapar nada (sem
    aspas, sem espaço, sem `=`/`;`/`#` que teriam significado especial
    no formato .conf do Asterisk).
    """
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def find_placeholders(content: str) -> set:
    """
    Encontra todos os placeholders no padrão 'troque_esta_senha*'
    dentro de um texto - usado tanto pra achar o que precisa trocar
    quanto pra confirmar que não sobrou nenhum depois.
    """
    return set(re.findall(r"troque_esta_senha[a-z0-9_]*", content))


def replace_placeholder(content: str, placeholder: str, new_secret: str) -> str:
    """Troca TODAS as ocorrências de um placeholder específico pelo novo segredo, no texto todo."""
    return content.replace(placeholder, new_secret)


def replace_all_placeholders(content: str, secret_map: dict) -> str:
    """
    Troca vários placeholders de uma vez, na ORDEM CERTA: do mais
    longo pro mais curto. Isso importa porque 'troque_esta_senha_ami'
    é substring de 'troque_esta_senha_ami_admin' - trocar o mais curto
    primeiro corromperia o mais longo (viraria "SEGREDO1_admin", uma
    mistura do novo segredo com o resto do nome antigo, em vez de um
    segredo totalmente independente).
    """
    for placeholder in sorted(secret_map, key=len, reverse=True):
        content = replace_placeholder(content, placeholder, secret_map[placeholder])
    return content
