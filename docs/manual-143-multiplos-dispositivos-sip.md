# Manual 143 — Até três registros SIP por ramal dinâmico

## Escopo
Ramal criado pelo painel administrativo AXE PABX pode usar entre 1 e 3 contatos SIP simultâneos (AOR PJSIP), com limite persistido, editável e publicável. O valor padrão continua sendo **1** para preservar o legado. Essa opção não muda por si o limite dos ramais estáticos do pjsip.conf nem garante chamadas simultâneas por usuário; apenas define a quantidade máxima de registros de dispositivo.

## Uso
No painel Administração > Ramais, no cadastro ou edição, selecionar 1, 2 ou 3 dispositivos. A API administrativa aceita campo JSON `max_contacts` como número inteiro de 1 a 3; ausência significa 1.

Para aplicações via API:
- POST /api/extensions com max_contacts: 2 ou 3.
- PUT /api/extensions/{name} com max_contacts: 1 retorna ao padrão seguro e remove a configuração adicional do cadastro.
- A geração de PJSIP escreve max_contacts=1, 2 ou 3 no AOR correspondente e preserva remove_existing=yes.

## Segurança
- O limite de contatos controla dispositivos registrados, não autoriza compartilhamento de contas sem governança; os dispositivos usam a mesma credencial SIP nesse modelo.
- Acesso à API segue RBAC e isolamento por tenant já existentes; cadastro persistido malformado bloqueia publicação antes do reload.
- Valores booleanos, strings, floats, zero, negativos e valores maiores que três são rejeitados.
- O contexto permanece tN-internal e a sinalização/mídia seguem a política de segurança já aplicada no template endpoint-secure.
- O valor maior que um deve ser ativado explicitamente, pois amplia a superfície de acesso de uma mesma conta.

## Testes e limitações
- admin-api/tests/test_pabx_multidevice_contacts.py: validação, regressão do legado, persistência, atualização/reversão, limites e tenant.
- GitHub Actions quality-gates.yml e ui-regression.yml validam regressões estáticas/HTTP/UI.
- **Pendente de homologação em telefonia real:** registrar 2 e 3 dispositivos efetivos no mesmo AOR, realizar chamada recebida, desconectar um contato, testar novo registro e avaliar o comportamento de remove_existing no Asterisk 22.

Essa é uma capacidade específica de PABX puro no épico #373; não marca o total de 100 funcionalidades como concluído.