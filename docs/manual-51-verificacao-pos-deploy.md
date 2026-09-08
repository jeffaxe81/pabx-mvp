# Manual 51 — Verificação pós-deploy (item #51)

## O que é
Complementa o roteiro de implantação (manual 00) automatizando o que
dá pra checar programaticamente **depois** que o `docker compose up`
já rodou num ambiente real. **Não substitui** testar uma chamada de
verdade — cobre só "os serviços estão no ar" e "os segredos foram
trocados", não "o áudio funciona" ou "a fila roteia certo".

Este é um dos itens do roteiro original de próximos passos que eu
não conseguia executar sozinho (precisa de um Asterisk real
rodando) — a solução prática foi construir a **ferramenta** que você
roda quando tiver o ambiente de verdade, em vez de deixar isso como
um passo manual sem apoio nenhum.

## Três checagens
1. **Segredos** — reaproveita a mesma lógica do manual 50
   (`find_placeholders`) pra confirmar que nenhum `troque_esta_senha_*`
   sobrou em `docker-compose.yml`, `manager.conf` ou `pjsip.conf`
2. **AMI** — tenta logar de verdade na porta 5038 com as credenciais
   informadas; só aceita se o Asterisk responder `Response: Success`
3. **Serviços HTTP** — bate em cada serviço (`queue-api`, `admin-api`,
   `ai-worker`, `webphone`) e confere se responde `200`

## Como usar
```bash
python3 scripts/verify_deployment.py
```
O script pede o `AMI_SECRET` atual (não lê de arquivo automaticamente
de propósito — evita que o script precise de acesso de leitura a
segredos que talvez você já tenha movido pra fora do repositório, ver
manual 50). No final, imprime um resumo com código de saída `0`
(tudo certo) ou `1` (algo falhou) — dá pra usar em automação/CI se
quiser.

## O que ISSO NÃO valida
- Se uma chamada de verdade completa com áudio nos dois sentidos
- Se a fila roteia corretamente
- Se a URA/atendente virtual funcionam de ponta a ponta
- Se o TLS está configurado certo (só confirma que o serviço responde
  na porta HTTP, não testa a porta WSS/TLS do webphone)

Pra essas coisas, siga o roteiro de teste manual do manual 00
fase por fase — não existe atalho automatizado real pra "uma
ligação funciona", precisa ouvir de verdade.

## Como testar (o script em si)
1. `python3 scripts/verify_deployment.py` contra um ambiente real
2. Confirme que a checagem de segredos reflete o estado de verdade
   (rode antes e depois do manual 50 pra ver a diferença)
3. Digite um `AMI_SECRET` errado de propósito — confirme que a
   checagem 2 falha claramente
4. Pare um dos serviços (`docker compose stop queue-api`) — confirme
   que a checagem 3 aponta ele como não saudável

## Teste automatizado
- `scripts/tests/test_deployment_checks.py` (11 testes) — lógica pura:
  relatório de segredos remanescentes por arquivo, parsing da
  resposta de login AMI, resumo de saúde HTTP
- `scripts/tests/test_verify_deployment_runner.py` (8 testes de
  integração, com rede **mockada**) — leitura de arquivo real (sem
  tocar o repositório), login AMI aceito/recusado/conexão recusada,
  serviços saudáveis/indisponíveis
- **804 testes no total**, em 8 suítes

## Limitações conhecidas (honestidade técnica)
- **Nunca rodado contra um ambiente real** — mesma situação já
  documentada pro resto das integrações de rede deste projeto; a
  primeira execução de verdade é sua
- **Pede o `AMI_SECRET` interativamente** — não dá pra automatizar
  numa pipeline CI sem alguma adaptação (ex: variável de ambiente em
  vez de `input()`)
- **Não valida certificados TLS** de verdade, só que a porta HTTP
  simples responde
- **Portas fixas** (`127.0.0.1:8090` etc.) — se você mudou as portas
  padrão no `docker-compose.yml`, precisa editar `HTTP_SERVICES` no
  script também
