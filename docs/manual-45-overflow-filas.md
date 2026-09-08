# Manual 45 — Overflow entre filas (item #45)

## O que é
Se o cliente escolheu atendimento em inglês/espanhol (manual 35) mas
a fila daquele idioma não atende dentro de um tempo configurável, a
chamada **transborda automaticamente pra fila geral** do tenant —
qualquer atendente disponível é melhor do que ninguém, mesmo que não
fale o idioma escolhido.

## Como funciona
```
Cliente escolhe inglês → fila-t1-en
                            ↓ 45s sem resposta (OVERFLOW_TIMEOUT_SECONDS)
                          transborda → fila-t1 (geral)
                            ↓ ainda sem resposta
                          caixa de recado
```

A fila **geral** não tem overflow pra si mesma — isso seria um loop
infinito ("a fila geral estourou o tempo, transborda... pra fila
geral"). Só as filas de idioma específico (inglês/espanhol) calculam
um destino de overflow.

## Configuração
Um único valor global, em `[globals]` no `extensions.conf`:
```
OVERFLOW_TIMEOUT_SECONDS=45
```
Ajustável editando o arquivo (sem interface no painel ainda — ver
limitações).

## Arquitetura
Usa o **5º parâmetro nativo do `Queue()`** do Asterisk (tempo máximo
de espera), que faz `${QUEUESTATUS}` virar `"TIMEOUT"` quando
excedido — não é um mecanismo construído do zero. O overflow em si é
implementado com um `Goto(1000,1)` que reexecuta a extensão `1000`
com `${FILA_IDIOMA}` trocado pra fila geral — o cálculo de
`${FILA_OVERFLOW}` roda de novo nesse segundo passe e resulta vazio
(já que `FILA_IDIOMA` agora é a própria fila geral), o que
naturalmente impede um segundo nível de overflow sem precisar de
nenhuma variável de controle extra.

## Como testar manualmente
1. `docker compose up -d`, com só **uma** telefonista logada
   (`t1-recepcao`, que atende `fila-t1` e `fila-t1-en`)
2. Ligue, escolha inglês na URA, mas **não atenda** a chamada
3. Espere 45 segundos (o valor padrão) — confirme que a chamada
   transborda pra `fila-t1` (mesma telefonista, já que ela também
   está nessa fila) — pra testar de verdade a mudança de destino,
   use uma segunda telefonista que só esteja em `fila-t1`, não em
   `fila-t1-en`
4. Espere mais 45s sem atender — confirme que cai na caixa de recado

## Teste automatizado
- `tests/test_extensions_conf.py` (6 testes novos): timeout definido
  globalmente, `Queue()` recebe o timeout, overflow só calculado pras
  filas de idioma (nunca pra fila geral), `TIMEOUT` checado antes da
  caixa de recado, fallback pra caixa de recado quando não há mais
  overflow disponível, `Goto(1000,1)` troca a fila e tenta de novo
- `admin-api/tests/test_tenants.py::test_render_extensions_supports_queue_overflow`
  — tenant novo criado pelo wizard já nasce com a mesma lógica

## Limitações conhecidas (honestidade técnica)
- **Timeout único e global** — não é configurável por tenant nem por
  fila individualmente; todo mundo usa os mesmos 45 segundos
- **Sem interface no painel** pra ajustar o valor — precisa editar
  `extensions.conf` na mão e recarregar o dialplan
- **`Goto(1000,1)` reexecuta `Answer()`/`Playback(aviso-gravacao)`**
  — o aviso de gravação toca de novo no momento do overflow (efeito
  colateral pequeno, mas real: o cliente ouve o aviso uma segunda vez
  durante a mesma ligação)
- **Só existe overflow das filas de idioma pra fila geral** — não há
  um mecanismo genérico de "fila A transborda pra fila B" configurável
  livremente; seria uma extensão natural futura generalizar isso
- **Sem métrica de quantas chamadas transbordaram** — o evento
  acontece (visível no `NoOp()` dos logs do Asterisk), mas não é
  registrado em nenhum relatório do `queue-api` ainda
