# Homologação parcial — PINs efêmeros de voicemail (t1/t2/t3)

## O que esta frente comprova
- O preparo do laboratório Asterisk produz um arquivo estático e um dinâmico com nove caixas postais esperadas.
- Cada mailbox usa PIN numérico individual de oito dígitos, sem padrão trivial ou repetição cruzada.
- Nome da mailbox, contexto e prefixo de empresa são congruentes (comparação exata, inclusive t1 versus t10).
- Qualquer arquivo malformado, PIN insuficiente, caixa faltante ou cruzamento impede iniciar o Asterisk descartável.
- O resultado de validação só informa contagens; nenhum PIN é divulgado.

Execução no conjunto estático:
```bash
python3 -m pytest -q scripts/tests/test_voicemail_pin_bootstrap_lab.py
```

A verificação do preparo do laboratório é invocada antes de todos os modos
de `lab/asterisk_lab.py`, incluindo `--calls --voicemail`. Não toca ambientes
instalados nem usa senhas de clientes. O SHA e os relatórios de CI precisam
passar integralmente antes do merge.

## Limites
A checagem é apenas de **configuração efetiva no staging**, e não autenticação
interativa de voicemail. Ainda faltam testar PIN correto e incorreto por DTMF,
tentativas sucessivas/lockout, leitura de mensagens e isolamento de volumes
no Asterisk real; provas integradas HTTP/Asterisk e homologação do ambiente-alvo
também são obrigatórias. Não marcar Marco 8 como concluído; GO permanece bloqueado.

Referências: issue #88; PRs #89, #90, #91 e #94.
