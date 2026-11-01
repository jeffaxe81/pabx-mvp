# REL-03 — Reconciliação de 100 candidatos AXE PABX

**Escopo:** PABX puro; Contact Center e IA fora do lote. Este documento complementa a auditoria inicial `docs/rel03-auditoria-duplicidades.md`.

**Resultado documental:** 100/100 IDs auditados na matriz `docs/rel03-auditoria-100-candidatos.csv`.
- EXISTENTE: **6** — capacidade genérica já existente; não é entrega inédita.
- PARCIAL: **24** — existe base funcional, mas incremento específico continua por comprovar.
- SEM_EVIDENCIA_DIRETA: **70** — não é possível confirmar a capacidade pela referência selecionada; **não** significa que o código não a tenha.

**Bloqueio contra contabilização duplicada:** nenhum dos 100 candidatos tem classificação NOVA ou CONCLUÍDO nesta matriz. Para qualquer implementação, exigir inspeção da função e testes atuais, checagem de equivalência comportamental, ID do teste de regressão, PR e CI verde. Referências associadas são fontes de comparação, não provas de inexistência de código.

**Critério de aceite REL-03:** reconciliação documental 100/100, identificação explícita de possíveis duplicidades e controle para não transformar candidatos em 100 funcionalidades entregues. A análise definitiva de código dos candidatos sem evidência direta é obrigatória antes de abrir cada novo trabalho, mas não equivale ao fechamento da auditoria do inventário. Nenhuma homologação real nem liberação de produção decorre deste aceite.

**Teste:** `tests/test_rel03_roadmap_audit.py` exige 100 IDs distintos, correspondência completa com o roadmap, 3 classes conservadoras, referências não vazias e notas de julgamento, sem marcar NOVA.
