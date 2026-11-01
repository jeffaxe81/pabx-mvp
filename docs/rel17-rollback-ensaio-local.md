# REL-17 — Ensaio local de rollback

## Escopo e proteção

O rollback de arquivos usa `backup/restore.sh` e requer um arquivo previamente aprovado por `backup/validate_archive.py`. **Nunca execute o script no host de produção para fins de teste.** O teste automatizado `tests/test_rel17_restore_sandbox.py` cria um diretório temporário, gera um snapshot da versão anterior, modifica arquivos simulados e executa o script real nesse diretório, confirmando o retorno ao conteúdo anterior.

## Procedimento operacional local

1. Registrar a versão, o hash do backup e o estado atual dos serviços.
2. Interromper o ambiente local: `docker compose down`.
3. Verificar o arquivo: `python3 backup/validate_archive.py backups/ARQUIVO.tar.gz`.
4. Executar `sh backup/restore.sh backups/ARQUIVO.tar.gz` na raiz do projeto, confirmar `sim` apenas depois de validar o destino.
5. **Restaurar separadamente os volumes `admin_data` e `queue_api_data`**, seguindo os comandos apresentados pelo script. Não reiniciar o PABX antes de restaurá-los.
6. Validar ramais, tenants, configurações, credenciais, registros SIP, roteamento interno e CDR em laboratório; somente então executar `docker compose up -d`.
7. Manter o backup original e os logs de evidência. Se a validação falhar, manter o serviço parado e escalar a recuperação.

## Critério e limitações

O teste automatizado comprova a restauração e a recusa de confirmação dos **arquivos** em sandbox. Ele **não comprova** restauração real dos volumes Docker, retorno de chamadas SIP nem integridade de banco em operação. Essas etapas exigem ensaio separado com dados não produtivos antes de declarar rollback integral homologado.
