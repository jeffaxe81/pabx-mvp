# Manual 141 — Cockpit de voz com 50 capacidades analíticas

## Escopo de entrega

Este incremento adiciona **50 indicadores operacionais de leitura**, não 50 novos controladores de chamadas. O objetivo é dar transparência e antecipação de problemas no call center de voz sem alterar roteamento, telefonia em produção ou expor informações pessoais. Possui API JSON autenticada, console web responsivo, filtragem, atualização periódica e exportação CSV.

**Fora do escopo:** IA, canais digitais, WFM, discador preditivo, alteração automática de escala, SLA contratual, bilhetagem financeira, homologação de tráfego SIP/AMI em ambiente real.

## Operação

- Serviço: `queue-api`, aproveita dados já observados em memória via AMI, SLA, estado BLF e registros de qualidade/alerta.
- Rota: `GET /api/supervision/cockpit` com `Authorization: Bearer <token>` válido para papel **supervisor** ou **admin**. O tenant é derivado da identidade autenticada; `?tenant=t2` não altera o escopo.
- Interface: `/call-center.html` no webphone, informando URL HTTPS da API e token de supervisão, sem armazená-lo no localStorage, sessionStorage, cookies ou URL.
- Navegadores de outra origem exigem o FQDN exato em `QUEUE_CORS_ORIGINS`. O catálogo `QUEUE_ACCESS_POLICY_PATH` precisa estar corretamente configurado com permissões restritas (modo 0600).
- `Cache-Control: no-store`; resposta sem nomes/telefones dos clientes, canais de ligação, identificadores de chamada, ramais individuais ou motivos textuais de pausa.
- UI atualiza a cada 15 s enquanto aberta; permite buscar, filtrar por área e exportar o snapshot em CSV.

## Catálogo das 50 entregas analíticas

| ID | Área | Indicador disponibilizado |
|---|---|---|
| CC-01 | fila | Chamadas aguardando |
| CC-02 | fila | Filas com espera |
| CC-03 | fila | Maior espera |
| CC-04 | fila | Espera média |
| CC-05 | fila | Mediana de espera |
| CC-06 | fila | Espera P90 |
| CC-07 | fila | Espera P95 |
| CC-08 | fila | Espera acima do limite SLA |
| CC-09 | fila | Espera acima de 60 s |
| CC-10 | fila | Espera acima de 120 s |
| CC-11 | fila | Espera de 0 a 19 s |
| CC-12 | fila | Espera de 20 a 59 s |
| CC-13 | fila | Espera de 60 a 119 s |
| CC-14 | fila | Espera de 120 s ou mais |
| CC-15 | fila | Maior fila por volume |
| CC-16 | equipe | Ramais monitorados |
| CC-17 | equipe | Ramais livres |
| CC-18 | equipe | Ramais ocupados |
| CC-19 | equipe | Ramais tocando |
| CC-20 | equipe | Ramais indisponíveis |
| CC-21 | equipe | Agentes pausados |
| CC-22 | equipe | Ausências manuais |
| CC-23 | equipe | Participação livre |
| CC-24 | equipe | Participação ocupada |
| CC-25 | equipe | Participação indisponível |
| CC-26 | equipe | Pausas por ramal monitorado (aprox.) |
| CC-27 | equipe | Ausências por ramal monitorado (aprox.) |
| CC-28 | equipe | Fila por ramal livre |
| CC-29 | equipe | Reforço sugerido (3 por ramal) |
| CC-30 | equipe | Fila sem ramais livres |
| CC-31 | sla | Chamadas oferecidas |
| CC-32 | sla | Chamadas dentro do SLA |
| CC-33 | sla | Chamadas fora do SLA |
| CC-34 | sla | SLA observado |
| CC-35 | sla | SLA de referência |
| CC-36 | sla | Diferença para referência |
| CC-37 | sla | Percentual fora do SLA |
| CC-38 | sla | Filas abaixo de 80% |
| CC-39 | sla | Atendimentos faltantes no volume atual |
| CC-40 | sla | Próximas chamadas perfeitas para recuperar 80% |
| CC-41 | qualidade | Eventos perdidos no buffer |
| CC-42 | qualidade | Alertas de fraude no buffer |
| CC-43 | qualidade | Medições de qualidade ruim |
| CC-44 | qualidade | Soma de sinais nos buffers |
| CC-45 | qualidade | Categorias de risco com sinais |
| CC-46 | diagnostico | Atenção na fila |
| CC-47 | diagnostico | Atenção à equipe |
| CC-48 | diagnostico | Atenção ao SLA |
| CC-49 | diagnostico | Atenção à qualidade |
| CC-50 | diagnostico | Categorias em alerta |

## Interpretação

**Referência SLA:** 80% das chamadas atendidas até o limite `SLA_THRESHOLD_SECONDS`. Métricas 39 e 40 são contas matemáticas conservadoras; não são previsão automática de qualidade. Recomendações de equipe assumem referência arbitrária de até 3 chamadas aguardando por ramal livre — isso **não** é dimensionamento de Erlang C nem WFM.

Se não houver amostra, o backend retorna `null` em medidas que exigem denominador ou evidência, incluindo SLA, percentis de fila e riscos derivados. Não transforma ausência de dados em sinal verde. As contagens de buffers de fraude, qualidade e chamadas perdidas não representam janela única nem medem duplicatas entre categorias. Estados BLF podem incluir ramais que não são agentes.

A operação é **somente leitura** e não altera status de agente, configurações, fila, gravações ou AMI. Cada indicador pode ser testado isoladamente com snapshots sintéticos. Faltam ainda ensaios de carga/integração real com troncos SIP, Asterisk e grupos de agentes.

## Aceite automatizado e rastreabilidade

- `queue-api/tests/test_call_center_cockpit.py`: 50 casos individuais de valor esperado, catálogo único, isolamento t1/t2/t10, tipos de dados malformados, falta de amostra, limites de percentil e SLA.
- `queue-api/tests/test_call_center_cockpit_http.py`: servidor HTTP real de loopback com mocks, 401 não autenticado, 403 agente, CORS restrito, isolamento por tenant e supressão de informações privadas.
- Rodar na raiz: `python -m pytest -q queue-api/tests/test_call_center_cockpit.py queue-api/tests/test_call_center_cockpit_http.py` com `PYTHONPATH=queue-api`.
- Gate geral: `.github/workflows/quality-gates.yml`, job `pytest | queue-api`; `ui-regression.yml` quando o webphone é alterado.

**Critério de 100% de implantação:** os testes de CI e a homologação de chamadas reais precisam passar em ambiente controlado. Sem essa evidência, a entrega é um incremento versionado, não uma release operacional homologada.
