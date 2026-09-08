# Manual 50 — Geração de segredos fortes (item #50)

## Por que isso existe
Todo o projeto, desde o início, usa senhas **placeholder** e óbvias
(`troque_esta_senha_ami`, `troque_esta_senha_1001`, etc.) — de
propósito, pra deixar claro nos arquivos de exemplo que aquilo
precisa ser trocado. O problema real: como este repositório é
**público no GitHub**, qualquer pessoa que veja o código sabe essas
senhas exatas. Subir o sistema sem trocar isso é o mesmo que não ter
senha nenhuma.

## O que o script faz
`scripts/generate_secrets.py` varre `docker-compose.yml`,
`asterisk/manager.conf` e `asterisk/pjsip.conf`, encontra todos os
placeholders `troque_esta_senha_*`, gera um segredo aleatório forte
(32 caracteres, sem símbolos que teriam significado especial dentro
de um `.conf`) pra cada um, e aplica a troca nos três arquivos de
uma vez — mantendo os segredos de AMI **sincronizados** entre
`docker-compose.yml` e `manager.conf` (são o mesmo segredo em dois
lugares; se ficassem diferentes, `queue-api`/`admin-api` nunca
autenticariam no Asterisk).

## Um bug real encontrado e corrigido durante a implementação
`troque_esta_senha_ami` é **substring** de
`troque_esta_senha_ami_admin`. Uma implementação ingênua que trocasse
os placeholders em qualquer ordem corromperia o segundo: ele viraria
uma mistura do novo segredo com o sufixo `_admin` do nome antigo, em
vez de um segredo totalmente independente. A correção: processar os
placeholders do **mais longo pro mais curto**
(`replace_all_placeholders`, ordenado por `len()` decrescente) — o
teste `test_replace_all_handles_substring_collision_correctly` fixa
esse comportamento.

## Como usar
```bash
python3 scripts/generate_secrets.py
```
Ao final, o script imprime um resumo com os avisos importantes (ver
abaixo).

## ⚠️ Depois de rodar — NÃO comite de volta pro GitHub
Os três arquivos alterados passam a conter **segredos reais**. Se
você commitar e der push pra este mesmo repositório público, estará
publicando os novos segredos exatamente como os antigos estavam
publicados — sem ganho nenhum de segurança. Antes de rodar em
produção de verdade, escolha um destes caminhos:
- Fazer o deploy a partir de um **repositório privado** (fork
  privado, ou clone sem remoto público)
- Manter os arquivos alterados **fora do controle de versão** local
  (`git update-index --skip-worktree` nos três arquivos, ou um
  `.gitignore` específico pro seu fluxo de deploy)
- Usar o mecanismo de secrets do seu ambiente de produção real
  (Docker Secrets, Vault, variáveis de ambiente injetadas pelo
  orquestrador) — fora do escopo deste script, que é só um ponto de
  partida pra desenvolvimento/piloto

## O que o script NÃO cobre
- **`ADMIN_PASSWORD_HASH`** (senha do painel de administração) usa
  hash PBKDF2, não texto plano — precisa ser gerado separadamente:
  ```bash
  cd admin-api
  python3 -c "from auth import hash_password; print(hash_password('sua-senha-aqui'))"
  ```
  e colar o resultado no `docker-compose.yml`
- **Certificados TLS** (self-signed, exemplo) — precisam ser
  regenerados/substituídos por certificados reais separadamente (ver
  manual 02)
- **PINs de monitoramento de chamada** (manual 42) e **senhas de
  telefonistas dinâmicas do wizard** (manual 39) — já são gerados sob
  demanda no momento da criação, não são placeholders estáticos no
  código

## Como testar
1. `python3 scripts/generate_secrets.py` (rode contra uma cópia do
   projeto primeiro se quiser só validar, sem alterar o repositório
   de verdade)
2. Confirme que `docker-compose.yml`/`manager.conf` têm o mesmo
   segredo de AMI
3. Confirme que nenhum `troque_esta_senha_*` sobrou em nenhum dos
   três arquivos
4. Rode de novo — confirme que a segunda execução não encontra
   placeholder nenhum (idempotente: não regenera segredos já trocados
   por acidente)

## Teste automatizado
- `scripts/tests/test_secrets_generator.py` (13 testes) — geração de
  segredo forte (comprimento, unicidade, sem caracteres perigosos pra
  `.conf`), busca de placeholders, substituição simples, **e a
  correção do bug de substring** (`replace_all_placeholders`)
- `scripts/tests/test_generate_secrets_runner.py` (3 testes de
  integração, com arquivos temporários — nunca contra o repositório
  real): segredos sincronizados entre múltiplos arquivos, idempotência
  quando não há mais placeholder, não quebra se um arquivo alvo não
  existir
- **785 testes no total**, em **8 suítes** (nova suíte `scripts/tests`)

## Limitações conhecidas (honestidade técnica)
- **Não gera novo `ADMIN_PASSWORD_HASH`** — mecanismo diferente
  (hash), documentado acima como passo manual separado
- **Não lida com certificados TLS**
- **Não impede alguém de commitar os arquivos alterados por engano**
  — o aviso é textual (impresso no terminal), não um bloqueio técnico
  automático (ex: git hook)
- **Roda uma vez, aplica pra todos os placeholders de uma vez** — não
  dá pra regenerar só um segredo específico sem rodar o processo
  inteiro de novo (que, sendo idempotente quando não há mais
  placeholder, também não ajudaria — precisaria de um modo diferente
  pra "rotacionar só este segredo aqui")
