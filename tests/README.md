# Testes automatizados

Testes **estáticos** (não sobem o Asterisk de verdade) que validam a
consistência dos arquivos de configuração e do webphone a cada
mudança. Pensados para rodar em segundos, localmente ou em CI, antes
de qualquer `docker compose up`.

## Rodando

```bash
cd tests
pip install -r requirements.txt --break-system-packages   # ou dentro de um venv
python3 -m pytest -v
```

## O que cada arquivo cobre

| Arquivo | O que valida |
|---|---|
| `test_pjsip_conf.py` | Transportes (UDP/TLS/WSS) existem; todo ramal tem auth+aor; ramais internos usam criptografia; ramal web usa `webrtc=yes`; sem senha fraca/placeholder; `subscribe_context` aponta pra contexto real |
| `test_extensions_conf.py` | Contextos esperados existem; ramal 1000 roteia pra telefonista web; chamada sem DID cai na recepção; todo `hint` aponta pra endpoint real; sem ramal duplicado no mesmo tenant |
| `test_docker_compose.py` | YAML válido; serviços `asterisk`/`provisioning`/`webphone` existem; volumes montados apontam pra arquivos que existem de verdade; portas expostas |
| `test_provisioning.py` | `devices.json` real é válido; gerador não deixa `{{placeholder}}` sobrando; fabricante desconhecido não quebra o script |
| `test_webphone_html.py` | IDs usados pelo JavaScript continuam no HTML; biblioteca JsSIP carregada; array `COLLEAGUES` (presença); transferência assistida usa hold antes de consultar e limpa as duas pernas ao completar; pickup da fila chama o endpoint certo |
| `test_ami_config.py` | `manager.conf` (AMI habilitado, usuário com senha real, restrito por IP) e `queues.conf` (fila com membro, timeout e gravação automática válidos) |

Suíte separada em `queue-api/tests/` (parsing do protocolo AMI, lógica
de estado da fila, e listagem/segurança de gravações - tudo sem
depender de rede) — rodar com `cd queue-api && python3 -m pytest tests/ -v`.

## O que esses testes **não** cobrem (ainda)

- Registro SIP de verdade (precisaria subir o Asterisk em container e
  usar um cliente SIP real, ex: `pjsua` ou `sipexec`, num teste de
  integração)
- Qualidade de áudio / RTP
- Comportamento do navegador com WebRTC (isso é teste manual, ver
  `docs/manual-05-telefonista-web.md`)

Ideia natural de evolução: um segundo nível `tests/integration/` que
sobe o `docker-compose.yml` de verdade e faz uma chamada de teste via
`sipp` ou `pjsua`, uma vez que o projeto tiver CI configurado.

## Regra do projeto

Toda nova funcionalidade implementada neste projeto deve vir com:
1. Teste(s) automatizado(s) aqui (mesmo que só estático/sanidade)
2. Atualização do `README.md` principal
3. Um manual em `docs/` (ver `docs/README.md`)

Isso está registrado como regra permanente no prompt master
(`prompt-base-pabx.md`).
