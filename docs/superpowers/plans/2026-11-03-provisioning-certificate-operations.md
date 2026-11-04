# Provisioning Certificate Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consultar validade e revogar certificados por tenant/MAC com persistência segura.

**Architecture:** CLI local sobre o cadastro v2 do servidor mTLS. Validação compartilhada, leitura por FD e escrita atômica sob lock; nenhuma nova porta ou credencial.

**Tech Stack:** Python 3.12, biblioteca padrão POSIX, pytest, OpenSSL já usado nos testes.

**Spec:** docs/superpowers/specs/2026-11-03-provisioning-certificate-operations-design.md

## Global Constraints

- PABX puro; sem Contact Center ou IA.
- Nenhum segredo, certificado ou fingerprint na saída da CLI.
- Cadastro v2, validade máxima de 30 dias, MAC/tenant exatos.
- Sem produção, publicação de serviço, mudança do RC ou falso aceite operacional.
- Merge apenas com toda CI e laboratório aprovados no SHA revisado.

## Review Focus

- t1/t10 ou MAC de outra empresa não podem ser revogados por engano.
- Revogações simultâneas não podem sobrescrever uma à outra.
- Symlinks, arquivos não regulares e permissões públicas devem falhar fechados.
- Falha de escrita não pode truncar cadastro ou vazar dados no erro.
- Relógio inválido ou limite de validade não pode gerar estado ativo incorreto.

### Task 1: Validação compartilhada e leitura segura

**Files:** `provisioning/mtls_server.py`, `tests/test_provisioning_mtls.py`.

**Interfaces:** `validate_policy(registry, devices) -> dict`; `load_policy` mantém contrato.

- [ ] Reproduzir troca de caminho entre stat e abertura e entrada de schema inválido.
- [ ] Verificar RED, extrair validação e ancorar leitura em FD com O_NOFOLLOW e limite.
- [ ] Executar testes mTLS existentes e novos; verificar GREEN.

### Task 2: Inventário e revogação local

**Files:** criar `provisioning/certificates.py`, `tests/test_provisioning_certificates.py`; atualizar manual mTLS.

**Interfaces:** `list_certificates(registry_path, devices_path, tenant=None, *, now=None) -> list`; `revoke_certificate(registry_path, devices_path, tenant, mac) -> dict`; `main(argv=None) -> int`.

- [ ] Escrever e executar RED para inventário, revogação exata e CLI sem vazamento.
- [ ] Implementar estados, validação, lock POSIX e publicação atômica 0600.
- [ ] Cobrir concorrência real, falha de replace, links/permissões e idempotência.
- [ ] Usar CLI na prova mTLS real com servidor ativo: 200 antes, 404 depois, outro tenant 200.
- [ ] Executar oito suítes Python isoladas, testes Node e CI/laboratório da PR.
- [ ] Documentar comandos, limites e evidências; revisar diff e integrar somente com CI verde.
