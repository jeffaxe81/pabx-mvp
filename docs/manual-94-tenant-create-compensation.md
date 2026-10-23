# Manual 94 — Criação de tenants com compensação de arquivos e AstDB

## Problema corrigido

Antes desta entrega, o wizard criava arquivos de configuração e
registrava o DID no AstDB, mas, se o AMI falhasse, ainda respondia
**HTTP 201** e registrava o tenant como concluído. A gravação de
arquivos também podia ficar parcialmente executada.

## Novo fluxo

1. Verificar permissão de administrador, DID estático, duplicidade e
   conteúdo do cadastro, sob trava de transação do wizard.
2. Gerar as duas senhas SIP e PINs de voicemail, sem publicá-los.
3. Montar os cinco arquivos de infraestrutura e três arquivos
   dinâmicos do tenant, verificando que nenhum destino já existe.
4. Escrever arquivos temporários na mesma pasta e sincronizar os
   dados antes da publicação exclusiva; nenhum arquivo existente
   é substituído.
5. Abrir sessão AMI, registrar DID e confirmar todas as respostas de
   reload de PJSIP, dialplan, voicemail, filas e estacionamento.
6. Persistir o cadastro JSON apenas após essas confirmações.
7. Responder HTTP 201 com credenciais **somente se tudo foi concluído**.

## Tratamento de falhas

Se a criação ou o reload falhar, os novos arquivos são removidos e a
API retorna **HTTP 502**, sem incluir as senhas geradas. Se o registro
do DID tiver sido tentado, o sistema abre uma **nova conexão AMI** para
tentar removê-lo e recarregar as configurações anteriores.

A resposta inclui `rollback_incomplete`:

- `false`: as compensações necessárias foram concluídas no escopo
  que o software conseguiu observar;
- `true`: a compensação do DID ou do reload não pôde ser confirmada.
  **Exige reconciliação manual antes de nova tentativa.**

É obrigatório conferir `database show tenant-did` em laboratório
se ocorreu perda de conexão após o registro.

## Testes automatizados

```bash
(cd admin-api && python3 -m pytest -q \
  tests/test_tenant_provisioning.py tests/test_server_security.py)
```

A suíte simula falha de login, falha após DBPut potencialmente aplicado,
falha de reload, indisponibilidade na compensação, falha no cadastro
JSON, arquivos preexistentes e diretórios ausentes.

## Limitações

O sistema não dispõe de transação distribuída ACID entre sistema de
arquivos, AstDB, Asterisk e JSON. Pode haver falhas elétricas e
interrupções abruptas que escapam ao contexto de compensação; a
confirmação de `Response: Follows` ainda não equivale à verificação
semântica completa do serviço. Os arquivos são publicados
individualmente, embora o reload só ocorra ao final.

A trava da criação protege threads do mesmo `admin-api`, não múltiplos
processos ou hosts. **A remoção de tenants e o CRUD de ramais ainda
precisam de reconciliação própria**; este manual não os declara
transacionais. Nenhum servidor real foi alterado e nenhuma chamada
SIP/RTP foi realizada.
