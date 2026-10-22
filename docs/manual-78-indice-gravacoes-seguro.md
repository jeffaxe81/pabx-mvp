# Manual 78 — Listagem segura de gravações

## Objetivo

Impedir que aliases por links simbólicos incluídos no diretório
de gravações exponham metadados de áudios localizados fora da pasta
autorizada. O acesso direto a arquivos também deve rejeitar links
simbólicos, mesmo se apontarem para outro arquivo dentro da pasta.

## Alteração

Em `queue-api/recordings.py`:

- `list_recordings` não inclui links simbólicos na busca.
- `safe_recording_path` rejeita links simbólicos antes de resolver
  o caminho; mantém proteção contra diretórios e extensões inválidas.
- Limites de listagem menores ou iguais a zero retornam lista vazia.
- Caminho inexistente ou que não seja diretório retorna lista vazia.

A alteração mantém o formato e a ordem de resposta dos arquivos
regulares. **Não muda a configuração Asterisk, o armazenamento nem
a política de retenção das gravações.**

## Testes automatizados

```bash
(cd queue-api && python3 -m pytest -q tests/test_recordings_index_safety.py)
```

Os testes usam arquivos temporários: nenhum áudio real é exposto
ou apagado.

## Homologação e limitações

Verificar a listagem real, a reprodução e os filtros com gravações
legítimas de laboratório. Esta mudança não substitui controles de
autenticação, autorização e isolamento de tenant nos endpoints de
gravação; eles devem ser avaliados separadamente antes da exposição
externa da API.
