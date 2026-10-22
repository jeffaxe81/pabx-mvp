# Manual 79 — Validação de ramais e provisionamento SIP controlado

## Objetivo

Proteger a criação e edição de ramais administrados pelo painel, antes
de gravar o banco JSON e regenerar arquivos do Asterisk (PJSIP,
dialplan e voicemail). Campos JSON inesperados ou com caracteres de
controle podiam gerar erros internos ou injetar novas diretivas.

## Regras de entrada

- A requisição precisa ser um objeto JSON; nome, tenant, nome de
  exibição, e-mail e senha fornecida devem ter tipos corretos.
- O identificador do ramal permanece limitado a letras minúsculas,
  números e hífen; quebras de linha são recusadas mesmo antes da
  normalização.
- Número do ramal somente inteiro ou string decimal (1100–1199);
  números fracionários, booleanos e conteúdo arbitrário são recusados.
- Nome de exibição (até 60 caracteres) não pode conter controles nem
  delimitadores da configuração (`;`, `=`, `,`, `<`, `>`, colchetes).
  Caracteres acentuados imprimíveis continuam aceitos.
- E-mail opcional deve respeitar formato de endereço simples e não pode
  alterar a estrutura de `voicemail.conf`.
- Senha SIP fornecida precisa ter 12–128 caracteres de alfabeto seguro
  para arquivo `.conf`. Se estiver ausente, é gerada senha aleatória
  de 32 caracteres usando `secrets.token_urlsafe(24)`.
- Na edição de um ramal existente, uma senha legada curta pode
  permanecer **sem alteração**, mas não pode ser escolhida como
  nova senha. Planeje rotação das senhas antigas.

## Provisionamento

A criação retorna as credenciais SIP **apenas na resposta administrativa
de POST**. O backend continua ocultando o campo `password` em
listagens e edições. O painel apresenta a senha em texto após a criação,
com botão **Ocultar credenciais**, e limpa o campo ao trocar para
edição, iniciar outra criação ou sair. O input de senha é do tipo
`password` e o JSON usa `Cache-Control: no-store`.

Copie o segredo no momento da criação e armazene em cofre adequado.
**É necessário HTTPS** na interface administrativa para impedir
exposição de credenciais em trânsito. Não registre segredos reais em
issues, screenshots, PRs ou relatórios.

## Testes

```bash
(cd admin-api && python3 -m pytest -q tests/test_store.py tests/test_server_security.py)
python3 -m pytest -q tests/test_admin_html.py
node --test tests/ui_browser.test.cjs
```

Os testes simulam valores JSON de tipo errado, tentativas de injeção,
senhas curtas, nomes acentuados, resposta de criação e ocultação de
credencial num Chromium instrumentado com API mockada.

## Limitações e homologação

- Não migra senhas antigas automaticamente; permanece necessária
  rotação programada de segredos fracos.
- O PIN `1234` de correio de voz dos **ramais dinâmicos** continua
  como limitação separada e não é resolvido por esta entrega. A troca
  desse PIN exige evolução específica.
- O gerador e armazenamento JSON não fornecem transação distribuída
  com AstDB/AMI; erros de reload devem ser tratados operacionalmente.
- Registro SIP/TLS, mídia RTP/SRTP e isolamento em chamadas reais
  exigem homologação de laboratório (Manual 73).
