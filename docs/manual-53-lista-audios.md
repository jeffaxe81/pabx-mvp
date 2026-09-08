# Manual 53 — Lista de áudios existentes no painel (item #53)

## O que fecha
O manual 48 (TTS) documentou explicitamente como limitação: **"sem
lista de áudios gerados na interface — o painel gera, mas não mostra
um histórico do que já foi criado"**. Este item fecha essa lacuna.

## O que é
Uma tabela na seção de TTS do painel, listando todo `.wav` existente
em `asterisk/sounds/custom/` — nome do arquivo, tamanho, e data de
geração/modificação — do mais recente pro mais antigo. Recarrega
automaticamente depois de gerar um áudio novo, e também ao entrar no
painel.

## Não é exclusivo de áudio gerado por TTS
A pasta `custom/` também tem os *placeholders* originais do projeto
(menus da URA, aviso de gravação, etc.) — a lista mostra **todos**
os `.wav` da pasta, não só os gerados via TTS. Isso é intencional:
serve como uma visão geral de "o que existe hoje", útil também pra
conferir se um placeholder ainda não foi substituído.

## Quem pode ver
Leitura de baixo risco — **admin e supervisor**, diferente da própria
geração de áudio (que continua admin-only, já que é uma ação de
conteúdo público que todo cliente ouve).

## Como usar
Painel → seção "Gerar áudio por texto (TTS)" → tabela "Áudios
existentes", logo abaixo do formulário de geração.

## Como testar manualmente
1. `docker compose up -d`
2. Entre no painel — confirme que a tabela já mostra os placeholders
   originais (`aviso-gravacao.wav`, `menu-principal-pt.wav`, etc.)
3. Gere um áudio novo pelo formulário de TTS
4. Confirme que a tabela atualiza sozinha, mostrando o arquivo novo
   no topo (mais recente primeiro)

## Teste automatizado
- `admin-api/tests/test_sounds.py` (5 testes) — lista com metadados
  corretos, ignora arquivos não-`.wav`, diretório inexistente/vazio
  vira lista vazia (não erro), ordenação do mais recente pro mais
  antigo
- `admin-api/tests/test_server_security.py::test_sounds_listing_requires_authentication`
  — admin e supervisor têm acesso, mas exige login
- `tests/test_admin_html.py` (3 testes novos) — carregada ao entrar
  no painel, recarrega depois de gerar áudio novo, mostra nome/
  tamanho/data
- **823 testes no total**, em 8 suítes

## Limitações conhecidas (honestidade técnica)
- **Sem reprodução de áudio na interface** — só lista metadados, não
  tem um player pra ouvir o arquivo antes de considerar pronto (o
  admin precisaria acessar o arquivo por outro caminho, ex: SSH no
  servidor, pra conferir o resultado)
- **Sem exclusão pela interface** — a lista é só leitura; apagar um
  áudio gerado por engano ainda exige acesso direto ao sistema de
  arquivos
- **Não distingue placeholder original de áudio gerado por TTS** —
  ambos aparecem juntos, sem marcação visual de origem
- **Nunca testado contra um Asterisk real** — mesma situação já
  documentada pro resto do projeto (aqui, especificamente: nunca
  confirmado que o arquivo listado realmente reproduz corretamente
  quando o Asterisk toca via `Playback()`)
