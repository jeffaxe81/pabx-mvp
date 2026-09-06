"""
Gera o CONTEÚDO dos 4 arquivos .conf dinâmicos a partir da lista de
ramais do painel. Lógica pura (recebe a lista, devolve string) -
escrever em disco é responsabilidade do server.py, não daqui, pra
manter isso 100% testável sem I/O.

Esses arquivos são incluídos (#include) nos .conf estáticos do
Asterisk - ver manual 16 pra como a inclusão funciona.
"""

AUTO_GENERATED_HEADER = (
    "; ARQUIVO GERADO AUTOMATICAMENTE PELO PAINEL DE ADMINISTRAÇÃO.\n"
    "; NÃO EDITE NA MÃO - qualquer alteração aqui é sobrescrita na\n"
    "; próxima mudança feita pelo painel.\n\n"
)


def render_pjsip_dynamic(extensions: list) -> str:
    blocks = [AUTO_GENERATED_HEADER]
    for ext in extensions:
        name = ext["name"]
        blocks.append(f"""[{name}](endpoint-secure)
context=t1-internal
subscribe_context=t1-hints
auth={name}
aors={name}
callerid={ext['display_name']} <{ext['number']}>
mailboxes={name}@t1

[{name}]
type=auth
auth_type=userpass
username={name}
password={ext['password']}

[{name}]
type=aor
max_contacts=1
remove_existing=yes
""")
    return "\n".join(blocks)


def render_extensions_dynamic_dial(extensions: list) -> str:
    lines = [AUTO_GENERATED_HEADER]
    for ext in extensions:
        lines.append(
            f"exten => {ext['number']},1,MixMonitor(/var/spool/asterisk/monitor/"
            f"${{STRFTIME(${{EPOCH}},,%Y%m%d-%H%M%S)}}-${{CALLERID(num)}}-{ext['number']}.wav,b)\n"
            f" same => n,Dial(PJSIP/{ext['name']},20)\n"
            f" same => n,Hangup()\n"
        )
    return "\n".join(lines)


def render_extensions_dynamic_hints(extensions: list) -> str:
    lines = [AUTO_GENERATED_HEADER]
    for ext in extensions:
        lines.append(f"exten => {ext['number']},hint,PJSIP/{ext['name']}")
    return "\n".join(lines) + ("\n" if extensions else "")


def render_voicemail_dynamic(extensions: list) -> str:
    lines = [AUTO_GENERATED_HEADER]
    for ext in extensions:
        email = ext.get("email", "")
        lines.append(f"{ext['name']} => 1234,{ext['display_name']},{email}")
    return "\n".join(lines) + ("\n" if extensions else "")


def render_all(extensions: list) -> dict:
    """Retorna {nome_do_arquivo: conteudo} pros 4 arquivos dinâmicos."""
    return {
        "pjsip_dynamic.conf": render_pjsip_dynamic(extensions),
        "extensions_dynamic_dial.conf": render_extensions_dynamic_dial(extensions),
        "extensions_dynamic_hints.conf": render_extensions_dynamic_hints(extensions),
        "voicemail_dynamic_t1.conf": render_voicemail_dynamic(extensions),
    }
