# Manual 40 — Aviso de gravação / conformidade LGPD (item #40)

## Origem
Este item veio de uma **auditoria de gaps** feita contra um framework
de avaliação de PABX corporativo (fornecido pelo usuário, baseado nos
critérios usados pra avaliar produtos de telefonia contra soluções
como as da Dígitro Tecnologia). A auditoria comparou nosso sistema
contra uma lista extensa de funcionalidades esperadas de um PABX/
contact center maduro — este foi o item de **maior risco** encontrado:
o sistema gravava chamadas (manual 09) sem nunca avisar o cliente,
uma lacuna real de conformidade com a LGPD (que exige aviso/
consentimento pra gravação de chamada).

## O que é
Um aviso sonoro toca **antes** de qualquer chamada ser conectada nos
pontos onde ela vai ser gravada — fila de atendimento (ramal `1000`)
e os ramais diretos das telefonistas (`1010`/`1011`). O cliente ouve
o aviso antes de falar com qualquer atendente.

## Onde foi aplicado
- `[t1-internal]` e `[t2-internal]`: extensões `1000`, `1010`, `1011`
- Template do wizard (`admin-api/tenants.py`): qualquer tenant criado
  a partir de agora já nasce com o aviso, sem precisar de ajuste manual
- **Não precisou** ser adicionado em `pickup-target` — a chamada já
  passou pela fila (que já tem o aviso) antes de ser redirecionada
  pro pickup, então o cliente já ouviu o aviso uma vez
- **Não se aplica** a `callback-connect` nem `click-to-call` — esses
  fluxos não gravam a chamada (sem `MixMonitor`), então não há nada
  pra avisar

## Ordem importa
O aviso toca **antes** do `MixMonitor()`/`Queue()` começar a gravar de
verdade — avisar depois que já gravou não cumpre o propósito do
consentimento. Isso é testado explicitamente
(`test_recording_consent_announcement_plays_before_recording_starts`).

## Como testar manualmente
1. `docker compose up -d`
2. Ligue pro ramal `1000` (fila) de um ramal de teste
3. Confirme que ouve o placeholder de áudio (aviso de gravação) antes
   de entrar na fila/tocar na telefonista
4. Repita discando `1010`/`1011` diretamente

## Teste automatizado
- `admin-api/tests/test_tenants.py::test_render_extensions_plays_recording_consent_announcement`
- `tests/test_extensions_conf.py`:
  - `test_recording_consent_announcement_plays_before_every_recorded_call`
    — os dois tenants têm o aviso nos 3 pontos gravados
  - `test_recording_consent_announcement_plays_before_recording_starts`
    — ordem correta (aviso antes da gravação começar)
- `tests/test_ura_sounds.py` — placeholder de áudio existe

## Limitações conhecidas (honestidade técnica)
- **Áudio placeholder** (beep), mesma situação de todos os outros
  pontos de áudio do projeto — precisa trocar por gravação real
  dizendo o aviso de verdade ("esta ligação pode ser gravada...")
  antes de produção
- **Não é consentimento ativo** — o cliente é avisado, mas não há uma
  opção de "aperte X se não concorda" que desvie a chamada pra um
  fluxo sem gravação; é aviso informativo, não consentimento
  opt-out/opt-in interativo
- **Não cobre gravações fora do dialplan principal** — se algum fluxo
  novo no futuro adicionar `MixMonitor()` em outro ponto, o aviso
  precisa ser adicionado manualmente lá também; não há um mecanismo
  central que garanta isso automaticamente pra qualquer gravação nova
- **Não é uma auditoria jurídica completa de LGPD** — cobre
  especificamente o aviso de gravação de chamada, que foi o gap mais
  óbvio encontrado; outros aspectos de conformidade (anonimização de
  dados sensíveis em transcrição, direito de eliminação, etc.)
  continuam como lacunas identificadas na auditoria, não
  implementadas ainda
