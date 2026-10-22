# Manual 77 — Bloqueio de GO com arquivos de configuração ausentes

## Problema identificado

O script `scripts/verify_deployment.py` verificava os placeholders
de senha apenas nos arquivos que existiam. Se `docker-compose.yml`,
`asterisk/manager.conf` ou `asterisk/pjsip.conf` estivesse ausente,
ele simplesmente ignorava o arquivo. Até mesmo uma relação sem arquivos
poderia produzir um resultado positivo para a checagem de segredos.

Esse comportamento criava uma falsa indicação de prontidão.

## Correção implementada

A checagem de segredos agora **falha de forma segura** quando:

- Qualquer arquivo obrigatório não existe ou não é um arquivo regular.
- O arquivo existe mas está vazio ou contém apenas espaços.
- O arquivo não pode ser lido ou tem codificação UTF-8 inválida.
- Não existe qualquer arquivo definido como obrigatório.
- Há um ou mais placeholders `troque_esta_senha_*` pendentes.

O relatório imprime somente caminhos dos arquivos indisponíveis e
**nomes de placeholders**, nunca as senhas reais. A verificação AMI
permanece com entrada oculta, e as checagens HTTP continuam
independentes. Código de saída `1` significa bloqueio operacional.

## Execução

```bash
python3 scripts/verify_deployment.py
```

O verificador deve ser executado no diretório de instalação cuja
configuração corresponda aos serviços em execução. Se os arquivos
foram movidos para um gerenciador de segredos, adapte o procedimento
de implantação para auditar a configuração final efetivamente
carregada — não trate arquivos locais ausentes como aprovação.

## Testes automatizados

```bash
(cd scripts && python3 -m pytest -q tests/test_verify_deployment_runner.py)
```

Os testes usam arquivos temporários e redes simuladas para verificar
ausência, conteúdo vazio, erros de leitura/codificação, configurações
corretas e ausência de exposição de credenciais.

## Limitações

A ausência de placeholders **não prova** a robustez das senhas nem
a correspondência entre Asterisk, AMI e Docker. Além disso,
`verify_deployment.py` não valida chamadas SIP/RTP, TLS/SRTP,
failover ou isolamento entre tenants. A homologação de campo deve
seguir o Manual 73, com evidências independentes.
