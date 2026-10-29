# Manual 136 — Prova de MixMonitor real com mídia SRTP por empresa

## Objetivo

Esta etapa acrescenta uma **prova executável** da criação de arquivos pelo
**MixMonitor do Asterisk real**, no container efêmero usado pela CI. Diferente
dos testes anteriores de catálogo/HTTP, o próprio Asterisk recebe áudio PCMU
sintético, cifra-o/decifra-o como mídia SRTP e grava um WAV no spool.

## Como funciona

- O laboratório cria exclusivamente em sua cópia privada do dialplan a
  extensão `9988` para `t1`, `t2` e `t3`. **Essa extensão não é instalada
  nem versionada como rota de produção**.
- Cada origem `tN-1001` registra-se por SIP/TLS, disca `9988`, e transmite
  cerca de 1,6 s de tons PCMU sintéticos após negociar SDES-SRTP.
- O dialplan temporário executa `MixMonitor()`, `Wait()` e
  `StopMixMonitor()`, com `CDR(accountcode)=tN`.
- O laboratório exige arquivo no caminho privado
  `/var/spool/asterisk/monitor/tN/<aleatório>.wav`, com tamanho mínimo
  acima do cabeçalho WAV; valida CDR de origem/contexto/tenant no mesmo
  registro, sem combinar campos de chamadas diferentes.
- Confirma a ausência do mesmo arquivo nas pastas das outras duas empresas,
  encerramento SIP e ausência de canais pendentes.
- O relatório da CI contém apenas booleanos, contagens e nomes dos tenants.
  Não inclui o áudio, nome do arquivo, cabeçalhos SIP ou credenciais.

Os checks obrigatórios de `lab.recording_checks` fazem parte da suíte de
chamadas reais (`--calls`); falha de um deles reprova esse job do laboratório.

## Testes estáticos

`scripts/tests/test_recording_mixmonitor_lab.py` valida as rotas temporárias,
a correlação de CDR sem colisão de prefixos, a exigência de áudio acima do
cabeçalho e a presença dos checks no gate obrigatório.

## O que ainda NÃO está homologado

Este ensaio **não** valida o caminho de produção `1010`/`1011` ou
`Queue`, não estabelece isolamento de volumes independentes, não vincula
automaticamente o áudio a uma identidade SSO e não faz reprodução HTTP com
a mídia recém-gravada. Ele também não testa PIN do voicemail.

Por isso o critério ponderado `recordings_real` do marco 8 segue
**pendente**; o marco formal e o GO operacional não mudam automaticamente.
Para conclusão integral são necessários origem CDR do fluxo produtivo,
importação autorizada, playback real por tenant e verificação da infraestrutura.

## Comandos de execução

```bash
python3 -m pytest -q scripts/tests/test_recording_mixmonitor_lab.py
python3 -m lab.asterisk_lab --calls --report /tmp/axe-lab-mixmonitor.json
```

A execução exige Docker local isolado, dependências de SRTP e permissão de
uso do laboratório. Nenhum número de cliente é usado.
