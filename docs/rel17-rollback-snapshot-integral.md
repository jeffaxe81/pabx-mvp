# REL-17 — Rollback integral isolado (arquivos e dados de volumes)

O comando `python3 backup/restore_sandbox.py <backup.tar.gz> --sandbox-root <diretório>`
usa `validate_archive.py` e **exige** o arquivo `.axe-pabx-sandbox`
no diretório de destino. Executa rollback de **7 árvores completas**
(`asterisk`, `admin`, `webphone`, `provisioning`, `recordings`,
`admin_data`, `queue_api_data`) e **2 arquivos** de configuração.
Todas as entradas são recuperadas em diretório temporário no mesmo filesystem,
validadas e então renomeadas com compensação em caso de falha parcial.
A substituição de árvores elimina arquivos órfãos da versão posterior.
Não usa `docker.sock`, não conecta à telefonia e não grava dados do ambiente
operacional. A ausência do marcador **bloqueia** execução.

**Provas automatizadas:** `tests/test_rel17_full_snapshot_sandbox.py`
valida a volta da versão anterior para todos os componentes,
o bloqueio de backup incompleto antes de escrita e a recusa de destino sem
marcador. A PR #330 valida também a execução de `backup/restore.sh` sobre
arquivos simulados e a recusa sem confirmação.

**Limites:** o ensaio de sandbox **não** é restauração de volumes
Docker em funcionamento, teste de consistência de banco,
homologação de chamada SIP nem recuperação de host real.
No host real, continua obrigatório interromper serviços, validar o backup,
executar `backup/restore.sh`, restaurar volumes manualmente segundo manual 28,
validar configurações, chamadas e dados e só então reiniciar.
**Produção NO-GO até homologação operacional.**
