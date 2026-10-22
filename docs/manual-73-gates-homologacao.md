# Manual 73 — Matriz de homologação e critérios de GO

## Objetivo

O AXE PABX precisa distinguir **código aprovado no CI** de
**funcionalidades comprovadas com chamadas e infraestrutura reais**.
O script `scripts/homologation_gate.py` calcula o avanço e bloqueia
uma recomendação de GO enquanto existirem cenários obrigatórios não
aprovados com referências de evidência.

O script não executa chamadas, não conecta ao Asterisk, não verifica
a legitimidade das provas e não concede autorização de implantação.

## 13 cenários obrigatórios

1. Transporte SIP/TLS e certificado confiável
2. Registro SIP de dois ramais
3. Chamada interna completa
4. Áudio RTP bidirecional
5. Negociação SRTP
6. DID conhecido no tenant correto
7. DID desconhecido rejeitado
8. Isolamento entre empresas, filas e gravações
9. URA e filas
10. Transferência assistida e retorno
11. Gravações e permissões de leitura
12. Backup e restauração
13. Contingência, falha e recuperação

## Preparar o arquivo de evidências

1. Copiar `docs/modelo-homologacao-pabx.json` para uma área local
   restrita, fora do repositório.
2. Preencher `source_commit` com o SHA Git completo (40 caracteres)
   do release efetivamente instalado. O modelo vem intencionalmente
   com `null` para impedir qualquer aprovação por omissão.
3. Após cada teste real, ajustar seu `status`: `pending`,
   `passed`, `failed` ou `blocked`.
4. Para cada `passed`, informar uma referência de evidência
   verificável (por exemplo, `LAB-023` ou `CHAMADA-T1-04`).
   Evitar credenciais, dados pessoais e trechos de gravação.

## Executar

```bash
python3 scripts/homologation_gate.py --file /caminho/privado/evidencias.json

python3 scripts/homologation_gate.py \
  --file /caminho/privado/evidencias.json --format markdown
```

Retornos:

- `0`: todos os 13 cenários declarados como aprovados com evidência;
- `1`: homologação incompleta, falha ou bloqueada;
- `2`: JSON inválido, SHA ausente, cenário ou evidência inválidos.

O resultado informa quantos cenários passaram e a porcentagem
`aprovados / 13 × 100`. Mesmo em 100%, o rótulo é apenas
**APTO PARA REVISÃO DE GO**: cabe ao responsável conferir as provas,
validar o escopo, riscos residuais, backup/rollback e autorizar.

## Regras de segurança

- O arquivo de homologação não deve ser versionado com informações
  confidenciais.
- Evidências referenciadas devem ficar em repositório interno com
  controle de acesso e retenção adequada.
- Um resultado `passed` sem referência é inválido.
- Novos cenários ou remoção dos existentes exigem alteração de código
  e revisão: chaves desconhecidas são recusadas.
- A ferramenta **não afirma que realizou** testes SIP, chamadas,
  RTP, TLS, restauração ou failover.

## Testes automatizados do gate

```bash
(cd scripts && python3 -m pytest -q tests/test_homologation_gate.py)
```

A CI avalia apenas a consistência do cálculo e dos critérios de
aceite. A comprovação de telefonia real depende do laboratório.
