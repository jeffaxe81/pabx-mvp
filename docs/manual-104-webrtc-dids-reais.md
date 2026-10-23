# Manual 104 — Duas semanas de homologação: WebRTC e números de entrada

## Escopo desta rodada

O usuário limitou esta rodada aos marcos 6 e 7 do programa de 16 semanas,
com parada ao concluir ambos. O marco 8 não faz parte desta entrega.
O [Manual 103](manual-103-webrtc-real.md) registra a entrega original
do Webphone pela PR #56; este manual reúne o encerramento da rodada e
os aceites adicionais de números de entrada da PR #57.

O laboratório continua usando Asterisk 22.11.0 com imagem fixada por
digest, certificado e credenciais descartáveis, configurações extraídas
do commit Git e remoção do container por ID e token de propriedade.
Os relatórios nunca autorizam produção.

## Marco 6 — Webphone com WSS e DTLS-SRTP

O navegador Chromium opera a interface real, com a biblioteca JsSIP
3.10.1 distribuída localmente e sua integridade verificada. São seis
chamadas, nos dois sentidos em t1/t2/t3. Registro, WebSocket, SIP, ICE,
DTLS e SRTP são reais; apenas a entrada do microfone usa tons sintéticos.

O aceite exige DTLS conectado, fingerprints correlacionados ao
transporte, perfil SRTP, pacotes enviados e recebidos e reprodução do
tom remoto distinto na saída de áudio da interface. Também exige
desligamento, CDR coerente, desregistro e ausência de contatos/canais
residuais. Verifica CA/hostname do WSS e a rejeição de uma CA não
confiável. O perfil temporário do navegador aceita somente o pin SPKI
do certificado efêmero do laboratório.

```bash
npm ci --ignore-scripts --no-audit --no-fund
python3 -m pip install -r lab/requirements.txt
python3 -m lab.asterisk_lab --calls --webrtc --report /diretorio/webrtc.json
```

O modo exige **138 verificações**. A [prova inicial do navegador](https://github.com/jeffaxe81/pabx-mvp/actions/runs/39989528646/job/120537830105)
passou em **138/138**; nessa execução o job independente dos DIDs ainda
reproduzia a falha descrita abaixo. A execução final citada ao fim deste
manual aprovou todos os jobs após as correções.

## Marco 7 — Encaminhamento e rejeição dos DIDs

O modo `--dids` requer `--calls`. Acrescenta um tronco SIP/TLS autenticado
em loopback e exercita o contexto real `from-tdm-gateway`, sem substituir
suas rotas. O tronco não usa identificação por IP e existe somente na
cópia privada do laboratório.

| Cenário | Resultado exigido |
| --- | --- |
| DID estático de t1 | Atendimento no 1001 de t1, SRTP e CDR novo coerente |
| DID estático de t2 | Atendimento no 1001 de t2, SRTP e CDR novo coerente |
| DID dinâmico de t3 | AstDB resolve t3; regra VIP real encaminha ao seu 1001 |
| DID desconhecido | SIP 403, nenhum ramal tocando, CDR novo sem atendimento |
| Cadastro removido | SIP 403 após remover o mapeamento usado na chamada anterior |
| Empresa inexistente | SIP 403 antes de atender na URA |

Para t3, o cadastro VIP usa um chamador sintético fixo e evita depender
do horário comercial ou de prompts de voz. Não substitui a homologação
completa das opções da URA.

```bash
python3 -m pip install -r lab/requirements.txt
python3 -m lab.asterisk_lab --calls --dids --report /diretorio/dids.json
```

O modo exige **106 verificações**, incluindo as 70 já exigidas para
chamadas internas seguras. Os ramais 1001 das outras empresas permanecem
registrados e observados durante cada tentativa. Um INVITE inesperado,
EOF, erro de leitura ou observador indisponível reprova o cenário.

O CDR positivo precisa ser novo e conter, na mesma linha, empresa,
origem, destino, contexto, canais, atendimento, duração e identificador
coerentes. A rejeição exige resposta SIP final correlacionada e bem
formada, além de CDR novo do tronco, sem atendimento, sem canal de destino
e sem tempo faturado. Arquivo vazio ou CDR atrasado não comprova rejeição.

## Falhas encontradas e corrigidas

1. Um DID cadastrado para t99 inexistente entrava na URA e era atendido.
   A [execução de reprodução](https://github.com/jeffaxe81/pabx-mvp/actions/runs/39989528646)
   passou em 104/106; falharam somente rejeição e ausência de atendimento
   do cadastro órfão. Agora `DIALPLAN_EXISTS` verifica a entrada interna
   da empresa antes de entrar na URA. Falha segue para `Hangup(21)`.
2. A revisão independente mostrou que uma resposta negativa sem tag
   `To` podia ser aceita. A validação central de respostas finais agora
   recusa a mensagem; regressões com sockets reais cobrem 401 e 403.
3. A revisão também mostrou que a ausência temporária do CDR podia
   produzir um falso positivo. Agora o aceite aguarda um registro novo
   coerente, até o prazo existente; testes cobrem ausência, atraso,
   reutilização de registro e atendimento indevido.
4. Uma repetição final deixou a negociação ICE/DTLS da última chamada
   pendente ao fim dos seis segundos de observação. A espera agora
   acompanha a condição real de mídia, com limite monotônico de 20 s
   por chamada e orçamento de 240 s para o processo do navegador. Todas
   as exigências de certificado, mídia e áudio remoto foram preservadas.

Os dois achados da revisão tiveram testes RED → GREEN. Não houve achado
menor adiado. Os limites de operadora externa, hardware, produção e
isolamento completo continuam fora destes dois marcos.

## Privacidade e limites

O JSON preserva SHA, versões, estados, booleanos e contagens. Não exporta
credenciais, chaves, SDP, Call-ID, CDR bruto, console bruto ou áudio.
As chamadas usam mídia sintética em loopback; não medem qualidade
acústica de headset, NAT externo, disponibilidade de operadora ou carga.

`live_tenant_isolation_tested` e `operational_go_authorized` permanecem
`false`. Filas, voicemail, gravações e autorização cruzada ainda exigem
os aceites próprios do marco 8 e dos marcos posteriores.

PR desta rodada: [#57](https://github.com/jeffaxe81/pabx-mvp/pull/57),
dependente da [#56](https://github.com/jeffaxe81/pabx-mvp/pull/56).

## Evidência final

O commit de implementação `be1878f481e81c7a7c8ca16d7254094e160d493d`
foi aprovado na [CI estática 40007838447](https://github.com/jeffaxe81/pabx-mvp/actions/runs/40007838447)
(oito jobs) e no [laboratório real 40007838427](https://github.com/jeffaxe81/pabx-mvp/actions/runs/40007838427)
(quatro jobs):

- Registro SIP/TLS: **22/22**.
- Chamadas internas com CDR e SRTP: **70/70**.
- Navegador WSS/DTLS-SRTP: **138/138**.
- Números de entrada e rejeições: **106/106**.

As contagens são por modo e compartilham verificações; não representam
336 testes independentes. Na validação local, as oito suítes passaram
em **1.387 testes Python**, e a suíte Node em **19/19**, incluindo
as verificações de certificado nativo incorporadas da PR #56.

Os marcos 6 e 7 estão concluídos: **7 de 16 marcos, 43,8%**. A execução
para neste ponto, conforme solicitado. O marco 8 permanece planejado.
