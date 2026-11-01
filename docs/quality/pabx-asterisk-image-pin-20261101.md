# AXE PABX — proteção da imagem Asterisk para a próxima homologação

**Data:** 2026-11-01. **Escopo:** PABX puro, após a RC `v0.1.0-rc.1` já congelada. Este ajuste é de preparação de código para homologação futura; **não altera a tag da RC nem executa implantação**.

## Problema e correção

O serviço `asterisk` no `docker-compose.yml` utilizava `andrius/asterisk:latest`, referência mutável. Isso permite iniciar um binário Asterisk diferente da versão exercitada no GitHub Actions, mesmo usando o mesmo código de dialplan.

A referência passa a ser:

```
andrius/asterisk:22.11.0_debian-trixie@sha256:d6333b8b331563c5887b98b12da9371ef48317e657d17d81770fe085f335041d
```

É o **mesmo digest declarado em `lab/asterisk_lab.py`**, usado nos ensaios isolados de Asterisk. O novo `scripts/asterisk_image_preflight.py` é **somente leitura, sem Docker, rede ou comandos de telefonia**. Ele reprova `latest`, tag sem digest, referência divergente do laboratório, entrada duplicada ou arquivo simbólico. A suíte `tests/test_docker_compose.py` verifica também o YAML efetivo.

## Execução controlada

```bash
python3 scripts/asterisk_image_preflight.py --root .
python3 scripts/security_config_preflight.py --root .
```

O primeiro comando comprova somente que o *compose* aponta ao mesmo digest do laboratório. O segundo inspeciona TLS, credenciais e ACL, podendo **reprovar o checkout de demonstração** por conter segredos/certificados não operacionais. Nenhum deles comprova aptidão de produção.

Antes de qualquer atualização de imagem em ambiente real, a equipe deve identificar o binário atualmente instalado, verificar compatibilidade das configurações e módulos, versionar a preparação específica do ambiente, obter autorização de mudança, realizar backup e testar plano de rollback. Fazer o pull da imagem pode exigir acesso ao registry; **este PR não executa pull, recreate ou restart**.

## Próximas provas ainda obrigatórias

Manter os 13 cenários do modelo de homologação e as 15 provas operacionais como **pendentes**, inclusive interoperabilidade com gateway/operadora, chamadas reais, SRTP, gravações, voicemail/PIN, recuperação e failover. Preservar `operational_go_authorized=false` e o acompanhamento na [issue #173](https://github.com/jeffaxe81/pabx-mvp/issues/173).

**Resultado limitado:** redução do risco de drift de imagem para próximos testes controlados. **GO operacional: BLOQUEADO.**
