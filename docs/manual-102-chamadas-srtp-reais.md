# Manual 102 — Chamadas internas reais com SIP/TLS e SDES-SRTP

## Escopo

Esta etapa estende o [laboratório de registro](manual-101-laboratorio-sip-real.md)
para realizar seis chamadas: 1001 → 1002 e 1002 → 1001 em cada empresa
t1, t2 e t3. Usa Asterisk real, os contextos versionados e o gerador
administrativo real para os ramais seguros adicionais de t2/t3.

Cada chamada exige registro autenticado dos dois clientes, INVITE com
Digest, atendimento, ACK, mídia nos dois sentidos, BYE confirmado,
ausência de canais residuais e CDR atendido com origem, destino,
contexto, tenant, canais e duração coerentes. As rotas diretas estáticas
atribuem `CDR(accountcode)` ao tenant antes de executar `Dial()`. Os ramais estáticos de
t1 e t2 também fazem parte do percurso validado.

## Execução

Em checkout limpo, Linux com Docker e OpenSSL, sem outro serviço ocupando
as portas locais documentadas no Manual 101:

```bash
python3 -m pip install -r lab/requirements.txt
python3 -m lab.asterisk_lab --calls --report /diretorio/relatorio-chamadas.json
```

O workflow `asterisk-lab.yml` mantém o teste de 22 verificações de registro
e acrescenta um job independente de chamadas. O modo `--calls` exige
70 verificações: as 22 originais e oito aceites para cada uma das seis
chamadas. Resultado incompleto ou negativo retorna exit code 1.

## Mídia e proteção

O cliente seleciona PCMU/8000 mesmo quando o Asterisk oferece outros
codecs, preserva a tag SDES da oferta e responde com PCMU em `RTP/SAVP` com
`AES_CM_128_HMAC_SHA1_80`. Chaves de 30 bytes são geradas por execução
e entregues somente pelo SDP dentro da conexão TLS com certificado
verificado. O cliente usa pylibsrtp 1.0.0; não implementa criptografia.

São enviados tons sintéticos distintos a cada 20 ms. O receptor verifica
a autenticação SRTP e compara os 160 bytes PCMU de cada pacote com o tom
da outra ponta. Cinco ou mais pacotes corretos em cada direção são
necessários. Isso comprova o conteúdo de mídia nesse trajeto; não mede
MOS, latência de rede externa ou qualidade acústica de headset.

O cliente também altera uma cópia de um pacote recebido e tenta
reprocessar um pacote já aceito: libsrtp deve recusar ambos. Esses dois
testes verificam a proteção do cliente do laboratório; não constituem
um ensaio de injeção de pacotes contra o Asterisk.

## Privacidade e evidências

Aplica as mesmas regras de exportação Git, permissões privadas,
imagem fixada por digest, certificado efêmero, token de propriedade
e remoção de container do Manual 101. O CDR customizado é lido somente
em memória para verificar os campos esperados. Gravações sintéticas
eventualmente geradas pelo dialplan ficam no container descartável.

O relatório público contém SHA, versão/digest, resultados booleanos,
contagens de pacotes, perfil criptográfico e eventos de protocolo
predefinidos (por exemplo, `invite_received` e `response:200`). Não inclui SDP, Call-ID,
credenciais, chaves, CDR completo ou arquivos de áudio.

## Limites

O marco 5 do programa só pode ser concluído após CI real bem-sucedida.
Este teste usa TLS e SDES-SRTP. A homologação posterior de WSS/DTLS
e dos DIDs está registrada no [Manual 104](manual-104-webrtc-dids-reais.md).
Permanecem pendentes os aceites completos de isolamento funcional
cruzado, filas, URA, transferência, gravações,
restauração, carga e operação em servidor de homologação.
`operational_go_authorized` permanece `false`.

PR dependente: [#54](https://github.com/jeffaxe81/pabx-mvp/pull/54),
baseada na [#53](https://github.com/jeffaxe81/pabx-mvp/pull/53).

## Histórico de correções desta entrega

- O contato SIP do Asterisk pode usar `transport=TLS` e omitir `usuario@`;
  o cliente agora aceita essas formas sem permitir host externo ou porta inválida.
- A oferta de mídia pode listar vários codecs. O cliente seleciona PCMU
  e preserva a tag SDES, mantendo a exigência de SRTP autenticado.
- As rotas diretas estáticas de t1/1001–1002 e t2/1001 não marcavam
  `CDR(accountcode)`. A atribuição ao tenant agora precede `Dial()`.
- Falhas de libsrtp agora produzem relatório JSON de reprovação sanitizado.
  Causas da ponta chamada também são preservadas, evitando ocultá-las
  atrás de um timeout da ponta originadora.
- A preparação do laboratório cria o diretório `cdr-custom` antes das
  chamadas; o backend Asterisk 22.11 abre o arquivo de saída sem criar
  seu diretório pai. O diagnóstico reconhece a etiqueta `Logging:`
  apresentada pela CLI dessa versão.

## Evidência de execução

A execução [39980624663](https://github.com/jeffaxe81/pabx-mvp/actions/runs/39980624663)
aprovou os dois jobs: **22/22** verificações de registro e **70/70**
verificações do modo de chamadas. As seis chamadas tiveram estabelecimento,
mídia SRTP bidirecional com payload correto, desligamento, canais liberados
e CDR atendido coerente. O container foi removido ao final.

A [CI estática 39980624670](https://github.com/jeffaxe81/pabx-mvp/actions/runs/39980624670)
aprovou as oito suítes Python. A validação local final passou em
**1.361 testes Python e 7 Node**. A revisão independente teve três
achados importantes, corrigidos com regressões; nenhum crítico ou
menor adiado. O marco 5 está concluído, totalizando **5 de 16 marcos**.
Naquele checkpoint, o marco 6 continuava em andamento. Sua conclusão
posterior e a do marco 7 estão documentadas no Manual 104.
