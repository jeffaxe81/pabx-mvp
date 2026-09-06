#!/usr/bin/env python3
"""
Gera os arquivos de auto-provisionamento (um por MAC address) a partir
dos templates em provisioning/templates/ e do cadastro devices.json.

Uso:
    python3 generate.py

Saida:
    provisioning/files/<MAC>.cfg   (um arquivo por telefone cadastrado)

O telefone, ao ligar, faz um GET em:
    http://<ip-do-servidor>:8080/<MAC>.cfg
e aplica a configuracao sozinho (auto-provisionamento real).
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DEVICES_FILE = os.path.join(BASE, "devices.json")
TEMPLATES_DIR = os.path.join(BASE, "templates")
OUTPUT_DIR = os.path.join(BASE, "files")

TEMPLATE_EXT = {
    "yealink": "yealink.cfg.tpl",
}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(DEVICES_FILE, encoding="utf-8") as f:
        data = json.load(f)

    for device in data["devices"]:
        vendor = device["vendor"]
        template_name = TEMPLATE_EXT.get(vendor)
        if not template_name:
            print(f"[AVISO] fabricante '{vendor}' sem template, pulando {device['mac']}")
            continue

        template_path = os.path.join(TEMPLATES_DIR, template_name)
        with open(template_path, encoding="utf-8") as tf:
            content = tf.read()

        content = (
            content.replace("{{RAMAL}}", device["ramal"])
            .replace("{{NOME}}", device["nome"])
            .replace("{{SENHA}}", device["senha"])
            .replace("{{SERVIDOR}}", device["servidor"])
        )

        out_path = os.path.join(OUTPUT_DIR, f"{device['mac']}.cfg")
        with open(out_path, "w", encoding="utf-8") as of:
            of.write(content)

        print(f"[OK] gerado: {out_path}")


if __name__ == "__main__":
    main()
