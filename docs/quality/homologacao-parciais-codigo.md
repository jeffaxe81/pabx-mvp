# AXE PABX — homologação técnica limitada das frentes parciais

**Modalidade solicitada:** revisão de código e testes automatizados, **sem ensaio na instalação local/real e sem liberação operacional**.

**Classificação:** `CODE_ONLY_ACCEPTED_WITH_LIMITATIONS` para o **escopo de código identificado**, não para a funcionalidade inteira. A CI da PR e seus testes existentes precisam aprovar o código antes de integrar à `main`. As referências de testes não afirmam sua execução pelo verificador.

| Área parcial | O que existe e é elegível para aceite técnico de código | O que continua pendente |
| --- | --- | --- |
| Autenticação | Sessões locais, usuários, papéis admin/supervisor e revogação de token de sessão do painel | SSO unificado, autenticação e revogação entre painel e API de filas |
| Gravações | Propostas conservadoras de proveniência CDR e catálogo por manifesto revisado | Classificação automática confiável sem etapa manual e evidência de acesso segregado na instalação |
| Provisionamento | Gerador de configuração e template Yealink; teste unitário com arquivo temporário | Outros fabricantes, descoberta/provisionamento físico e transporte seguro validado |
| IA/TTS | Pipeline de transcrição/resumo/sentimento e validador TTS; flag `AI_FEATURES_ENABLED=false` por padrão | Execução com modelos reais, medição de latência/capacidade e análise da licença XTTS opcional |

**Fora desta homologação, por não estarem plenamente implementados:** failover geográfico/automático e instalador local inteiramente automatizado. Eles não devem ser marcados como aceitos.

## Critério de aceite e registro

- O cadastro está em `docs/quality/homologacao-parciais-codigo.json`; cada item possui evidências de símbolos reais no código, arquivo(s) de teste existentes e lacunas remanescentes.
- O comando `python3 scripts/partial_code_review.py` valida a estrutura, a existência de símbolos no AST e as referências dos testes, sem acessar infraestrutura ou serviço de produção.
- Os testes unitários e de CI da PR permanecem obrigatórios. Se um check falhar, corrigir antes do merge.
- Os estados globais de `docs/plano-16-semanas-pabx.json` e `docs/quality/provas-operacionais-diferidas.json` ficam **inalterados**. Não converter status `DEFERRED_NOT_EXECUTED` em `passed` sem executar as provas.
- **100% da revisão dos quatro recortes** significa apenas que os quatro registros estáticos foram auditados; não representa 100% das funcionalidades desenvolvidas ou homologadas.
- A homologação operacional e o GO permanecem pendentes. A autorização de uso definitivo em produção é uma decisão distinta.

Este documento não comprova que o Windows/WSL2 já foi instalado, que há telefone real registrado ou que houve chamadas reais. Referências: issues [#30](https://github.com/jeffaxe81/pabx-mvp/issues/30), [#61](https://github.com/jeffaxe81/pabx-mvp/issues/61) e [#173](https://github.com/jeffaxe81/pabx-mvp/issues/173).
