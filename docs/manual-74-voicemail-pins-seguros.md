# Manual 74 — PINs aleatórios para correio de voz por tenant

## Problema e solução

A criação de tenants adicionais (t3+) pelo wizard ainda atribuía o PIN
**1234** às duas caixas postais das telefonistas. Um PIN comum e previsível
não deve ser usado em caixa postal com conteúdo de clientes.

Esta entrega passa a gerar **dois PINs numéricos de oito dígitos, diferentes**
por tenant, usando `secrets.randbelow` do Python. Cada PIN é gravado
no arquivo `voicemail_tenants/tN.conf` e mostrado ao administrador
**somente na resposta de criação**, junto das senhas SIP.

A interface usa `textContent` e inclui a opção de ocultar credenciais.
A API de listagem de empresas não exibe PINs. Respostas JSON têm
`Cache-Control: no-store`.

## Operação

1. Criar um novo tenant pelo assistente no painel administrativo.
2. Copiar as duas senhas SIP e os dois PINs de voicemail para um cofre
   de credenciais apropriado, usando canal de distribuição autorizado.
3. Configurar cada telefonista com sua senha SIP individual.
4. Orientar cada usuário sobre seu PIN individual e a troca de PIN
   quando a política operacional exigir.
5. Ocultar as credenciais e encerrar a sessão.

**Atenção:** esses dados só aparecem na criação. Caso não tenham sido
guardados, deverá ser seguido um processo administrativo de rotação
controlada — não existe recuperação pelo endpoint de listagem.

## Testes automatizados

```bash
(cd admin-api && python3 -m pytest -q tests/test_tenants.py tests/test_server_security.py)
python3 -m pytest -q tests/test_admin_html.py
```

## Verificação operacional em laboratório

- Confirmar que as duas caixas do tenant t3 têm PINs distintos de 8 dígitos.
- Validar a autenticação na caixa postal com PIN correto e errado.
- Confirmar que uma telefonista não acessa mensagens da outra.
- Confirmar permissões de arquivo e ausência de credenciais nos logs.
- Verificar que o encerramento da sessão elimina credenciais visíveis.
- Documentar a rotação de credenciais se o PIN for comprometido.

## Limitações

Esta mudança afeta **novos** tenants criados pelo wizard. **Não corrige
automaticamente** o PIN fraco das caixas já criadas, nem as configurações
estáticas t1/t2 e os ramais dinâmicos do painel (que precisam de auditoria
e rotação específica). Não implementa bloqueio de tentativas de acesso
a voicemail nem substitui os controles do Asterisk. Registro SIP,
áudio, gravações e isolamento ainda requerem homologação real.
