# Manual 103 — Webphone real com WSS e DTLS-SRTP

## Escopo

Estende os [registros reais](manual-101-laboratorio-sip-real.md) e as
[chamadas SIP/TLS com SDES](manual-102-chamadas-srtp-reais.md) para operar
as telas reais do Webphone em Chromium contra Asterisk 22.11.0.

O teste registra dois operadores em cada empresa t1, t2 e t3 e realiza
1010 → 1011 e 1011 → 1010. Playwright preenche os campos e usa os botões
de conectar, discar, atender, desligar e desconectar. WebSocket, SIP,
RTCPeerConnection, ICE, DTLS, SRTP e estatísticas são reais. Somente a
entrada de microfone fornece tons sintéticos distintos (440 e 880 Hz).

Cada chamada exige transporte DTLS conectado, par ICE selecionado,
fingerprints SHA-256, cifra SRTP reconhecida, pelo menos 25 pacotes RTP
enviados e recebidos e o tom da outra ponta. A faixa recebida deve ser a
mesma ligada ao elemento de áudio da interface, em reprodução, sem mute
e com volume positivo. A análise de frequência usa essa faixa ligada
à interface. Nenhum microfone físico ou conteúdo real é capturado.

Quando o Chromium omite o objeto de certificado remoto de `getStats`,
o teste obtém o DER do mesmo transporte de áudio por
`RTCDtlsTransport.getRemoteCertificates()`, calcula SHA-256 com Web Crypto
e exige correspondência exata com o fingerprint SHA-256 do SDP de áudio.
Certificado ausente sem essa prova nativa, hash divergente ou estatística
presente com SHA-1 continuam reprovados. DER e fingerprint ficam somente
na memória, sem inclusão no relatório. Referência:
[API nativa DTLS](https://w3c.github.io/webrtc-pc/#dom-rtcdtlstransport-getremotecertificates).

Após pelo menos dois segundos de chamada atendida, o teste desliga e
verifica CDR com empresa, contexto, origem, destino, canais e duração
coerentes. Exige também desregistro confirmado, ausência de contatos e
canais residuais, fechamento do navegador/servidor e remoção do container.

## Execução

Requer Linux com Docker, OpenSSL, Python 3.12, Node e Chromium. Use um
checkout limpo e as portas locais livres descritas no Manual 101.

```bash
python3 -m pip install -r lab/requirements.txt
npm ci --ignore-scripts --no-audit --no-fund
npm run check:sip
npx playwright install --with-deps chromium
python3 -m lab.asterisk_lab --calls --webrtc --report /diretorio/webrtc.json
```

Para um Chrome/Chromium já instalado, `PABX_BROWSER_EXECUTABLE` pode
indicar o executável. O workflow `asterisk-lab.yml` prefere o navegador
do runner. `--webrtc` exige `--calls` e acrescenta 68 aceites aos 70 do
laboratório anterior: **138 verificações obrigatórias**. Falha, ausência
de campo ou relatório inválido resulta em reprovação e exit code 1.

## Cliente SIP e atualização do aplicativo

O carregamento anterior de JsSIP dependia de uma URL que respondia HTTP
404. A página agora usa `vendor/jssip-3.10.1.min.js`, com versão fixada,
licença MIT preservada e Subresource Integrity SHA-384. `package-lock.json`
fixa as dependências; esbuild 0.25.11 reproduz o bundle sem execução de
scripts de instalação.

```bash
npm run build:sip
npm run check:sip
npm run test:node
```

O cache do service worker passou de `telefonista-shell-v2` para `v3`,
incluindo o cliente SIP e o módulo de áudio. A regressão executa o worker
com um cache antigo, instala/ativa a nova versão e verifica os ativos
sem rede. Os testes de chamadas bloqueiam service workers para ler os
ativos exportados do SHA; não constituem teste de instalação PWA em
navegador real.

O áudio é acompanhado desde a criação do peer connection, com recuperação
de receivers já existentes. Isso cobre o evento `track` anterior à
confirmação SIP, chamadas recebidas, troca de linha e retorno de consulta.

JsSIP 3.10.1 não expõe a API `Subscriber` usada pelo painel antigo de BLF.
A interface informa que a presença SIP está indisponível, sem interromper
o registro, o áudio ou os demais painéis. Este incremento não homologa BLF.

## TLS, privacidade e isolamento

Uma conexão independente valida CA e hostname do WSS, a negociação TLS
e o upgrade WebSocket com subprotocolo SIP. Um controle negativo exige
rejeição do certificado quando a CA efêmera não é confiável.

O perfil Chromium recebe apenas a exceção SPKI da chave efêmera esperada;
`ignoreHTTPSErrors` permanece desativado. As páginas e ativos são servidos
por HTTPS privado, e requisições externas são bloqueadas. ICE usa apenas
o ambiente local, sem STUN/TURN externo.

O laboratório concede a permissão de microfone somente à origem HTTPS
privada, como faria o operador ao usar `getUserMedia`. A entrada permanece
sintética. Omitir essa permissão mudava a coleta ICE do Chromium: o ensaio
ficava sem par selecionado e sem DTLS. Com a permissão, as seis chamadas
passaram nas verificações de ICE, DTLS, RTP, tom remoto e áudio da interface.

Os nomes antigos de SDES e os nomes atuais de perfis DTLS-SRTP identificam
as mesmas três opções aceitas. O relatório normaliza para os nomes IANA:

| Nome antigo | Perfil no relatório |
| --- | --- |
| `AES_CM_128_HMAC_SHA1_80` | `SRTP_AES128_CM_HMAC_SHA1_80` |
| `AEAD_AES_128_GCM` | `SRTP_AEAD_AES_128_GCM` |
| `AEAD_AES_256_GCM` | `SRTP_AEAD_AES_256_GCM` |

Perfis NULL, nomes desconhecidos e ausência de cifra continuam reprovados.
Referências: [RTCTransportStats](https://www.w3.org/TR/webrtc-stats/#dom-rtctransportstats-srtpcipher),
[registro IANA](https://www.iana.org/assignments/srtp-protection) e
[implementação WebRTC](https://webrtc.googlesource.com/src/+/main/rtc_base/ssl_stream_adapter.cc).

Configurações e ativos vêm do Git. Credenciais e chave privada ficam no
staging privado e não aparecem em argumentos de linha de comando. O
relatório admite somente campos e tipos conhecidos: resultados booleanos,
versão do navegador, cifra, contadores e frequência/RMS dos tons sintéticos.
Diagnósticos de falha usam estados fixos e booleanos; não copiam strings
arbitrárias do navegador. Não há SDP, Call-ID, senha, chave, CDR bruto,
áudio, screenshot, trace ou console bruto no artefato público. O workflow
preserva apenas o JSON sanitizado por 14 dias.

No timeout, Python envia SIGTERM primeiro para permitir que o handler
Playwright encerre o grupo separado do Chromium. A espera é limitada e
tem escalada para encerramento forçado. Uma regressão com processo filho
destacado verifica que a limpeza acontece e o filho é recolhido.

## Revisão e evidência

A revisão independente identificou quatro correções necessárias: escutar
`track` antes de `confirmed`, atualizar o cache de clientes já instalados,
correlacionar o áudio da interface ao receiver atual e manter duração
suficiente para o CDR. As correções possuem regressões e mantêm os
critérios originais de aceite.

A execução inicial [39987382230](https://github.com/jeffaxe81/pabx-mvp/actions/runs/39987382230)
reprovou com 97/138 aceites e não constitui evidência de conclusão.
A execução [39988760854](https://github.com/jeffaxe81/pabx-mvp/actions/runs/39988760854)
chegou a 122/138: comprovou a mídia, mas reprovou a comparação antiga da
cifra e bloqueou as etapas posteriores de CDR e limpeza. A comparação
foi corrigida com regressões antes da nova execução.
A execução [40007398762](https://github.com/jeffaxe81/pabx-mvp/actions/runs/40007398762)
comprovou que a falha de certificado vinha de estatística remota ausente,
com DTLS, cifra e mídia ativos. A prova DER/SDP foi acrescentada com testes
de hash conhecido, fingerprint incorreto, duplicado, malformado e SHA-1.
A execução [40008037655](https://github.com/jeffaxe81/pabx-mvp/actions/runs/40008037655)
aprovou **138/138 verificações do Webphone**, além dos jobs independentes
de registro (**22/22**) e chamadas TLS/SDES (**70/70**). As seis chamadas
WebRTC tiveram mídia bidirecional, cifra aprovada, áudio ligado à interface,
CDR coerente e limpeza completa.

A [CI estática 40008037783](https://github.com/jeffaxe81/pabx-mvp/actions/runs/40008037783)
aprovou as oito suítes Python (**1.370 testes**). A
[CI de interface 40008037781](https://github.com/jeffaxe81/pabx-mvp/actions/runs/40008037781)
aprovou **19 testes Node e 24 testes Chromium**. O código validado é
`27025101bc4a39e09d9d666b6afb093aedd090f4`. O marco 6 está concluído:
**6 de 16 marcos, ou 37,5%** do programa.

O Chromium local não inicia por restrição de socket do ambiente; os testes
reais de navegador foram executados no runner de CI. A validação local
Python/Node e as evidências remotas são apresentadas separadamente.

PR dependente: [#56](https://github.com/jeffaxe81/pabx-mvp/pull/56),
baseada na [#54](https://github.com/jeffaxe81/pabx-mvp/pull/54).

## Limites

O ensaio comprova sinalização e mídia no trajeto local do laboratório.
Não mede qualidade acústica de headset, MOS, latência externa, NAT/WAN,
TURN ou interoperabilidade com operadora. Permanecem os marcos seguintes
de DID, isolamento funcional cruzado, filas, URA, transferência, gravações,
restauração, carga e operação em homologação. Não há implantação nem GO;
`operational_go_authorized` permanece `false`.
