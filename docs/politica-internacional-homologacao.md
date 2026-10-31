# Política de chamadas internacionais — checklist de integração

## Configuração

O dialplan estático t1/t2 chama `Gosub(politica-externa,s,1)` antes do `Dial()`; a rota alternativa t1 também valida após remover o prefixo seletor de tronco.

Ativação de bloqueio por tenant (exemplo):

```bash
asterisk -rx 'database put politica-externa-t1 internacional bloquear'
asterisk -rx 'database get politica-externa-t1 internacional'
```

Para remover o bloqueio: `asterisk -rx 'database del politica-externa-t1 internacional'`.

## Testes obrigatórios ainda não executados

- [ ] t1 internacional 00... com política bloquear -> rejeição no tronco principal.
- [ ] t1 internacional via prefixo seletor de rota alternativa -> rejeição antes de Dial.
- [ ] t1 internacional sem política -> comportamento anterior.
- [ ] t2 bloqueado independentemente de t1.
- [ ] t2 permitido independentemente de t1.
- [ ] Entrada com tenant/destino inválido -> DENY.
- [ ] Chamada nacional permitida -> não afetada pela política internacional.
- [ ] Tenant criado pelo wizard -> integração efetiva confirmada; não presumir suporte.
- [ ] Teste de sintaxe/reload Asterisk, CDR e trilha de auditoria.

## Limites conhecidos

O bloqueio reconhece destino que começa por `00` após a remoção do prefixo de acesso/seleção de tronco. Outras convenções de discagem internacional devem ser normalizadas antes da decisão.

Não habilitar a política em produção sem homologar roteamento e recuperação (rollback).
