# Manual 80 — Credenciais e isolamento no acesso a gravações

## Risco corrigido (Issue #30, primeira etapa)

Antes, `GET /api/recordings` e `GET /recordings/<arquivo>` eram
públicos para qualquer cliente que alcançasse a porta da queue-api.
O player também colocava o caminho diretamente em `<audio src>`,
sem enviar uma credencial.

Agora **ambos endpoints negam acesso por padrão**. Apenas tokens
Bearer pré-autorizados com hash SHA-256, papel, tenant e expiração
válida podem listar ou baixar gravações previamente relacionadas
ao tenant em um catálogo confiável.

O nome do áudio, sozinho, **não prova a qual empresa pertence**.
Áudios legados sem vínculo no catálogo ficam invisíveis até que o
responsável confirme sua origem; não há migração automática que
possa misturar tenants.

## Preparação (ambiente privado de homologação)

1. Crie um token aleatório forte (não use senha SIP, AMI ou de login).
   Exemplo local em Python, sem serviços externos:

   ```bash
   python3 - <<'PY'
   import secrets, hashlib
   token = secrets.token_urlsafe(36)
   print("TOKEN (entregar por canal seguro):", token)
   print("SHA256 (gravar no catálogo):", hashlib.sha256(token.encode()).hexdigest())
   PY
   ```

2. Crie `/app/data/recording_access.json` dentro do volume privado
   `queue_api_data` com permissões restritas. Exemplo **sem token real**:

   ```json
   {
     "credentials": [
       {
         "token_sha256": "<64 caracteres hexadecimais do token>",
         "tenant": "t1",
         "role": "supervisor",
         "expires_at": 4102444800
       }
     ],
     "recordings": {
       "20261022-120000-11999998888-1010.wav": {
         "tenant": "t1",
         "owner_extension": "t1-1010"
       }
     }
   }
   ```

   A expiração do exemplo é ilustrativa, **não** uma recomendação de
   longa duração. Use vencimentos curtos e substitua/revogue os hashes
   quando necessário. Não coloque arquivo, token nem dados reais no Git.

3. Só relacione `filename -> tenant` depois de conferir a origem em
   registro de chamada/Asterisk/tenant confiável. **Nunca confie em
   um parâmetro de tenant vindo do navegador** ou em heurística por
   sufixo do nome. Para `role: agent`, informe também
   `extension` na credencial: agentes só veem registros com
   `owner_extension` coincidente. Admin e supervisor veem apenas
   os registros do próprio tenant.

4. Configure `RECORDINGS_ACCESS_POLICY_PATH` (padrão
   `/app/data/recording_access.json`) e `RECORDINGS_CORS_ORIGINS`
   com a URL **exata** da interface, por exemplo
   `https://pabx.exemplo.com`. O padrão vazio nega preflights
   cross-origin. A `queue-api` segue sem HTTPS nativo: termine TLS
   em proxy reverso confiável e bloqueie acesso direto à porta HTTP,
   inclusive com firewall. Não transfira credenciais em HTTP remoto.

5. No Webphone, insira a credencial em **Gravações** e clique
   **Atualizar**; o token só é mantido no campo durante a sessão.
   Ao desconectar, o campo é limpo. O player busca o áudio via
   `fetch` com cabeçalho Authorization e cria uma URL Blob temporária,
   revogada ao atualizar/desconectar. Tokens não são colocados nas URLs.

## Testes e validações

```bash
(cd queue-api && python3 -m pytest -q tests/test_recording_access.py tests/test_recording_http_security.py)
(cd tests && python3 -m pytest -q test_webphone_html.py)
```

Testes HTTP locais cobrem requisição anônima (401), token inválido e
revogado (401), lista isolada por tenant, gravação de outro tenant (404),
CORS não autorizado (403) e preflight autorizado (204). Não usam
arquivos reais ou Asterisk.

## Limitações e GO

- Esta etapa usa credenciais de serviço/operador emitidas fora do
  painel, não uma sessão SSO integrada ao administrador. O token é
  uma credencial delegada e **não comprova a identidade SIP**.
- O catálogo deve ser alimentado por uma origem administrativa
  confiável; sem catálogo o serviço permanece fechado. Não foi
  criado importador automático porque os nomes históricos são ambíguos.
- Endpoints não relacionados a gravações da queue-api ainda requerem
  auditoria independente de autenticação, autorização e CORS.
- É necessário testar o Webphone com HTTPS e gravações de laboratório,
  permissões de admin/supervisor/agente, revogação, isolamento entre
  empresas e recuperação antes de recomendar GO operacional.
