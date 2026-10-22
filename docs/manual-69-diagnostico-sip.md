# Manual 69 — Diagnóstico somente leitura de SIP/Asterisk

## Objetivo

Antes de realizar os testes de registro, ligações e qualidade de áudio,
é útil comprovar que a instância de homologação carrega os recursos
esperados. O `scripts/sip_preflight.py` executa exclusivamente consultas
do **CLI Asterisk** e apresenta um relatório JSON resumido.

Ele **não** envia INVITE/REGISTER, não usa AMI nem credenciais, não
executa `reload`, não altera banco, arquivos, filas ou canais e não
coloca chamadas na rede. Tampouco faz teste de RTP, SRTP ou mídia
bidirecional. O CLI pode retornar informações operacionais sensíveis;
por isso a ferramenta não grava nem imprime a saída bruta.

## Execução no servidor de homologação

A partir da raiz do repositório, onde o Asterisk já está instalado:

```bash
# Asterisk no contêiner deste projeto
python3 scripts/sip_preflight.py --runtime docker --container pabx-mvp

# Quando o Asterisk roda diretamente no host Linux
python3 scripts/sip_preflight.py --runtime local

# Para outro conjunto de ramais, repita a opção:
python3 scripts/sip_preflight.py --runtime docker \
  --expect-endpoint t1-1001 --expect-endpoint t2-1001
```

O script usa `docker exec` ou `asterisk -rx` sem shell e com
**comandos fixos**. Requer permissão para o Docker ou para o CLI do
Asterisk. Não execute com privilégios elevados se não forem necessários.

## Checagens executadas

| Comando consultado | O que informa |
|---|---|
| `core show version` | Instância Asterisk responde ao CLI |
| `pjsip show transports` | Transportes TLS e WSS cadastrados |
| `pjsip show endpoints` | Ramais esperados aparecem na configuração |
| `dialplan show from-tdm-gateway` | Existe consulta DID → tenant e rejeição de DID desconhecido |
| `core show channels count` | Contagem informativa de canais ativos |

Uma resposta bem-sucedida **não comprova**: certificado TLS confiável,
registro de ramal, codec, autenticação, chamada estabelecida, áudio
bidirecional, gravação, failover, operação de filas ou isolamento
dinâmico em chamada real.

## Resultado e evidências

O comando retorna status `0` se todas as checagens forem aprovadas,
`1` se algum item não for identificado, e `2` quando os argumentos
forem inválidos. A saída JSON inclui os resultados individuais,
quantidade observada de canais, data UTC e marcadores explícitos
`call_tested=false` e `rtp_tested=false`.

Para guardar evidência local sem expor segredos:

```bash
umask 077
python3 scripts/sip_preflight.py > sip-preflight-evidencia.json
```

Atenção: direcione para um caminho privado e não versionado no Git.

## Etapa complementar obrigatória: chamada real

Com duas pontas SIP no laboratório, em ambiente autorizado:

1. Registrar dois ramais do mesmo tenant usando TLS e SRTP; verificar
   criptografia e negociar codecs.
2. Discar `600` e verificar áudio de eco; realizar uma chamada
   entre ramais com áudio bidirecional.
3. Testar DID cadastrado de t1 e t2, DID de tenant novo e DID
   desconhecido (deve rejeitar, não cair em t1).
4. Conferir fila/URA, transferência, gravação e relatórios; validar
   que dados/chamadas de um tenant não aparecem no outro.
5. Capturar evidências de CLI, chamadas e RTCP, **sem credenciais**.

## Testes automatizados da ferramenta

```bash
(cd scripts && python3 -m pytest -q tests/test_sip_preflight.py)
```

Esses testes são mockados e fazem parte do CI Python; nenhum servidor
de telefonia externo é contatado pela suíte automatizada.
