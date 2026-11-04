# Private Provisioning Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Gerar e servir `.cfg` somente em armazenamento privado do operador.

**Architecture:** Gerador Python existente publica por descritor em pasta privada, preservando conteúdo legado e atomicidade por arquivo. O leitor mTLS valida as mesmas restrições antes de responder.

**Tech Stack:** Python 3.12, POSIX/Linux, biblioteca padrão, pytest e OpenSSL já existentes.

**Spec:** docs/superpowers/specs/2026-11-03-private-provisioning-files-design.md

## Global Constraints

- PABX puro; sem Contact Center/IA e sem deploy.
- Diretório 0700 e arquivos 0600 por padrão; nenhum segredo no log.
- Links e objetos não regulares não podem ser seguidos ou alterados.
- Não excluir arquivos antigos nem modificar diretórios superiores.
- Merge somente após revisão e CI/laboratórios inteiramente verdes no HEAD.

## Review Focus

- Umask permissivo não pode expor temporários, pastas ou arquivos.
- Arquivos antigos de MACs fora do lote também precisam ficar privados.
- Renomear a pasta durante a escrita não pode redirecionar dados para um link.
- Falha antes do replace preserva conteúdo anterior; falhas no lote não equivalem a rollback global.
- GET mTLS com certificado válido não pode liberar arquivo ou pasta públicos.

### Task 1: Publicação privada por descritor

**Files:** `provisioning/generate.py`, novo `tests/test_provisioning_private_files.py`.

**Interfaces:** `_publish(staged)` mantém contrato; `_stage(devices)` gera nomes MAC canônicos.

- [ ] Testar RED para permissões, conteúdo legado, links, FIFO, troca de diretório e MAC maiúsculo.
- [ ] Implementar diretório ancorado, lock, preflight de arquivos, chmod restritivo e replace relativo.
- [ ] Verificar GREEN e regressões existentes do gerador; confirmar limpeza de temporários.

### Task 2: Leitura mTLS privada e orientação de migração

**Files:** `provisioning/mtls_server.py`, `tests/test_provisioning_mtls.py`, manual 05 e documentos de segurança.

**Interfaces:** `read_cfg(directory, mac)` mantém bytes/erro genérico no handler.

- [ ] Testar RED para arquivo/pasta públicos, hardlink e identidade local divergente.
- [ ] Validar metadados no FD e adaptar fixtures a armazenamento privado.
- [ ] Gerar os `.cfg` no teste HTTPS real e comprovar leitura, recusa de permissões abertas e revogação.
- [ ] Executar matriz de regressão, testes Node, revisão independente e correções necessárias.
- [ ] Registrar evidências, abrir PR e integrar com todos os checks aprovados.
