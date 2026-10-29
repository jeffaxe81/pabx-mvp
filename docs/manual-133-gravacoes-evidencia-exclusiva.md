# Manual 133 — Evidência CDR de gravação exclusiva por empresa

## Objetivo

Evitar que um arquivo de áudio receba autorização por `tenant` a
partir de evidência de origem ambígua. As alterações são limitadas ao
processo de reconciliação e leitura de catálogos; não autorizam acesso
a gravações sem credencial válida.

## Quatro pontos de controle

1. **CDR de origem**: `load_raw_cdr()` recusa eventos JSONL com
   `AccountCode` repetido, campos duplicados e constantes JSON
   `NaN/Infinity`. Nenhuma proposta é gerada a partir de entrada
   ambígua.
2. **Manifesto administrativo**: `load_manifest()` recusa a mesma
   ambiguidade mesmo quando o JSON malformado aparenta ter sido
   normalizado por um parser permissivo.
3. **Lotes sucessivos**: `preview_batch()` confronta cada nova
   referência `source_ref` com todas as referências presentes no
   catálogo, bloqueando uso da mesma evidência para `t1`, `t2`
   e `t10` em importações distintas.
4. **Leitura da API**: `load_recording_policy()` valida a exclusividade
   por `tenant` de cada `source_ref`. Políticas legadas ambíguas
   retornam inválidas e a camada HTTP recusa autenticação.

Uma prova pode referenciar mais de um arquivo **do mesmo tenant**,
quando houver múltiplas pernas legítimas, sem rejeição automática.

## Testes e gate

```bash
cd queue-api
python3 -m pytest -q \
  tests/test_recording_cdr_candidates.py \
  tests/test_recording_catalog.py \
  tests/test_recording_access.py
```

CI estática e laboratório Asterisk real devem passar completamente
no mesmo SHA antes de integrar na `main`.

## Restrições

Esta entrega **não prova** geração de gravação real no Asterisk,
isolamento físico do volume, autenticação SSO, reprodutor HTTP
com arquivo real nem autorização de produção. O marco 8 permanece
`in_progress`, e a issue #30 continua aberta até essas provas.
