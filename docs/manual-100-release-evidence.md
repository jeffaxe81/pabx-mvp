# Manual 100 — Pacote de evidências com SHA único do release

## Objetivo

Associar três informações de homologação ao mesmo release:
o commit Git informado pelo operador, o diagnóstico somente leitura
do Asterisk (Manual 96) e os 13 cenários declarados do Manual 73.

A ferramenta `scripts/release_evidence.py` **não executa chamadas
nem verifica autenticidade externa das provas**. Ela recusa relatórios
inconsistentes e apresenta os bloqueios sem publicar a saída bruta
do CLI ou os identificadores de evidência.

## Passo 1 — Gerar a auditoria de laboratório

No repositório do release efetivamente instalado, identifique o
SHA completo de 40 caracteres. No ambiente de laboratório autorizado:

```bash
python3 scripts/asterisk_lab_audit.py \
  --runtime docker --container pabx-mvp \
  --source-commit <SHA-COMPLETO> \
  --tenant-registry /diretorio-privado/tenants.json \
  > /diretorio-privado/auditoria.json
```

**Atenção:** `--source-commit` associa o relatório ao SHA
**declarado**; o programa não comprova que o container tenha sido
construído a partir desse commit. Conferir imagens, volumes, manifesto
e commit é obrigação do operador.

## Passo 2 — Executar os 13 testes reais

Usar `docs/modelo-homologacao-pabx.json` como base em pasta
privada. Preencher o mesmo `source_commit`, o resultado e uma
referência verificável para cada cenário. Os testes de registro,
RTP, SRTP, chamadas e isolamento **não são realizados** pelo
script de auditoria.

## Passo 3 — Vincular os dois relatórios

```bash
python3 scripts/release_evidence.py \
  --sha <SHA-COMPLETO> \
  --lab-audit /diretorio-privado/auditoria.json \
  --homologation /diretorio-privado/homologacao.json \
  > /diretorio-privado/revisao-release.json
```

## Validações e códigos de saída

- `0`: todos os checks declarados estão positivos e os dois
  relatórios têm o mesmo SHA; **apto apenas para revisão humana**;
- `1`: auditoria ou homologação incompleta, bloqueada ou falha;
- `2`: documento inválido, SHA diferente, estrutura inconsistente,
  ausência ou tamanho excessivo de arquivo.

O arquivo resultante contém resumo das verificações e hashes
SHA-256 dos dois relatórios. Esses hashes permitem detectar
alterações posteriores nos arquivos, mas **não autenticam quem
produziu ou validou a evidência**.

## Testes automatizados

```bash
(cd scripts && python3 -m pytest -q \
  tests/test_release_evidence.py tests/test_asterisk_lab_audit.py)
```

## Limitações e aprovação

O resultado **não concede GO operacional** nem comprova que as
chamadas, registros ou meios de comunicação foram realmente testados:
o conteúdo de ambos os arquivos foi fornecido pelo operador. A
autenticidade, a correspondência com o deployment real, a revisão
de gravações, a restauração de backup, o desempenho e a segurança
dependem de verificações independentes. Guardar evidências em
repositório restrito, nunca em branch pública.
