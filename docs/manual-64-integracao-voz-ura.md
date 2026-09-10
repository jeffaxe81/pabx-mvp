# Manual 64 — Integração de voz na URA principal (item #64)

## O que é
Até este ponto, o atendente virtual com IA (Whisper transcreve, Llama
3 classifica, Piper confirma em voz — manuais 37/49) só era alcançável
via uma extensão de teste isolada (`650`), separada do fluxo real de
atendimento. Este item integra essa pipeline **direto no menu
principal da URA**, como uma opção de voz ao lado das opções por
dígito de sempre.

## Como funciona
No menu principal (`[horario-comercial]`), além de apertar `1`
(vendas), `2` (suporte) ou `9` (callback), o cliente agora pode
apertar **`0`** pra falar em vez de digitar:

```
exten => 0,1,Goto(atendente-virtual,s,1)
```

Isso reaproveita o contexto `[atendente-virtual]` que já existia
(manual 37) — sem duplicar nenhuma lógica de transcrição/classificação.
`${TENANT}` já está definido no momento em que a chamada chega em
`horario-comercial` (veio de uma chamada real ou de uma extensão de
teste que já tratou disso antes), então o atendente virtual roteia
pro tenant certo automaticamente.

## Sem duplicação entre tenants
`[horario-comercial]` é um contexto **compartilhado** (manual 38) —
não existe uma cópia por tenant. Essa única mudança no dialplan já
vale pra `t1`, `t2`, e qualquer tenant futuro criado pelo wizard, sem
precisar tocar em `tenants.py`.

## Bug de conformidade encontrado durante esta integração
Ao revisar o `[atendente-virtual]` de perto pra fazer essa integração,
encontrei algo que passou despercebido desde a criação do recurso
(manual 37): a chamada `AGI(atendente_virtual.py)` **grava a voz do
cliente** (`RECORD FILE`), mas o contexto nunca tocava o aviso de
gravação (`custom/aviso-gravacao`, manual 40, LGPD) antes disso — ao
contrário de todo outro ponto do projeto que grava chamada. Corrigido:

```
exten => s,1,Set(TENANT=...)
 same => n,Answer()
 same => n,Playback(custom/aviso-gravacao)     ← adicionado
 same => n,Playback(custom/menu-atendente-virtual)
 same => n,AGI(atendente_virtual.py)
 ...
```

## Como testar manualmente
1. `docker compose up -d`
2. Disque pro DID de um tenant, deixe o menu principal tocar
3. Aperte `0` em vez de `1`/`2`
4. Confirme que ouve o aviso de gravação, depois o pedido pra
   descrever o motivo, depois a confirmação falada (manual 49), e só
   então é roteado

## Teste automatizado
- `tests/test_extensions_conf.py` (2 testes novos) — opção `0`
  presente e roteando pro atendente virtual, disponível igualmente
  pra qualquer tenant (sem hardcode de `t1`/`t2` no `Goto`)
- **911 testes no total**, em 8 suítes (a correção do aviso de
  gravação não adicionou teste dedicado além dos já existentes de
  integridade do dialplan, que continuam passando)

## Limitações conhecidas (honestidade técnica)
- **O áudio do menu principal não menciona a opção `0`** — o texto
  falado (`custom/menu-principal-*`) precisaria ser regravado/
  regenerado por TTS (manual 48) pra informar "aperte 0 pra falar com
  um assistente"; a opção funciona tecnicamente, mas ninguém saberia
  que ela existe só ouvindo o menu atual
- **Nunca testado contra um Asterisk real** — mesma situação de
  sempre pro resto do dialplan deste projeto
