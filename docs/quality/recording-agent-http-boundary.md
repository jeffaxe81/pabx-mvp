# Marco 8 — Autorização HTTP de gravações por agente

A matriz em `queue-api/tests/test_multi_tenant_cross_service_http.py`
exercita a `Handler` real em loopback, com arquivos e credenciais
sintéticos para `t1`, `t2` e `t10`.

Os 18 casos adicionais verificam:

- listagem limitada ao proprietário autenticado, mesmo com `tenant`,
  `extension` e `role` adulterados na query string;
- download permitido apenas para a gravação do próprio ramal e tenant;
- negativa para arquivo de colega, arquivo sem proprietário e outro tenant;
- resposta 404 idêntica à de arquivo inexistente, sem bytes do áudio;
- revogação e expiração aplicadas na próxima listagem e download,
  sem reiniciar o servidor;
- manutenção do acesso do supervisor e de agente de outro tenant;
- `Cache-Control: no-store` nas respostas exercitadas e conteúdo/comprimento
  exatos no download autorizado.

## Reprodução em Linux

```bash
python3 -m pip install -r tests/requirements.txt
cd queue-api
python3 -m pytest -q tests/test_multi_tenant_cross_service_http.py
python3 -m pytest -q tests
```

O Linux é necessário para os controles POSIX de abertura segura usados pelo
serviço. Não substituir esses controles por mocks para obter testes verdes
no Windows.

Uma verificação local de sensibilidade substituiu apenas em memória o papel
do agente por supervisor na autorização. Os três casos de download no
próprio tenant falharam ao receber 200 em vez de 404 para arquivo de colega.
Isso comprova que a matriz detecta a remoção do controle de proprietário.
Nenhuma alteração dessa simulação é feita no código do serviço.

## Limites do aceite

Esta entrega amplia a prova HTTP de permissões existente. Não executa
Asterisk, não gera gravação por chamada, não comprova isolamento de volumes
e não integra identidade/SSO. As issues #30 e #92 permanecem abertas e o
marco 8 continua `in_progress`; a contagem de marcos concluídos não muda.
CI estática e laboratório Asterisk no SHA da PR continuam obrigatórios
antes da integração. `operational_go_authorized` permanece `false`.
