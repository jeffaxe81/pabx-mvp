# Manual 138 — Prova das rotas diretas 1010/1011 com MixMonitor real

## Objetivo e limite

As PRs 125–126 demonstraram a geração do WAV pelo Asterisk e a
reprodução HTTP a partir de uma rota **efêmera 9988**. Esta etapa
acrescenta um segundo ensaio, agora a partir do **próprio bloco
versionado das rotas 1010/1011** de `t1` e `t2`.

O ensaio preserva as linhas `Set(CDR(accountcode)=tN)`,
`MixMonitor(...,b)`, `Dial(...,20,g)` (exceto o nome do endpoint
destino), a lógica de pesquisa de satisfação e o fallback de fila.

Há **duas substituições exclusivas do staging**:

- `Playback(custom/aviso-gravacao)` é substituído por `NoOp` para
  não depender do arquivo de anúncio do cliente.
- `Dial(PJSIP/tN-recepcao[-2],20,g)` direciona para o ramal de teste
  `PJSIP/tN-1002`, com mídia SDES-SRTP/PCMU de laboratório. Não
  são alteradas as rotas versionadas da produção.

Esse procedimento preserva o comando de gravação usado no fluxo
produtivo, mas **não** comprova a recepção WebRTC original.

**Restauração obrigatória:** após as quatro chamadas diretas, o laboratório
reescreve o arquivo original de staging, executa `dialplan reload` e
comprova os destinos `tN-recepcao` e `tN-recepcao-2` antes do teste
Chromium/WebRTC. Uma restauração incompleta reprova o job. A primeira
execução da PR mostrou que não restaurar o dialplan interfere nos CDRs
do navegador; a correção foi acompanhada de regressões específicas.

## Quatro fluxos obrigatórios

- t1 → 1010
- t1 → 1011
- t2 → 1010
- t2 → 1011

Cada fluxo exige: route carregada; registro SIP; resposta do atendente;
SRTP bidirecional autenticado; BYE; CDR `ANSWERED` com `accountcode`,
canal A, canal B, contexto, origem, destino e `uniqueid` no mesmo
registro; novo arquivo WAV único e não ambiguamente atribuído; RIFF/WAVE
com áudio real; canais encerrados.

A sequência usa `Docker cp` para inspecionar o **arquivo recém-gerado**
sem publicar áudio, telefone, nome do arquivo, credenciais ou conteúdo
do CDR nos logs da CI. Os arquivos de ensaio são efêmeros.

## Critério de aceite

São **36 novos checks obrigatórios** no job de chamadas Asterisk real,
além das provas de MixMonitor da rota 9988 e da API HTTP. Falha de
qualquer check invalida esse job e bloqueia merge.

Testes estáticos recusam alterações inadvertidas no MixMonitor,
rotas ou CDR e demonstram que a cópia do staging não modifica
`asterisk/extensions.conf`.

```bash
python3 -m pytest -q scripts/tests/test_direct_route_recording_lab.py
python3 -m lab.asterisk_lab --calls --report /tmp/axe-lab-diretas.json
```

## Pendências explícitas

A entrega **não** homologa o destino WebRTC real, a gravação
da `Queue` atendida, a catalogação automática da operação,
autenticação SSO do usuário, segregação de volumes de produção,
backup/restauração ou voicemail PIN. O critério `recordings_real` não
é marcado automaticamente como concluído. O marco 8 segue aberto,
sem autorização operacional (GO=false).
