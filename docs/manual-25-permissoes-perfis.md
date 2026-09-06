# Manual 25 — Permissões e perfis (item #19)

## O que é
O painel de administração deixou de ser "um admin só, tudo ou nada" e
ganhou dois papéis:

| Papel | Ramais | Lista de bloqueio | Modo feriado | Usuários |
|---|---|---|---|---|
| **admin** | criar/editar/excluir | criar/excluir | ligar/desligar | criar/editar/excluir |
| **supervisor** | só visualizar | só visualizar | ligar/desligar | sem acesso |

O modo feriado é liberado pros dois papéis de propósito — é uma ação
**operacional** (ligar/desligar um interruptor), bem diferente de
criar um ramal novo ou apagar um número de bloqueio, que são
mudanças estruturais reservadas ao admin.

## Como funciona
- **Um único usuário admin inicial** continua vindo das variáveis
  `ADMIN_USERNAME`/`ADMIN_PASSWORD_HASH` do `docker-compose.yml` — mas
  agora ele só serve pra **popular o primeiro usuário** na primeira
  vez que o painel sobe (`ensure_bootstrap_admin()`). Depois disso,
  todo gerenciamento de usuários é pela própria interface, seção
  "Usuários do painel"
- Sessões agora guardam o **papel**, não só quem logou — toda rota que
  muda alguma coisa (`POST`/`PUT`/`DELETE`) checa o papel certo antes
  de tocar no banco de dados ou na AMI
- **Não dá pra remover o último admin** — o sistema bloqueia essa
  ação pra evitar ficar sem ninguém conseguindo administrar

## Como configurar
1. No `docker-compose.yml`, gere o hash da senha do primeiro admin
   (mesmo processo do manual 16) e configure `ADMIN_USERNAME`/
   `ADMIN_PASSWORD_HASH`
2. `docker compose up -d` — na primeira subida, esse usuário é criado
   automaticamente com papel `admin`
3. Logue no painel, vá em "Usuários do painel", crie os supervisores
   que precisar

## Como testar manualmente
1. Suba o painel com um admin configurado, confirme que consegue
   criar ramal, bloquear número, ligar modo feriado, e criar um novo
   usuário
2. Crie um usuário com papel **supervisor**
3. Faça login como esse supervisor — confirme que:
   - Consegue **ver** a lista de ramais e a lista de bloqueio
   - **Não** vê os formulários de criar/editar ramal nem de bloquear
     número (a seção some da tela)
   - **Consegue** ligar/desligar o modo feriado
   - **Não** vê a seção "Usuários do painel" de jeito nenhum
4. Tente chamar a API diretamente como supervisor (ex:
   `curl -X POST .../api/extensions ... -H "Authorization: Bearer <token-do-supervisor>"`)
   — confirme que recebe `403`, não só a interface escondendo o botão
   (a proteção real é no backend, a UI é só conveniência)
5. Tente excluir o único admin que existe — confirme que é bloqueado

## Teste automatizado
- `admin-api/tests/test_users.py` — CRUD de usuários, validação de
  papel, hash de senha reaproveitado do `auth.py`, proteção contra
  remover o último admin
- `admin-api/tests/test_auth.py` — sessão guarda e recupera o papel
- `admin-api/tests/test_server_security.py` — **reescrito por
  completo**: cada rota de mutação é checada quanto ao papel exigido
  ANTES de mexer no store/AMI (não só "está autenticado", mas "tem o
  papel certo"); rotas de leitura também exigem o papel adequado
- `tests/test_admin_html.py` — seção de usuários escondida por
  padrão, `applyRolePermissions()` esconde os cards certos, papel é
  guardado a partir da resposta do login

## Limitações conhecidas (honestidade técnica)
- **Só dois papéis** (admin/supervisor) — o documento de
  funcionalidades original mencionava também "atendente" e "usuário
  comum", mas esses não têm acesso ao painel de administração neste
  projeto (eles usam o console da telefonista, `webphone/index.html`,
  que não tem sistema de login/permissão nenhum ainda)
- **A restrição de UI é só conveniência** — quem realmente protege é
  o backend (`_require_role`); esconder um botão na tela não impede
  alguém de chamar a API diretamente sem o papel certo (e o teste do
  passo 4 acima prova isso)
- **Sem 2FA ainda** — isso é o próximo item do backlog (#20)
- **Sessões em memória** — continuam desaparecendo se o `admin-api`
  reiniciar (mesma limitação já aceita no manual 16)
- **Sem log de auditoria** — não fica registrado quem criou/editou/
  excluiu o quê, só o resultado final
