# Manual 30 — Discador automático / campanhas (item #25)

## O que é
Lista de contatos pra uma equipe comercial discar em sequência, com
controle de tentativas e resultado de cada uma — sem precisar
discar manualmente número por número. **Reaproveita o mesmo mecanismo
do click-to-call** (manual 12): o Asterisk liga primeiro pro ramal do
atendente, e quando ele atende, completa pro número do contato.

## Como funciona
1. Cria uma campanha: nome, ramal do atendente, lista de números
2. Clica "Discar próximo contato" — o sistema pega o primeiro contato
   `pendente`, marca como `discando`, e dispara o `Originate` via AMI
   (mesmo contexto `click-to-call` do manual 12)
3. Quando a chamada termina, o evento `DialEnd` (o mesmo já usado pra
   detectar chamada perdida, manual 11) é conferido: se o número
   bate com um contato `discando` de alguma campanha, o resultado é
   registrado automaticamente
4. Resultado mapeado: `ANSWER` → atendida (final); `BUSY`/`NOANSWER`/
   `CONGESTION` → volta pra `pendente` (tenta de novo) até **3
   tentativas**, depois vira `esgotado`

## Segurança
**Reaproveita a mesma chave do click-to-call** (`CLICK_TO_CALL_API_KEY`)
— mesma categoria de risco (originar chamada via AMI), mesma proteção.
Se essa chave não estiver configurada, campanhas ficam desabilitadas
junto (mesmo padrão "desligado por padrão" do resto do projeto).

## Como usar
1. Configure `CLICK_TO_CALL_API_KEY` no `docker-compose.yml` (manual 12)
2. Acesse `http://<ip>:8082/campanhas.html?api=http://<ip>:8090`
3. Cole a mesma chave no campo "Chave de API"
4. Crie a campanha: nome, ramal do atendente, um número por linha
5. Clique "Discar próximo contato" — o ramal do atendente toca,
   atende, e a chamada completa pro contato

## Como testar manualmente
1. Crie uma campanha com 2-3 números de teste
2. Clique "Discar próximo" — confirme que o ramal do atendente toca
3. Atenda — confirme que a chamada completa pro número discado
4. Depois de desligar, atualize a lista — o contato deve aparecer
   como "Atendida"
5. Repita sem atender — o contato deve continuar "Pendente" (ainda
   tem tentativas) até a 3ª vez, quando vira "Esgotado"

## Teste automatizado
- `queue-api/tests/test_campaigns.py` — validação de entrada,
  sanitização de número (mesma do click-to-call), próximo contato
  pendente, contagem de tentativas, mapeamento de disposição pra
  status (inclusive a lógica de retry até `MAX_ATTEMPTS`), extração
  do número discado a partir do evento `DialEnd`
- `queue-api/tests/test_server_routes.py` — todas as rotas de
  campanha exigem a chave de API **antes** de tocar no store/AMI;
  marcar como "discando" acontece antes do `Originate` de verdade
  (evita corrida de clique duplo)
- `tests/test_campaigns_html.py` — IDs da interface, chave sempre
  enviada, contatos parseados um por linha
- `tests/test_docker_compose.py::test_campaigns_path_configured`

## Limitações conhecidas (honestidade técnica)
- **É um discador "preview manual", não "power dialer" automático** —
  a telefonista/atendente clica "discar próximo" um de cada vez; não
  há discagem contínua automática sem intervenção
- **Correlação de resultado por número discado, não por ID único** —
  se dois contatos de campanhas diferentes tiverem o mesmo número
  "discando" ao mesmo tempo (cenário raro num MVP de escala pequena),
  o primeiro encontrado recebe o resultado
- **Sem agendamento** (discar só em certo horário, respeitar fuso
  horário do contato, etc.)
- **Sem integração com o discador de saída em massa de verdade** (não
  há limite de chamadas simultâneas, nem detecção de secretária
  eletrônica) — isso é característica de discadores preditivos
  comerciais, fora do escopo deste MVP
- **Sem teste de integração real** do fluxo Originate→DialEnd — mesma
  situação já documentada pro resto das integrações AMI do projeto
