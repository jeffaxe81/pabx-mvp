# Manual 96 — Auditoria somente leitura do Asterisk em execução

## Objetivo

Executar verificações **contra o processo Asterisk em execução** em um
laboratório Docker ou em uma instalação local. Diferentemente de testes
com respostas AMI simuladas, o script consulta comandos reais com
`asterisk -rx`. Não faz alterações, não reinicia serviços e não
origina chamadas.

Ferramenta: `scripts/asterisk_lab_audit.py`.

## Pré-requisitos

Instalação de laboratório separada da produção, arquivos de configuração
atualizados segundo o Manual 87 e Asterisk operacional. O usuário que
executa o script precisa de acesso ao Docker ou ao CLI local do
Asterisk. Esse privilégio é sensível: use conta autorizada.

## Execução

Com o container Compose padrão `pabx-mvp`:

```bash
python3 scripts/asterisk_lab_audit.py \
  --runtime docker --container pabx-mvp
```

Para verificar também os DIDs e os contextos de empresas `t3+`:

```bash
python3 scripts/asterisk_lab_audit.py \
  --runtime docker --container pabx-mvp \
  --tenant-registry /caminho/privado/tenants.json
```

Sem Docker (com `asterisk -rx` funcionando no host):

```bash
python3 scripts/asterisk_lab_audit.py --runtime local
```

O caminho de `tenants.json` é um arquivo privado do ambiente
administrativo; não o publique nem forneça seus dados em tickets.
Sem `--tenant-registry`, apenas os contextos básicos `t1/t2`
são conferidos.

## Verificações

O utilitário executa comandos CLI **somente leitura**, sem shell:

- `core show version` e `pjsip show transports`: processo disponível
  e presença dos transportes TLS/WSS;
- `pjsip show endpoint` de `t1-1001`, `t2-1001` e de cada
  `tN-recepcao` informado: endpoint presente e vinculado ao
  contexto `tN-internal`;
- `dialplan show tN-internal`: contexto carregado no Asterisk;
- `dialplan show from-tdm-gateway`: indicação de consulta ao AstDB
  e rejeição de DID desconhecido;
- `database show tenant-did`: compara mapeamentos de DIDs somente
  para os tenants informados pelo cadastro.

O relatório JSON informa aprovações, falhas e percentual dos checks.
Não imprime a saída bruta do CLI, DIDs, valores AstDB, endereços ou
senhas, mesmo quando uma verificação falha.

## Códigos de retorno

- `0`: verificações de configuração carregada aprovadas; pronto
  para continuar as provas de chamadas, não é autorização de GO.
- `1`: uma ou mais verificações não passaram.
- `2`: parâmetros de invocação ou catálogo inválido.

## Testes automatizados

```bash
(cd scripts && python3 -m pytest -q tests/test_asterisk_lab_audit.py)
```

Os testes do CI utilizam saídas **simuladas**. Para preencher
evidências de homologação, execute o programa em laboratório real
e registre o commit implantado, a versão do Asterisk e os resultados
de forma controlada.

## Limitações importantes

**Esta auditoria não executa REGISTER, INVITE, testes de voz,
RTP bidirecional, SRTP, isolamento entre chamadas, gravações ou
backup/restauração.** Endpoints listados e contextos carregados
não comprovam que um telefone esteja registrado ou que chamadas
funcionem. Os campos correspondentes permanecem `false` mesmo
quando 100% dos checks forem aprovados.

A presença de palavras esperadas na saída do CLI não equivale a
uma validação semântica completa do dialplan; diferenças entre
versões do Asterisk podem exigir revisão dos reconhecedores de
formato antes de uma homologação. Não rode no servidor de produção
sem autorização e sem avaliar a política de acesso ao Docker.

A aprovação operacional continua sujeita aos 13 cenários e à
revisão de evidências do [Manual 73](manual-73-gates-homologacao.md).
