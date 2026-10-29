# Manual 137 — Download HTTP de gravação gerada pelo Asterisk real

## Escopo e evidência

A prova Asterisk da PR #125 gerava áudio real com `MixMonitor()` e verificava
arquivo, CDR e diretórios de `t1`, `t2` e `t3`. Esta etapa conecta
**o mesmo WAV recém-gravado** à **Handler HTTP de produção** da `queue-api`,
executada apenas em loopback e com catálogo efêmero.

O laboratório faz as quatro verificações, em sequência:

1. **Captura:** confirma o CDR único com `accountcode`, contexto, canal,
   origem, destino, duração e `uniqueid` exatos. Uma referência de origem
   exclusiva (`CDR:<uniqueid>`) é exigida para cada empresa. Não há dedução
   pelo nome do áudio nem pelo número do chamador.
2. **Áudio real:** copia o WAV do container Asterisk de teste ao diretório
   temporário privado, exige arquivo regular, permissões privadas,
   cabeçalhos `RIFF/WAVE` e mais de 2.000 bytes. Não cria áudio falso.
3. **API real:** inicia `server.Handler` vinculada a `127.0.0.1` em porta
   efêmera, com catálogo e Bearer efêmeros de `t1/t2/t3/t10`.
   Exige a listagem exata da empresa, HTTP 200 e **bytes idênticos**
   ao WAV original no download autorizado.
4. **Negativas:** exige HTTP 404 para gravação de outra empresa, HTTP 401
   sem token e após revogação de `t1`, HTTP 403 para origem não permitida,
   lista vazia e 404 para `t10` (sem confundir com `t1`). Confirma que
   `t2` e `t3` continuam autorizados após a revogação.

A suíte `--calls` agora exige esses 17 checks adicionais além dos
27 checks já existentes do MixMonitor. A falha de qualquer check reprova
a execução e impede a conclusão do gate real do Asterisk.

Os nomes opacos dos arquivos, o conteúdo WAV, credenciais, nomes de pessoas
e cabeçalhos HTTP não entram no relatório público. O diretório de staging
e o container são descartados após a execução. O HTTP de teste não recebe
conexões de redes externas.

## Limites do aceite

A prova demonstra o caminho **MixMonitor de laboratório → WAV → catálogo
temporário com prova CDR → Handler HTTP real → download autorizado/negado**.

**Não comprova** ainda o fluxo produtivo `1010`/`1011` ou `Queue`,
catalogação automática confiável do ambiente de produção, autenticação SSO
do painel, segregação real de volumes físicos, criptografia em repouso,
rotina de backup/restauração, nem proteção contra escrita por outro processo
com privilégio no volume do Asterisk.

Assim, o critério ponderado `recordings_real` e o marco 8 continuam
**pendentes** até prova do dialplan de produção e revisão do ambiente-alvo.
Nenhum GO operacional é autorizado.

## Testes

```bash
python3 -m pytest -q scripts/tests/test_recording_http_mixmonitor_lab.py
python3 -m lab.asterisk_lab --calls --report /tmp/axe-lab-http-real.json
```

Pré-requisitos do laboratório: Docker descartável, libSRTP e permissões para
copiar o WAV gerado dentro do container. Nenhum dado de cliente é utilizado.
