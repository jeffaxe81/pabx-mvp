# Manual 17 — Painel operacional consolidado (item #11)

## O que é
Uma tela só (`webphone/painel-operacional.html`) reunindo o que antes
estava espalhado em painéis separados dentro do console de cada
telefonista: chamadas em espera, estado dos ramais (livre/ocupado/
tocando) e métricas do dia. Pensada pra ficar aberta numa TV/monitor
de parede da supervisão, ou numa aba separada de quem coordena a
equipe — não é uma ferramenta de atender chamada, é só visão.

## Como funciona
- **Estado dos ramais**: novo rastreador (`extension_states.py`) no
  `queue-api`, alimentado pelo evento AMI `ExtensionStatus` — o mesmo
  mecanismo de hint já usado pelo BLF da interface web (manual 06),
  só que do lado do servidor, sem precisar de uma assinatura SIP por
  navegador
- **Fila e métricas**: reaproveita os endpoints que já existiam
  (`/api/queue`, `/api/metrics/today`) — nada novo ali
- **Atualização automática**: a página busca os 3 endpoints a cada 5
  segundos, sozinha (`setInterval`)

## Como configurar e acessar
Não precisa configuração adicional — os endpoints já existem. Acesse:
```
http://<ip-do-servidor>:8082/painel-operacional.html?api=http://<ip-do-servidor>:8090
```
O parâmetro `?api=` aponta pro `queue-api`. Também tem um link "Abrir
painel operacional" na barra lateral do console da telefonista, que já
monta essa URL sozinho com o endereço da API configurado ali.

## Como testar manualmente
1. `docker compose up -d`
2. Abra o painel operacional (link acima)
3. Confirme que os 3 blocos aparecem: métricas, ramais, fila
4. Registre um softphone e mude seu estado (livre → em chamada) —
   dentro de 5 segundos o painel deve refletir a mudança
5. Simule uma chamada na fila (discar `800`) — deve aparecer no bloco
   "Fila de espera" com o tempo de espera contando

## Teste automatizado
- `queue-api/tests/test_extension_states.py` — aplicação do evento
  `ExtensionStatus`, mapeamento de código pra rótulo, ordenação
- `tests/test_ops_panel.py` — IDs da página, os 3 endpoints são
  consultados, atualização periódica, URL da API configurável por
  query string, link a partir do console da telefonista

## Limitações conhecidas
- **Sem autenticação** — quem tiver o link acessa (mesma limitação já
  aceita nos outros endpoints do `queue-api` para uso em rede interna)
- **Só ramais que já geraram algum evento `ExtensionStatus`** aparecem
  na lista — um ramal recém-criado só aparece depois da primeira
  mudança de estado, não antes
- Não mostra chamadas em andamento com detalhe (quem fala com quem,
  duração) — só o volume agregado do dia; isso ficaria pra uma versão
  futura mais completa do item #11 original ("chamadas em andamento")
