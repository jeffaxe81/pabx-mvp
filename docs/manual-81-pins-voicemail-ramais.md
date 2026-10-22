# Manual 81 — PIN exclusivo para voicemail dos ramais dinâmicos

## Motivação

O painel AXE PABX já permite criar novos ramais SIP, mas o gerador
`admin-api/conf_generator.py` ainda atribui PIN previsível
`1234` ao correio de voz de cada ramal. Essa senha é pública
no código-fonte e não deve ser utilizada para caixas novas.

## Alteração

- **Novo ramal**: o backend usa `secrets.randbelow()` para gerar
  PIN numérico aleatório de oito dígitos, sem zero inicial. Para um
  mesmo tenant, evita repetir PINs já registrados no armazenamento.
- **Persistência**: o campo `voicemail_pin` é gravado no cadastro
  de ramais para gerar o mesmo valor nas próximas recargas do Asterisk.
  Não é devolvido na listagem de ramais ou na edição.
- **Provisionamento**: a resposta administrativa de criação apresenta
  username, senha SIP e PIN do voicemail. A interface mostra as duas
  credenciais apenas nessa operação e permite ocultá-las.
- **Proteção de API**: não aceita definir ou modificar o PIN via
  payload de POST/PUT comum; novos PINs são sempre gerados no servidor.
- **Compatibilidade**: ramais antigos sem `voicemail_pin` preservam
  `1234` até rotação específica, para evitar alterações silenciosas
  que interrompam acesso às mensagens.

## Testes

```bash
(cd admin-api && python3 -m pytest -q tests/test_store.py tests/test_conf_generator.py)
python3 -m pytest -q tests/test_admin_html.py
node --test tests/ui_browser.test.cjs
```

Os testes asseguram persistência estável após edição, unicidade entre
novos ramais do mesmo tenant, proteção contra alteração arbitrária,
exclusão da listagem HTTP, uso no `voicemail_dynamic_tN.conf` e
apresentação de credenciais com APIs simuladas.

## Procedimento operacional

1. Criar um ramal de laboratório no painel.
2. Guardar a senha SIP e o PIN de caixa postal no cofre autorizado.
3. Verificar que o campo de PIN do `voicemail_dynamic_tN.conf`
   corresponde à credencial gerada, sem publicá-la.
4. Entrar no voicemail com o PIN correto e errado e registrar evidências.
5. Fazer o teste com dois ramais de tenants diferentes para verificar
   que não existe leitura cruzada de mensagens.

## Pendências

**Atenção:** esta entrega NÃO faz rotação automática dos PINs legados.
Os ramais preexistentes e contas estáticas do `voicemail.conf` ainda
podem usar PIN fraco; planejar inventário e rotação autorizada antes
do GO operacional. Não há limitação de tentativas configurada por
este recurso; requisitos de segurança do correio de voz precisam
ser confirmados em laboratório.

Também não realiza chamadas reais, não altera serviços em execução e
não substitui a matriz de homologação do Manual 73.
