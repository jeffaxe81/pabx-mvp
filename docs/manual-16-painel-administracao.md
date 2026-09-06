# Manual 16 — Painel de administração web (backlog #10)

## O que é
Interface web (`admin/index.html`) pra cadastrar, editar e remover
ramais do tenant 1 sem precisar editar `.conf` na mão. Ao salvar, o
Asterisk recarrega a configuração sozinho (sem derrubar chamadas em
andamento).

**Escopo do MVP**: só CRUD de ramais do tenant 1. Criar tenant novo,
gerenciar troncos/filas ou usuários administradores continua manual —
ver limitações abaixo.

## Como funciona (arquitetura)
Como o Asterisk lê configuração de arquivos (não tem banco de dados
por trás neste projeto), a peça central é o **`#include`**: os arquivos
estáticos (`pjsip.conf`, `extensions.conf`, `voicemail.conf`) incluem
arquivos "dinâmicos" que o painel gera e regrava a cada mudança:

```
pjsip.conf          #include pjsip_dynamic.conf
extensions.conf      [t1-internal]  #include extensions_dynamic_dial.conf
                      [t1-hints]    #include extensions_dynamic_hints.conf
voicemail.conf        [t1]          #include voicemail_dynamic_t1.conf
```

Fluxo de uma criação de ramal:
1. Painel valida os dados (nome único, número na faixa 1100-1199,
   sem duplicar)
2. `admin-api` salva em `extensions_store.json` (a "fonte de verdade")
3. Regera os 4 arquivos dinâmicos a partir do store inteiro (não só o
   ramal novo - por isso é seguro editar/remover também)
4. Manda `pjsip reload` + `dialplan reload` + `voicemail reload` via
   AMI - o Asterisk aplica sem reiniciar

## Segurança
- **Login desligado por padrão** (`ADMIN_PASSWORD_HASH` vazio = toda
  tentativa de login falha) - mesmo padrão já usado em notificações e
  click-to-call
- Senha do admin fica como **hash PBKDF2** (nunca em texto plano),
  gerado assim:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'admin-api')
  from auth import hash_password
  print(hash_password('sua-senha-aqui'))
  "
  ```
  Cole o resultado em `ADMIN_PASSWORD_HASH` no `docker-compose.yml`
- Sessão por token (8h de validade), guardada em memória - some se o
  container reiniciar (precisa logar de novo, não é um problema de
  segurança, só de conveniência)
- Toda rota que muda dado (criar/editar/excluir) checa autenticação
  **antes** de tocar no armazenamento (testado explicitamente em
  `test_server_security.py`)
- A senha SIP de cada ramal nunca é devolvida pro navegador depois de
  criada (`public_view` remove o campo antes de responder)

## Como configurar
No `docker-compose.yml`, serviço `admin-api`:
```yaml
ADMIN_USERNAME: "admin"
ADMIN_PASSWORD_HASH: "<hash gerado acima>"
```

## Como usar
1. Acesse `http://<ip-do-servidor>:8091`
2. Entre com usuário/senha configurados
3. "Novo ramal": identificador (ex: `vendas-1`), número (1100-1199),
   nome de exibição, senha (deixe em branco pra gerar automática)
4. O ramal aparece na tabela e já pode ser usado - registre um
   softphone com o identificador e a senha
5. "Editar"/"Excluir" fazem o mesmo ciclo (regenera + recarrega)

## Como testar manualmente
1. Configure a senha de admin (seção acima) e `docker compose up -d`
2. Crie um ramal pelo painel
3. Confira: `asterisk/pjsip_dynamic.conf` deve ter o novo bloco
4. Registre um softphone com esse ramal - deve conectar sem reiniciar
   o container do Asterisk
5. Edite o nome de exibição do ramal - confirme que atualiza
6. Exclua o ramal - confirme que o softphone perde o registro

## Teste automatizado
- `admin-api/tests/test_auth.py` — hash/verificação de senha (salt
  único, comparação em tempo constante), sessões (criação, expiração,
  revogação)
- `admin-api/tests/test_store.py` — validação de entrada (nome, faixa
  de número, duplicatas), CRUD completo com persistência em disco
- `admin-api/tests/test_conf_generator.py` — os 4 arquivos gerados
  têm o conteúdo certo, sempre usam o template com criptografia
  (nunca `endpoint-plain`), sem vazar senha nos arquivos que não
  precisam dela
- `admin-api/tests/test_server_security.py` — autenticação checada
  antes de qualquer mutação, senha nunca devolvida ao navegador
- `tests/test_pjsip_conf.py`, `test_extensions_conf.py`,
  `test_voicemail_conf.py` — os `#include` existem nos arquivos
  estáticos certos
- `tests/test_docker_compose.py` — serviço presente, login desligado
  por padrão, credenciais AMI batendo com `manager.conf`
- `tests/test_admin_html.py` — IDs da interface, token sempre enviado
  nas chamadas de API, confirmação antes de excluir

## Limitações conhecidas (honestidade técnica)
- **Só ramais do tenant 1** — criar tenant novo, gerenciar troncos,
  filas ou os próprios usuários administradores continua 100% manual
- **Hash de senha é PBKDF2-SHA256 caseiro** (stdlib, sem dependência
  externa), não é bcrypt/argon2 — funcional e razoável pra este porte,
  mas não é o que uma auditoria de segurança recomendaria pra produção
  séria
- **Sem 2FA** (autenticação em dois fatores é o item #20 do backlog
  fase 2/3, ainda não implementado)
- **Sem controle de permissões/perfis** — é um usuário admin só, tudo
  ou nada (item #19 do backlog)
- **Sessões em memória** — reiniciar o container do `admin-api` derruba
  todo mundo logado
- **`admin-api` tem acesso de escrita à pasta `asterisk/` inteira**
  (monta o diretório todo, não só os 3 arquivos dinâmicos) — mais
  permissão do que estritamente necessário, aceito pela simplicidade
  do MVP
- **O reload de verdade via AMI não tem teste de integração** — mesma
  situação já documentada pro resto do projeto (AMI, tronco TDM,
  notificações): só valida contra um Asterisk real
- Editar `asterisk/*_dynamic.conf` na mão funciona até a próxima
  mudança pelo painel, que sobrescreve tudo - não é papel dessas
  pessoas, se decidirem editar, se lembrarem disso
