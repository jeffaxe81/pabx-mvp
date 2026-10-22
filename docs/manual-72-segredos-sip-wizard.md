# Manual 72 — Senhas SIP seguras no wizard de tenant

## Alteração

Ao criar um tenant pelo painel, o AXE PABX agora gera **duas senhas SIP
aleatórias independentes** para as telefonistas `tN-recepcao` e
`tN-recepcao-2`, usando o gerador criptograficamente seguro do Python
(`secrets.token_urlsafe(24)`). A senha não é derivada do ID do tenant
nem reutilizada entre tentativas.

As credenciais são gravadas em `pjsip_tenants/tN.conf` e retornadas
**somente na resposta HTTP de criação** para o administrador autenticado.
A resposta JSON usa `Cache-Control: no-store`; endpoints de listagem
de tenants não retornam senhas.

## Fluxo do administrador

1. Abrir **Administração → Empresas → Preparar ambiente**.
2. Informar identificador, DID e nome; revisar os dados.
3. Confirmar a criação e copiar as duas credenciais mostradas na tela.
4. Provisionar cada telefonista com **sua própria senha SIP**.
5. Armazenar os segredos num cofre de credenciais de acesso restrito.
6. Selecionar **Ocultar credenciais** ou encerrar a sessão quando terminar.

A interface não usa `localStorage` para guardar as senhas geradas:
as credenciais estão disponíveis apenas na resposta daquela criação e
são apagadas da área visível ao ocultar, iniciar outro wizard ou sair.

**Atenção:** se a senha não for copiada no momento da criação, não
existe um endpoint de recuperação nessa etapa. Um administrador com
acesso autorizado ao servidor pode tratar a recuperação/rotação da
senha no PJSIP com procedimento controlado de manutenção. Nunca envie
credenciais por e-mail aberto ou registre em PRs, issues ou screenshots.

## Medidas complementares

- A tabela de tenants e a revisão do wizard agora usam elementos DOM
  e `textContent`, sem interpolar identificadores, nomes ou dados da
  API diretamente em `innerHTML`.
- Erros de reload exibidos no resultado também são apresentados como
  texto, sem interpretação de HTML.
- A criação exige perfil **admin**, conforme autorização já existente.
- **Os exemplos estáticos t1/t2 não são alterados por este recurso.**
  Eles exigem substituição das credenciais de exemplo antes de produção.
- Recomenda-se usar HTTPS ao acessar o painel: o navegador recebe as
  senhas uma vez, e TLS é necessário para protegê-las em trânsito.

## Verificação

```bash
(cd admin-api && python3 -m pytest -q tests/test_tenants.py tests/test_server_security.py)
python3 -m pytest -q tests/test_admin_html.py
```

No laboratório, crie um tenant e verifique que as duas senhas são
fortes, diferentes e correspondem ao `pjsip_tenants/tN.conf`. Teste
registro SIP real com TLS/SRTP e confirme que a tela não exibe a senha
depois de ocultar ou sair.

**Limitações:** testes automatizados são estáticos/mockados; a
conclusão dessa PR não comprova registro SIP, qualidade RTP, failover
ou implantação operacional.