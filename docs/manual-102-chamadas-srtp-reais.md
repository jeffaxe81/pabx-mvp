# Manual 102 — Chamadas internas reais com SIP/TLS e SDES-SRTP

## Escopo

Esta etapa estende o [laboratório de registro](manual-101-laboratorio-sip-real.md)
para realizar seis chamadas: 1001 → 1002 e 1002 → 1001 em cada empresa
t1, t2 e t3. Usa Asterisk real, os contextos versionados e o gerador
administrativo real para os ramais seguros adicionais de t2/t3.

Cada chamada exige registro autenticado dos dois clientes, INVITE com
Digest, atendimento, ACK, mídia nos dois sentidos, BYE confirmado,
ausência de canais residuais e CDR atendido com origem, destino,
contexto, tenant, canais e duração coerentes. Os ramais estáticos de
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

O cliente negocia PCMU/8000 em `RTP/SAVP` com
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
contagens de pacotes e perfil criptográfico. Não inclui SDP, Call-ID,
credenciais, chaves, CDR completo ou arquivos de áudio.

## Limites

O marco 5 do programa só pode ser concluído após CI real bem-sucedida.
WSS/DTLS do Webphone continua pendente no marco 6; este teste usa
TLS e SDES-SRTP. Também permanecem pendentes os aceites completos de
DID, isolamento funcional cruzado, filas, URA, transferência, gravações,
restauração, carga e operação em servidor de homologação.
`operational_go_authorized` permanece `false`.

PR dependente: [#54](https://github.com/jeffaxe81/pabx-mvp/pull/54),
baseada na [#53](https://github.com/jeffaxe81/pabx-mvp/pull/53).
