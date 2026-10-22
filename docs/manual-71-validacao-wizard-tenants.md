# Manual 71 — Validação defensiva de cadastro multiempresa

## Objetivo

O assistente de criação de tenants recebe dados JSON enviados pelo navegador.
Dados malformados não devem gerar erro interno e **não devem** disparar
geração de arquivos ou ações AMI. Esta entrega valida o formato antes
de alterar a configuração da plataforma.

## Regras

- O corpo deve ser um objeto JSON; identificador, DID e nome precisam ser texto.
- O identificador segue `t3`, `t4`, ..., sem caracteres de controle.
  Os tenants de exemplo `t1` e `t2` continuam reservados.
- DIDs aceitam dígitos e a formatação comum de telefone
  (espaços, `+`, `-`, `(`, `)`, `.`); após normalização devem
  conter entre 8 e 15 dígitos. Letras e demais caracteres são rejeitados,
  não eliminados silenciosamente.
- O nome deve ter entre 2 e 60 caracteres imprimíveis.
- O cadastro existente precisa ser uma lista de registros com
  `tenant_id` e `did` textuais. Registros inesperados bloqueiam
  criação/remoção, evitando operações com estado inconsistente.
- A exclusão só aceita um ID válido `t3+` existente, impedindo
  nomes de arquivo e caminhos como `../`.

O servidor retorna uma validação rejeitada em vez de executar as
operações quando a entrada está incorreta. O comportamento existente
de normalizar `T3` e DID formatado é preservado.

## Testes automatizados

```bash
(cd admin-api && python3 -m pytest -q tests/test_tenants.py)
```

Os testes verificam IDs, campos JSON de tipo errado, CR/LF,
registros de tenants malformados, DIDs com caracteres inesperados
e exclusões inválidas. Não fazem reload real do Asterisk.

## Homologação

1. Criar `t3` com DID válido em ambiente de laboratório.
2. Tentar criar tenant com `did` numérico em JSON e confirmar
   rejeição controlada, sem arquivo adicional.
3. Tentar criar tenant com DID que contenha letras; confirmar
   rejeição e ausência de mapeamento AstDB.
4. Testar remoção de ID inválido; confirmar que arquivos permanecem.
5. Com dados válidos, confirmar o cadastro no AstDB e o roteamento
   de chamada entre tenants com isolamento de chamadas e gravações.

**Limites:** a validação defensiva não substitui criptografia SIP,
política de senhas dos endpoints gerados, transações/rollback do
wizard nem a homologação com chamadas reais.