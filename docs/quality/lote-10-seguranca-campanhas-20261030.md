# AXE PABX — 10 entregas técnicas: segurança do discador de campanhas

**Data:** 30/10/2026 — **escopo:** segurança e continuidade de campanhas existentes. **Status de homologação real:** pendente.

## Dez entregas implementadas

| Nº | Frente técnica | Mudança no fluxo real |
|---:|---|---|
| 01 | Persistência | Leitura não segue `symlinks` no catálogo de campanhas |
| 02 | Integridade JSON | Chaves duplicadas no mesmo objeto tornam o catálogo indisponível |
| 03 | Integridade JSON | Valores `NaN`/`Infinity` não são aceitos |
| 04 | Identidade | IDs de campanhas precisam ser únicos e o criador resolve colisões antes de publicar |
| 05 | Multiempresa | Ramal de discagem do cadastro precisa concordar com o tenant |
| 06 | Discador | Contatos de uma campanha não podem ter telefones repetidos ou não normalizados |
| 07 | Estado | Tentativas pendentes com contador esgotado e estados desconhecidos são recusados |
| 08 | Correlação AMI | Tentativa em `discando` exige `attempt_id` + `channel_id` e timestamp válidos |
| 09 | Segurança de chamadas | Evento AMI com disposição desconhecida **não libera nova tentativa** nem altera o registro |
| 10 | API/Operação | Consulta, criação e `dial-next` retornam `503` se o catálogo falhar, **sem chamar AMI** |

**Detalhes:** alterações concentradas em `queue-api/campaigns.py` e `queue-api/server.py`; testes negativos novos em `test_campaign_catalog_integrity.py`, `test_campaign_tenant_http.py` e ajuste do teste de resultado AMI desconhecido.

## Contratos e premissas

- Operações autenticadas por Bearer de tenant e chave operacional continuam intactas. A API não pode deduzir tenant a partir do telefone.
- Campanhas legadas **sem tenant** continuam legíveis para manutenção, mas não são elegíveis para originação pela API com tenant autenticado.
- Campanhas com mais de 1000 contatos, catálogo com mais de 10000 campanhas, ramais inválidos, números duplicados e estado ambíguo falham de modo conservador.
- O status `discando` **não comprova** que a chamada foi concluída; sem evento AMI correlacionado o contato fica sob revisão e não é reencaminhado automaticamente.
- A gravação e o destino RTP não são alterados; esse lote não aumenta o número de chamadas que o Asterisk é capaz de estabelecer.
- Este lote executa verificações de código e laboratório CI. **Não foi realizado deploy de produção nem homologação no cliente.** As 15 provas operacionais reais e o indicador formal de 7/16 marcos (43,8%) permanecem pendentes.
- Merge na `main` somente quando todos os checks e workflows da CI estiverem aprovados.
