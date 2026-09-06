# Manual 10 — Multi-chamada (segunda linha)

## O que é
A telefonista pode ter **duas chamadas simultâneas** — atender uma
segunda ligação sem derrubar a primeira (que fica automaticamente em
espera), e alternar entre as duas com um clique.

Antes desta funcionalidade, uma segunda chamada chegando era recusada
automaticamente sem alternativa.

## Como funciona
- **Linha 1**: primeira chamada, funciona exatamente como antes
- **Linha 2**: se uma segunda chamada chega enquanto já se está em
  outra, aparece um aviso ("Chamada na linha 2") **sem tirar a
  chamada atual da tela** — a telefonista decide se atende ou recusa
- Ao **atender a linha 2**: a linha 1 é colocada em espera
  automaticamente
- Uma **barra de linhas** aparece no topo da tela de chamada sempre
  que as duas linhas estão ocupadas, mostrando quem está em cada uma
  e o estado (Ativa/Espera/Tocando) — clique numa linha em espera pra
  voltar pra ela (a outra vai automaticamente pra espera)
- Se a linha ativa **cai** (chamador desliga) e existe uma segunda
  linha em espera, a interface **volta pra ela automaticamente**,
  tirando-a da espera — a telefonista nunca fica "no vazio" tendo uma
  chamada esperando
- Uma terceira chamada simultânea continua sendo recusada
  automaticamente (limite de 2 linhas)

## Interação com outras funcionalidades
- **Transferência assistida** (manual 07) exige que só uma linha
  esteja ocupada no momento de iniciar a consulta — se as duas linhas
  já estão em uso, o botão avisa e não deixa iniciar (não há uma
  terceira linha pra consulta)
- **Discagem/transferência por clique num colega** (manual 06) sempre
  atua na linha atualmente em foco (a que está sendo exibida na tela)

## Como configurar
Nada a configurar — é só lógica na interface (`webphone/index.html`).
Não precisa de mudança no Asterisk, porque cada linha é uma sessão SIP
independente (o ramal simplesmente aceita duas chamadas simultâneas,
o que o PJSIP já suporta nativamente).

## Como testar manualmente
1. Três outros ramais/softphones além da telefonista web: A, B, C
2. A liga pra telefonista (ramal 1000) — ela atende (linha 1)
3. B liga pra telefonista **enquanto ela ainda fala com A** — deve
   aparecer o aviso "Chamada na linha 2", sem esconder a chamada com A
4. Telefonista clica "Atender" no aviso da linha 2 — confirme que A
   fica em espera (silêncio/música de espera do lado de A) e ela passa
   a falar com B
5. A barra de linhas deve aparecer no topo, mostrando as duas
6. Clique na linha 1 na barra — confirme que volta a falar com A
   (e B vai pra espera)
7. Encerre a chamada com A (linha ativa) — confirme que a interface
   volta automaticamente pra B (tirando-o da espera)
8. Com as duas linhas ocupadas, peça pro ramal C ligar — confirme que
   a chamada de C é recusada automaticamente (ocupado)

## Teste automatizado
`tests/test_webphone_html.py::test_answering_second_line_holds_the_first`
`tests/test_webphone_html.py::test_line_ended_falls_back_to_other_line_automatically`
`tests/test_webphone_html.py::test_third_simultaneous_call_is_rejected`
`tests/test_webphone_html.py::test_line_switcher_prevents_switching_to_unanswered_line`

## Limitações conhecidas
- Limite fixo de **2 linhas** — não é configurável nem escalável além
  disso neste MVP
- **Mudo** (`isMuted`) é um estado único, não por linha — ao trocar de
  linha, o estado de mudo não é preservado (se você mudou a linha 1 e
  troca pra linha 2, precisa mutar de novo se quiser)
- Sem indicação sonora (bipe) de chamada em espera — só o aviso visual
  na tela
- A gravação automática (manual 09) cobre cada linha independentemente
  (cada uma gera seu próprio arquivo), mas não há gravação combinada
  caso a telefonista alterne entre as duas
