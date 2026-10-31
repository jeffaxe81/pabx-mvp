# 30 atividades independentes — fechamento AXE PABX

Estado: **planejadas**, sem alegação de execução ou homologação. Dependências e evidências deverão ser registradas por atividade.

Escopo: PABX puro, implantação local; Contact Center e IA fora do escopo.

## Discagem e políticas

- [ ] AT-01 — Inventariar prefixos de saída. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-02 — Testar destino nacional permitido. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-03 — Testar internacional bloqueado. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-04 — Testar internacional permitido. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-05 — Testar destino vazio e não numérico. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-06 — Verificar rota alternativa sem bypass. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.

## Troncos SIP

- [ ] AT-07 — Validar registro de tronco SIP. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-08 — Validar autenticação de tronco. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-09 — Testar falha de tronco primário. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-10 — Testar recuperação do tronco primário. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-11 — Validar codec negociado. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-12 — Validar CDR de chamadas externas. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.

## Multiempresa

- [ ] AT-13 — Validar contexto SIP por tenant. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-14 — Negar chamada cruzada entre tenants. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-15 — Validar isolamento de ramais. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-16 — Validar isolamento de DIDs. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-17 — Validar política de tenant dinâmico. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-18 — Testar variáveis de tenant ausentes. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.

## Operação PABX

- [ ] AT-19 — Validar criação de ramal. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-20 — Validar alteração de ramal. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-21 — Validar exclusão de ramal. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-22 — Validar transferência assistida. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-23 — Validar caixa postal por empresa. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-24 — Validar provisionamento de dispositivo. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.

## Segurança e entrega

- [ ] AT-25 — Revisar permissões da API administrativa. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-26 — Revisar segredos e configurações. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-27 — Validar backup restaurável. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-28 — Documentar rollback reproduzível. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-29 — Concluir jobs CI estática e Asterisk. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.
- [ ] AT-30 — Consolidar evidências e critérios da release. **Aceite:** teste reproduzível, resultado esperado/obtido, referência do commit e evidência CI ou laboratório.

**Total: 30 atividades planejadas; 0 concluídas nesta lista.**

As atividades de teste podem alimentar a campanha de 500 casos sem serem contabilizadas duas vezes.
