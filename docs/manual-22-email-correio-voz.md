# Manual 22 — E-mail de correio de voz (item #16)

## O que é
Quando alguém deixa uma mensagem de voz, ela chega **por e-mail**
também (com o áudio anexado), além de continuar disponível pra ouvir
discando `*97` (manual 01).

## Por que precisou de um script (mail_relay.py)
O `voicemail.conf` do Asterisk já monta o e-mail inteiro sozinho
(cabeçalhos + áudio anexado, graças a `attach=yes` que já existia) e
manda pra um comando externo (`mailcmd`) via stdin — normalmente isso
seria o `sendmail` do sistema. Só que o container do Asterisk não tem
um servidor de e-mail (MTA) de verdade instalado.

`asterisk/scripts/mail_relay.py` faz esse papel: recebe o e-mail já
pronto do Asterisk pelo stdin, e repassa pra um servidor SMTP externo
de verdade (o mesmo tipo de configuração já usada nas notificações de
chamada perdida, manual 11).

## Como configurar
1. Cada caixa de voz precisa de um e-mail associado, no
   `voicemail.conf`:
   ```
   t1-1001 => 1234,T1 Ramal 1001,t1-1001@suaempresa.com
   ```
   (o formato é `ramal => senha,Nome,email` — o e-mail é o 3º campo,
   opcional)
2. Pra ramais criados pelo **painel de administração** (manual 16),
   tem um campo "E-mail (opcional)" no formulário — se preenchido, já
   gera a caixa de voz com e-mail configurado automaticamente
3. No `docker-compose.yml`, serviço `asterisk`, configure as
   credenciais SMTP (**vazio por padrão = desabilitado**):
   ```yaml
   SMTP_HOST: "smtp.suaempresa.com"
   SMTP_PORT: "587"
   SMTP_USERNAME: "seu-usuario"
   SMTP_PASSWORD: "sua-senha"
   ```

## Como testar manualmente
1. Configure um e-mail numa caixa de voz e as credenciais SMTP
2. `docker compose up -d`
3. Ligue pra um ramal e deixe uma mensagem de voz (não atenda de
   propósito até cair na caixa)
4. Confira se o e-mail chegou, com o áudio anexado
5. Sem configurar SMTP: confirme que a caixa de voz continua
   funcionando normalmente (você ainda ouve a mensagem discando
   `*97`) — só não chega e-mail nenhum, sem erro visível

## Teste automatizado
Nova suíte: `asterisk/scripts/tests/` (a 4ª do projeto) —
`test_mail_relay.py`:
- parsing do e-mail recebido via stdin (extrai cabeçalhos, extrai
  destinatário)
- `is_configured()` desligado por padrão (host vazio)
- envio via SMTP usa a configuração certa (host/porta/login/TLS),
  usando mocks — sem rede de verdade

Também:
- `tests/test_voicemail_conf.py::test_voicemail_email_relay_configured`
- `tests/test_docker_compose.py::test_voicemail_mail_relay_script_mounted_and_disabled_by_default`
- `admin-api/tests/test_conf_generator.py` — e-mail incluído/omitido
  corretamente no `voicemail_dynamic_t1.conf` gerado pelo painel

## Limitações conhecidas (honestidade técnica)
- **O envio de verdade via SMTP não tem teste de integração** — mesma
  situação já documentada pro resto das integrações de rede do
  projeto (AMI, notificações, tronco TDM, click-to-call)
- **E-mail dos ramais estáticos (`t1-1001`, `t1-1002`, `t2-1001`) vem
  com endereço de exemplo** (`@example.com`) — troque pelos e-mails
  reais no `voicemail.conf` antes de usar em produção
- **Sem opção de "apagar do Asterisk depois de enviar por e-mail"**
  (`deletevoicemail` do Asterisk) configurada — a mensagem fica
  guardada nos dois lugares (caixa de voz E e-mail)
- **Um servidor SMTP só**, compartilhado entre voicemail e
  notificações de chamada perdida — não dá pra usar remetentes
  diferentes pra cada finalidade neste MVP
