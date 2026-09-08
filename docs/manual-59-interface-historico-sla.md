# Manual 59 — Interface do histórico de SLA no painel (item #59)

## O que fecha
O manual 58 (histórico de SLA por dia) documentou explicitamente como
limitação: **"sem interface no painel ainda — só a API expõe o
histórico"**. Este item fecha essa lacuna.

## O que é
Uma seção nova no painel operacional, "Histórico de SLA por dia",
mostrando cada dia já fechado (do mais recente pro mais antigo) com
o percentual de SLA de cada fila naquele dia — a mesma informação já
disponível em `GET /api/metrics/sla/history` (manual 58), agora
visível sem precisar consultar a API na mão.

## Como usar
Painel operacional → seção "Histórico de SLA por dia", logo abaixo do
histórico de tempo em pausa. Cada linha em negrito é uma data; as
linhas indentadas abaixo dela são as filas daquele dia com seu
percentual (`80% (32/40)`).

## Antes de ter dados
Como o histórico só é gravado à meia-noite (manual 58), um ambiente
recém-instalado não vai mostrar nada aqui até o primeiro dia fechar
de verdade — a interface trata isso explicitamente ("Nenhum dia
fechado ainda"), não como uma tela vazia sem explicação.

## Como testar manualmente
1. `docker compose up -d`, deixe rodando por mais de um dia com
   chamadas de verdade (ou ajuste o relógio do sistema, se for só pra
   testar a interface)
2. Abra o painel operacional — confirme que a seção mostra os dias
   fechados, mais recente primeiro

## Teste automatizado
- `tests/test_ops_panel.py` (3 testes novos) — endpoint buscado e
  renderizado, ordenado do mais recente pro mais antigo, trata estado
  vazio sem quebrar
- **879 testes no total**, em 8 suítes

## Um detalhe de teste que valeu registrar
Ao adicionar `renderSlaHistory`, os testes existentes de `renderSla`
(a função do SLA do **dia atual**, manual 46) começaram a falhar —
`renderSla` é literalmente um prefixo de `renderSlaHistory`, e como a
nova função acabou definida antes da antiga no arquivo, uma busca por
substring (`"function renderSla"`) passou a encontrar a função errada
primeiro. Corrigido tornando a busca mais específica
(`"function renderSla("`, com parêntese) — o tipo de coisa que só
aparece quando você começa a nomear funções de um jeito parecido.

## Limitações conhecidas (honestidade técnica)
- **Sem filtro de intervalo de datas na interface** — mostra todo o
  histórico acumulado, sem paginação nem limite de dias exibidos
- **Sem gráfico** — só uma lista de números; comparar tendência ao
  longo do tempo visualmente exigiria um gráfico, não implementado
- **Recarrega no mesmo ciclo de polling do resto do painel**
  (frequência pensada pra dados que mudam a cada segundo) — o
  histórico só muda uma vez por dia, então a maior parte dessas
  consultas trazem exatamente o mesmo resultado; não é incorreto, só
  não é a frequência de atualização mais eficiente possível
