# Manual 66 — CI e validação das entregas AXE PABX

## Objetivo

A esteira GitHub Actions em `.github/workflows/quality-gates.yml` executa
os testes já existentes em oito conjuntos independentes: configurações e
interfaces, admin-api, queue-api, ai-worker, AGI, scripts do Asterisk,
backup e scripts operacionais.

O fluxo roda em `pull_request`, em `push` na branch `main` e manualmente
(`workflow_dispatch`). Os jobs são independentes: falhas em uma suíte não
impedem que as demais apresentem seu diagnóstico.

A execução usa Python 3.12, `pytest` e `PyYAML`. Não inicia Docker,
Asterisk, Ollama, rede SIP, chamadas nem alterações em ambiente produtivo.

## Execução local

Na raiz do repositório, instale as dependências de teste:

```bash
python3 -m pip install -r tests/requirements.txt
python3 -m pytest -q tests
(cd admin-api && python3 -m pytest -q tests)
(cd queue-api && python3 -m pytest -q tests)
(cd ai-worker && python3 -m pytest -q tests)
(cd asterisk/agi && python3 -m pytest -q tests)
(cd asterisk/scripts && python3 -m pytest -q tests)
(cd backup && python3 -m pytest -q tests)
(cd scripts && python3 -m pytest -q tests)
```

## Critérios de promoção de PR

1. Todos os oito jobs de testes estáticos devem estar verdes.
2. Falhas devem ser corrigidas no próprio PR antes do merge.
3. Revisar segurança, escopo e compatibilidade do diff.
4. Para alterações que afetem PJSIP/AMI/URA/WebRTC/roteamento, também
   homologar registro SIP, chamadas internas/externas, mídia,
   criptografia, isolamento entre empresas e recuperação após falha,
   em ambiente de testes adequado.
5. Registrar evidências da homologação e só então autorizar implantação.

**Importante:** CI verde atesta somente estes testes automatizados.
Não representa a comprovação de chamadas reais, disponibilidade,
segurança de produção nem entrega homologada.
