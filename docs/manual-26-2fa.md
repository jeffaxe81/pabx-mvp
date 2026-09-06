# Manual 26 — Autenticação em dois fatores / 2FA (item #20)

## O que é
Cada usuário do painel de administração (manual 25) pode proteger a
própria conta com TOTP — o mesmo padrão de código de 6 dígitos do
Google Authenticator, Authy, 1Password, etc. É **autoatendimento**:
qualquer usuário (admin ou supervisor) configura o 2FA da própria
conta, ninguém configura pra outra pessoa.

## Como funciona
Implementado com **TOTP puro (RFC 6238)**, usando só biblioteca
padrão do Python (`hmac`, `hashlib`, `base64`) — sem nenhuma
dependência externa, consistente com o resto do projeto. A
implementação foi validada contra o **vetor de teste oficial do
RFC 6238** (não é só "consistente consigo mesma" — bate com o
algoritmo padrão de verdade).

Fluxo de configuração:
1. Usuário logado clica "Configurar 2FA" → backend gera um segredo
   novo e mostra na tela (`otpauth://` também é gerado, mas hoje só o
   segredo em texto aparece na interface — ver limitação abaixo)
2. Usuário adiciona esse segredo no app autenticador (manualmente,
   colando o texto — a maioria dos apps aceita "entrada manual" além
   de escanear QR code)
3. Usuário digita o código de 6 dígitos gerado pelo app pra confirmar
4. **Só depois dessa confirmação** o 2FA fica realmente ativo — um
   segredo configurado mas nunca confirmado não bloqueia login nenhum
   (evita a pessoa se trancar fora da própria conta por engano)

Fluxo de login com 2FA ativo:
1. Usuário digita usuário/senha normalmente
2. Se a senha está certa E o usuário tem 2FA ativo, o backend
   **não** devolve uma sessão de verdade — devolve um token
   temporário (`pending_token`) e pede o código
3. Usuário digita o código de 6 dígitos do app
4. Só aí o backend emite o token de sessão real

## Como usar
1. Logue no painel normalmente
2. Vá em "Autenticação em dois fatores (2FA)"
3. Clique "Configurar 2FA", copie o segredo mostrado
4. No seu app autenticador, adicione uma conta nova → "inserir chave
   manualmente" → cole o segredo
5. Digite o código de 6 dígitos que apareceu no app, clique "Confirmar
   e ativar"
6. Faça logout e login de novo — agora vai pedir o código

Pra desativar: seção "Desativar 2FA", digite sua senha atual e
confirme.

## Como testar manualmente
1. Configure o 2FA numa conta de teste (passos acima)
2. Faça logout, tente logar de novo com usuário/senha — confirme que
   aparece a tela "Verificação em duas etapas" em vez de entrar direto
3. Digite um código errado — confirme que é rejeitado
4. Digite o código certo do app — confirme que completa o login
5. Espere ~1 minuto e gere um código novo no app antes de usar — ainda
   deve funcionar (tolerância de ±30s pra diferença de relógio)
6. Desative o 2FA com a senha certa — confirme que o próximo login
   volta a ser em uma etapa só

## Teste automatizado
- `admin-api/tests/test_totp.py` — **inclui o vetor de teste oficial
  do RFC 6238** (prova que o algoritmo está correto, não só
  "funciona no nosso próprio teste"), geração de segredo, tolerância
  de relógio, rejeição de código incorreto/fora da janela
- `admin-api/tests/test_users.py` — campos de TOTP persistem
  corretamente numa edição de usuário que não mexe neles
  (`totp_secret`/`totp_enabled` não somem ao editar só o papel)
- `admin-api/tests/test_server_security.py`:
  - configurar 2FA só exige estar autenticado (não exige ser admin -
    é autoatendimento)
  - confirmação só ativa o 2FA **depois** de verificar o código
  - desativação exige senha confirmada **antes** de desligar
  - login com 2FA ativo nunca devolve sessão de verdade antes da
    verificação completa
  - o endpoint de verificação de código exige o token pendente correto
    (não aceita reaproveitar um token de sessão comum)
- `tests/test_admin_html.py` — fluxo de login reconhece
  `requires_totp`, tela de configuração mostra o segredo antes de
  ativar, desativação envia a senha

## Limitações conhecidas (honestidade técnica)
- **Sem QR code de imagem** — só o segredo em texto (e a URI
  `otpauth://` é gerada no backend, mas a interface hoje só mostra o
  texto do segredo, não um link clicável nem uma imagem de QR). Gerar
  QR code exigiria uma biblioteca extra ou desenhar o QR na mão, fora
  do escopo deste MVP — funciona perfeitamente por "entrada manual" no
  app autenticador, só é menos conveniente que apontar a câmera
- **Sem códigos de backup/recuperação** — se a pessoa perder o acesso
  ao app autenticador, não tem como recuperar sozinha; precisaria de
  outro admin editando o usuário no `users.json` diretamente (ou
  criar um endpoint de reset admin-only, não implementado ainda)
- **Um segredo só por usuário** — não dá pra ter múltiplos
  dispositivos configurados simultaneamente (celular + backup, por
  exemplo)
- **Sem rate limiting nas tentativas de código** — alguém poderia
  tentar força bruta os 6 dígitos (1 milhão de combinações, mas sem
  limite de tentativas isso não é tão improvável quanto parece);
  mitigação futura natural seria um rate limit por usuário/IP
