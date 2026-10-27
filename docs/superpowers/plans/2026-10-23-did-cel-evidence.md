# Evidência CEL nos aceites de DID — plano

> **For agentic workers:** Use superpowers:executing-plans. Executor nativo nesta sessão; revisão independente ao final.

**Goal:** Impedir que ausência de CDR ou evidências de chamadas diferentes aprovem um DID rejeitado.

**Architecture:** Complementar o runner da #57. CEL privado registra todas as aplicações e o ciclo completo; o avaliador correlaciona CEL/CDR e publica apenas booleanos. Nenhuma rota de produção é substituída.

**Tech Stack:** Python 3.12, Asterisk 22.11.0 fixado por digest, pytest e GitHub Actions.

**Spec:** docs/superpowers/specs/2026-10-23-did-cel-evidence-design.md.

## Global Constraints

- Sem editar a branch da #57 ou duplicar seu runner.
- CEL/CDR/SDP, áudio e identificadores brutos permanecem privados.
- Provas ausentes, ambíguas ou incompletas reprovam; mesma chamada em todos os campos.
- Configuração CEL apenas em `--dids`, diretórios privados e container descartável.
- Sem GO operacional, merge, deploy ou promoção de marcos sem execução real.

## Review Focus

- CDR vazio ou duplicado não comprova tentativa rejeitada.
- Linkedid de outra chamada e mudança de canal com mesmo uniqueid devem falhar.
- Causa ausente/duplicada ou ciclo sem CHAN_END/LINKEDID_END nunca aprova.
- Eventos de resposta, Dial/Queue, ponte, URA, voicemail e gravação invalidam a prova negativa.
- Falha de leitura/CEL desativado deve gerar resultado sanitizado e cleanup normal.

### Task 1: Avaliador privado

**Files:** lab/did_evidence.py; scripts/tests/test_did_evidence.py.

**Interfaces:** `parse_cel(raw)` retorna registros limitados ou None; `evaluate_trace(raw,tenant=None)` retorna booleanos e identificadores privados prefixados por `_`; `evaluate_cdr(raw,trace,tenant=None)` retorna somente booleanos. `new_trace(before,after)` valida o prefixo anterior e retorna apenas novos registros.

- [x] Escrever testes de caminho completo e corrupção/ausência/cruzamento; observar RED.
- [x] Implementar parsing, correlação e evidência negativa; verificar GREEN.
- [x] Publicar junto ao consumidor da tarefa 2.

### Task 2: Integrar ao runner existente

**Files:** lab/did_checks.py; lab/asterisk_lab.py; scripts/tests/test_did_cel_integration.py.

**Interfaces:** `prepare_dids` grava somente `cel.conf`/`cel_custom.conf` privados. `exercise_dids` exige `did_cel_backend` e `did_cel:<case>` nas seis situações já existentes. Diretório CEL é criado antes das chamadas.

- [x] Testar preparação privada, cursor e aceites sem CEL; observar RED.
- [x] Integrar leitura limitada, ciclo completo e CDR correlacionado no prazo do runner; verificar GREEN.
- [x] Publicar PR dependente da #57 e executar laboratório real; corrigir causas comprovadas.

### Task 3: Revisão e evidência

**Files:** docs/manual-105-cel-dids.md; docs/README.md; README.md.

- [x] Executar oito suítes Python, Node/navegador e CI real no SHA publicado.
- [x] Revisão independente com correção dos achados importantes/críticos.
- [x] Documentar evidência, falhas e limites; conferir árvore Git publicada.

## Evidência e decisões finais

- Implementação 7eb771e: 1.439 Python, 19 Node e 24 Chromium aprovados localmente.
- CI estática 40010571117: oito jobs aprovados. CI real 40010571089: quatro jobs aprovados, incluindo 113/113 DID/CEL.
- Revisão independente concluída; dois achados tratados como importantes, corrigidos com regressões RED→GREEN e suíte completa. Nenhum crítico ou menor adiado.
- Reutilizar os filtros de CDR da PR57 evita divergência; o custo dessa decisão é exigir validação da integração conjunta, comprovada na CI.
- Protótipos locais anteriores ficaram em checkpoints; a entrega complementa somente o runner da PR57. O custo é depender da integração dessa PR antes da presente.
- O programa permanece 7/16 (43,8%); sem GO operacional ou merge automático.
