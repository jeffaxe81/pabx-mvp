# Manual 70 — Segurança do verificador de autenticação AMI

## Objetivo

O verificador pós-implantação (`scripts/verify_deployment.py`) valida
a autenticação AMI do usuário de teste `queue-api`. A checagem ocorre
contra um Asterisk já instalado e **não** altera configurações, envia
comandos administrativos nem executa chamadas SIP.

Esta atualização corrige três pontos: senha digitada com eco no
terminal, resposta AMI dividida em vários pacotes TCP e aceitação de
prefixos falsos como `Response: SuccessExtra`.

## Como executar

```bash
python3 scripts/verify_deployment.py
```

A ferramenta solicita `AMI_SECRET` com `getpass`: os caracteres
digitados não são exibidos. O segredo segue diretamente para a
conexão AMI, sem ser incluído na saída ou em arquivos de evidência.
**Não coloque senhas na linha de comando, logs, screenshots ou PRs.**

## Regras da checagem

1. Recusar usuário/segredo vazios ou com caracteres CR/LF.
2. Conectar ao AMI na porta configurada, com timeout.
3. Enviar uma única ação `Login` com campos fixos.
4. Coletar fragmentos até o delimitador final `CRLF CRLF`, com
   limite de 16 KiB e número máximo de leituras.
5. Aceitar somente o primeiro campo `Response: Success` exato.
6. Tratar erro, timeout, fim de conexão ou resposta incompleta como
   falha de diagnóstico.

O script retorna status `0` quando todas as verificações
pós-implantação são aprovadas, ou `1` quando existe falha.

## Testes automatizados

```bash
(cd scripts && python3 -m pytest -q tests/test_verify_deployment_runner.py tests/test_deployment_checks.py)
```

A suíte usa sockets simulados e cobre fragmentação, resposta
incompleta, autenticação recusada, tentativa de CRLF e ocultação de
segredos. Não usa credenciais reais em GitHub Actions.

## Critérios de homologação

- Confirmar que um segredo válido é aceito e o inválido é recusado,
  em laboratório isolado.
- Confirmar que caracteres não são exibidos ao digitar o segredo.
- Registrar somente o resultado (passou/falhou), sem copiar o segredo.
- Prosseguir com o diagnóstico do Manual 69 e chamadas reais com
  TLS/SRTP, CDR e validação de isolamento de DIDs por tenant.

**Limite:** autenticação AMI bem-sucedida não garante funcionamento
de SIP, mídia, fila, telefonista WebRTC nem contingência.
