# Manual 90 — Respostas AMI completas e fragmentação TCP

## Contexto

O cliente AMI do `admin-api` lia somente um pacote `recv(4096)`
para cada ação. TCP é um fluxo de bytes: a mensagem pode chegar
em vários pacotes, e vários eventos/respostas podem chegar juntos.
Essa implementação podia interpretar uma resposta incompleta como
falha, descartar bytes seguintes ou receber um evento no lugar da
resposta ao comando de recarga.

## Proteções implementadas

- Lê o banner completo de autenticação, mantendo bytes seguintes.
- Monta cada resposta até `CRLF CRLF`, com buffer de bytes residual.
- Atribui `ActionID` por ação e exige que a resposta corresponda.
- Ignora até 32 eventos AMI intercalados antes da resposta.
- Rejeita conexões fechadas, pacotes incompletos, respostas inesperadas
  e buffers acima de **128 KiB**, sem expor conteúdo nem segredos.
- Aguarda o marcador `--END COMMAND--` após `Response: Follows`
  quando a saída do comando chega separada do cabeçalho. Mantém
  compatibilidade com respostas de comandos em um único bloco.
- Não altera os comandos administrativos existentes ou o formato
  das respostas JSON.

## Testes

```bash
(cd admin-api && python3 -m pytest -q tests/test_ami_client_framing.py)
```

A suíte utiliza um socket simulado, fragmentando os bytes em cortes
variados. Verifica respostas múltiplas numa leitura, eventos intercalados,
`ActionID` incorreto, socket fechado, timeout, limite de bytes,
fragmentação do banner, login negado e ambos os formatos de
`Response: Follows`.

Referência técnica: [AMI Command Syntax – documentação oficial do
Asterisk](https://docs.asterisk.org/Configuration/Interfaces/Asterisk-Manager-Interface-AMI/AMI-Command-Syntax/).

## Limitações e homologação

**Os testes usam respostas simuladas.** Não comprovam compatibilidade
com a versão de Asterisk instalada nem o resultado semântico dos
comandos executados no CLI. `Response: Success` ou
`Response: Follows` é confirmação do protocolo AMI, não prova
de que o dialplan/endpoint esteja operacional.

As rotinas de `DBGetTree` ainda utilizam leitura de eventos própria;
não estão incluídas nessa modernização e precisam de auditoria
separada. A sequência de ações AMI/JSON/AstDB não é transacional:
na falha de um comando, o rollback do Manual 87 é uma tentativa
de compensação e não reverte automaticamente todos os efeitos.

Em laboratório, verificar transporte TCP AMI, credenciais com
privilégios mínimos, `pjsip show endpoints`, `dialplan show`,
registro SIP/TLS, chamadas e isolamento multiempresa, seguindo a
matriz de 13 critérios do Manual 73. Não houve deploy nesta entrega.

## Complemento — consulta de listas (Manual 91)

O cliente `DBGetTree` agora reutiliza o framing do Manual 90 para
aguardar o evento terminal da consulta e evitar esperar artificialmente
um timeout. Consulte o [Manual 91](manual-91-ami-dbgettree-eventos.md).
