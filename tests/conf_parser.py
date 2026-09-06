"""
Parser "bom o suficiente" para arquivos .conf do Asterisk.

Não é um parser INI completo: precisa lidar com duas particularidades
reais do pjsip.conf:

1. O mesmo nome de seção aparece várias vezes (ex: [t1-1001] como
   endpoint, depois de novo como auth, depois de novo como aor).
2. Herança de templates: `[t1-1001](endpoint-secure)` herda chaves de
   `[endpoint-secure](endpoint-base!)`, que por sua vez herda de
   `[endpoint-base](!)`. Uma chave como `webrtc=yes` pode não estar
   escrita literalmente no bloco do endpoint final - ela só existe no
   template. Os testes precisam enxergar isso.

Para os testes, cada seção vira um dict com: name, template_ref (nome
do template do qual herda, sem o sufixo "!", ou None) e text (o texto
cru do bloco, sem herança resolvida).
"""
import re
from pathlib import Path

SECTION_RE = re.compile(r"^\[([^\]]+)\](?:\(([^)]*)\))?\s*$")


def parse_blocks(path: Path):
    """
    Retorna uma lista de dicts {name, template_ref, text}, na ordem em
    que aparecem no arquivo.
    """
    blocks = []
    current = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = SECTION_RE.match(raw_line.strip())
        if match:
            if current is not None:
                current["text"] = "\n".join(current["text"])
                blocks.append(current)

            name = match.group(1)
            template_raw = match.group(2)
            template_ref = None
            if template_raw and template_raw != "!":
                # remove o sufixo "!" (marca "esta seção também é template")
                template_ref = template_raw.rstrip("!") or None

            current = {"name": name, "template_ref": template_ref, "text": []}
        else:
            if current is not None:
                current["text"].append(raw_line)

    if current is not None:
        current["text"] = "\n".join(current["text"])
        blocks.append(current)

    return blocks


def get_key(text: str, key: str):
    """Retorna o valor de key=valor dentro do texto cru de um bloco, ou None."""
    match = re.search(rf"^{re.escape(key)}\s*=\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _template_lookup(blocks):
    """Mapa nome -> bloco, usado para resolver heranças de template."""
    return {b["name"]: b for b in blocks}


def get_key_inherited(block, key: str, all_blocks, _depth=0):
    """
    Resolve uma chave subindo a cadeia de templates se necessário.
    Ex: get_key_inherited(bloco_t1_1001, "webrtc", blocos) encontra o
    valor mesmo que "webrtc" só esteja definido em endpoint-webrtc.
    """
    value = get_key(block["text"], key)
    if value is not None:
        return value
    if block["template_ref"] and _depth < 10:
        parent = _template_lookup(all_blocks).get(block["template_ref"])
        if parent:
            return get_key_inherited(parent, key, all_blocks, _depth + 1)
    return None


def is_type_inherited(block, type_name: str, all_blocks):
    return get_key_inherited(block, "type", all_blocks) == type_name


def blocks_by_type(blocks, type_name: str):
    """
    Filtra blocos cujo 'type' resolvido (considerando herança de
    template) seja igual a type_name.
    """
    return [b for b in blocks if is_type_inherited(b, type_name, blocks)]
