# Manual 107 — Gravações: isolamento por tenant e validação defensiva

## Objetivo
Impedir que um catálogo de gravações adulterado vincule um agente ou o
proprietário de uma gravação a outra empresa. Esta entrega é **parte do
marco 8** e não equivale à homologação completa de isolamento.

## Política
- Todo acesso exige um `tenant` explícito e o áudio precisa constar no
  catálogo de gravações sob **o mesmo tenant**.
- `admin` e `supervisor` não têm acesso global: seus privilégios
  permanecem limitados ao próprio tenant.
- `agent` somente consulta gravação de seu próprio ramal, com
  `owner_extension` explicitamente associado. Áudio sem proprietário
  **não** é liberado a agentes.
- Ramal de agente e `owner_extension` precisam seguir o formato
  `tN-<ramal>` e coincidir com o tenant declarado: `t1` nunca é `t10`.
- Uma política que contenha identidade conflitante é rejeitada por
  `load_recording_policy`, inclusive quando tenta associar `extension`
  a papéis distintos de agente.
- `can_read_recording` revalida o vínculo mesmo se receber estrutura
  adulterada diretamente em memória.
- Arquivos de política que sejam **links simbólicos** são recusados.
  Nenhum token ou senha deve aparecer nos logs do teste.

## Regressão automatizada
Na raiz do repositório:

```bash
cd queue-api
python3 -m pytest -q tests/test_recording_tenant_boundary.py tests/test_recording_access.py tests/test_recording_credentials.py
```

Os cenários negativos incluem t1/t2/t10, metadados de proprietário
cruzados, token atribuído a ramal estrangeiro, extensão inválida, política
via symlink e gravação sem dono. Um cenário positivo mantém acesso do
agente autorizado; supervisor do mesmo tenant preserva acesso a gravação
sem owner.

## Limitações e evidências de aceitação
Esta alteração valida **políticas, arquivos de teste e autorização local**;
não comprova acesso HTTP autenticado em rede, arquivos reais
do Asterisk, manipulação de volumes, sessão/SSO, ou negação de
acesso por chamadas SIP. As negativas em ambiente-alvo estão documentadas
como pendentes em `docs/quality/real-environment-pending-2026-10-23.json`
na `main`. Elas são exigências de **GO operacional**, não motivo para
suspender novas alterações de código.

Antes de considerar o marco 8 concluído, reproduzir os negativos com
duas ou mais empresas em ambiente de teste Asterisk e API, coletar
resultados HTTP/SIP e trilhas sanitizadas, verificar isolamento do volume
e seguir os critérios de release. Nenhum GO de produção é declarado.
