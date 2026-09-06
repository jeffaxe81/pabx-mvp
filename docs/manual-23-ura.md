# Manual 23 — URA / IVR (item #17)

## O que é
Menu de voz pra chamadas que chegam sem ramal específico: "digite 1
para vendas, 2 para suporte", com comportamento diferente fora do
horário comercial e um modo feriado que pode ser ligado manualmente.

## Como funciona
Uma chamada sem DID mapeado (ou discando `700` internamente pra
testar) entra em `[ura-principal]`, que decide em ordem:

1. **Modo feriado está ligado?** (consulta o AstDB, gerenciável pelo
   painel de administração — manual 16) → toca a mensagem de feriado,
   **independente do dia/hora real**
2. **Está dentro do horário comercial?** (`GotoIfTime`, hoje
   configurado como seg-sex 08:00-18:00, direto no dialplan) → toca o
   menu principal
3. **Fora do horário comercial** → toca mensagem de fora de expediente

No menu principal: **1** vai pra fila de atendimento (mesma fila das
outras funcionalidades), **2** é um exemplo de rota diferente (ramal
direto da telefonista 1) — ajuste conforme sua necessidade real de
setores. Sem digitar nada, cai na fila depois de 10 segundos
(`WaitExten`) em vez de ficar a ligação presa.

## Sobre os arquivos de áudio (leia isto)
**Os três arquivos em `asterisk/sounds/custom/` são placeholders —
tons de beep gerados por código, não uma gravação de voz de verdade.**
Este projeto não tem como gravar ou sintetizar voz. São só pra você
confirmar que o mecanismo (tocar áudio, aguardar dígito, rotear)
funciona de ponta a ponta antes de trocar pelo áudio real:

- `menu-principal.wav` — 1 beep (placeholder do menu de horário comercial)
- `menu-fora-horario.wav` — 2 beeps (placeholder de fora de expediente)
- `menu-feriado.wav` — 3 beeps (placeholder de feriado)

**Pra usar de verdade**: grave (ou peça pra alguém gravar) os áudios
reais dizendo o menu, exporte como WAV mono 8kHz 16-bit, e substitua
os três arquivos mantendo os mesmos nomes — o dialplan não precisa
mudar.

## Como configurar
- **Horário comercial**: edite a linha `GotoIfTime(08:00-18:00,mon-fri,*,*?...)`
  em `asterisk/extensions.conf`, contexto `[ura-principal]`
- **Modo feriado**: pelo painel de administração (manual 16), botão
  "Ligar/Desligar modo feriado" — não precisa reload nem restart, o
  dialplan consulta o AstDB em tempo real a cada chamada
- **Opções do menu**: edite `[horario-comercial]` pra adicionar mais
  dígitos ou mudar o destino de cada um

## Como testar manualmente
1. `docker compose up -d`
2. De um ramal, disque `700` — deve ouvir 1 beep (placeholder do menu)
3. Digite `1` — deve cair na fila de atendimento (ramal 1000)
4. Disque `700` de novo, digite `2` — deve tocar direto na telefonista 1
5. Disque `700` e não digite nada — depois de 10s, deve cair na fila
6. Pelo painel, ligue o "modo feriado", disque `700` de novo — agora
   deve ouvir 3 beeps (placeholder de feriado) e cair direto na caixa
   de voz, **mesmo estando dentro do horário comercial**
7. Desligue o modo feriado antes de continuar testando outras coisas

## Teste automatizado
- `tests/test_extensions_conf.py` — modo feriado checado antes do
  horário comercial, dígitos 1 e 2 roteiam pra destinos diferentes,
  fora de horário e feriado caem em `VoiceMail()`, fallback de
  chamada externa entra na URA, extensão de teste `700` existe
- `tests/test_ura_sounds.py` — os 3 arquivos de áudio existem e são
  WAV mono 16-bit válidos (não testa o *conteúdo*, só o formato)
- `tests/test_docker_compose.py::test_ura_sounds_mounted_into_asterisk_container`
- `admin-api/tests/test_server_security.py::test_get_holiday_mode_requires_auth`
  — toggle de feriado também exige autenticação antes de mexer no AMI

## Limitações conhecidas (honestidade técnica)
- **Áudio placeholder, não voz real** (ver seção acima) — é o maior
  "isso não está pronto pra produção" deste manual
- **Horário comercial fixo no dialplan**, não configurável pelo painel
  — trocar exige editar `extensions.conf` e dar reload, diferente do
  modo feriado (que já é toggle em tempo real)
- **Só um nível de menu** — não tem submenu (ex: "vendas: 1 para
  produto A, 2 para produto B")
- **Só tenant 1** — tenant 2 não tem URA, mesma limitação de escopo já
  aceita em outras partes do painel de administração
- **Sem calendário de feriados automático** — o modo feriado é
  manual (alguém liga/desliga), não puxa uma lista de feriados
  nacionais/locais sozinho
