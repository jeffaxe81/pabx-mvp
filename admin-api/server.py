"""
Servidor HTTP do painel de administração. Serve tanto a API (JSON)
quanto o próprio HTML estático do painel (admin/index.html) - um
serviço só, sem nginx separado, já que é uma ferramenta interna de
baixo tráfego.

Endpoints:
  POST /api/login              -> {username, password} -> {token}
  POST /api/logout             -> (com header Authorization)
  GET  /api/extensions         -> lista os ramais (sem a senha)
  POST /api/extensions         -> cria um ramal
  PUT  /api/extensions/<name>  -> edita um ramal
  DELETE /api/extensions/<name> -> remove um ramal
  GET  /                       -> serve admin/index.html
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from auth import hash_password, verify_password, SessionStore
from store import add_extension, update_extension, delete_extension, load_store
from conf_generator import render_all
from ami_client import AMIClient
from blocklist import validate_blocklist_number
from vip import validate_vip_input
from tenants import (
    load_tenants, save_tenants, validate_tenant_creation_input,
    render_tenant_pjsip, render_tenant_queues, render_tenant_extensions, render_tenant_voicemail,
)
from users import load_users, save_users, find_user, add_user, update_user, delete_user, public_user
from totp import generate_secret, verify_totp, build_provisioning_uri

HTTP_PORT = int(os.environ.get("HTTP_PORT", "8091"))
STORE_PATH = os.environ.get("STORE_PATH", "/app/data/extensions_store.json")
TENANTS_PATH = os.environ.get("TENANTS_PATH", "/app/data/tenants.json")

# Multi-tenant (backlog #38/#39): t1/t2 são os exemplos estáticos
# originais do projeto (sempre válidos); os demais são os que o
# wizard de preparação de ambiente criou dinamicamente.
STATIC_TENANTS = {"t1", "t2"}
DEFAULT_TENANT = "t1"


def validate_tenant(raw_tenant: str):
    """Retorna o tenant se for conhecido (estático ou criado pelo wizard), ou None. Vazio/ausente vira o padrão (t1)."""
    tenant = (raw_tenant or DEFAULT_TENANT).strip()
    known_tenants = STATIC_TENANTS | {t["tenant_id"] for t in load_tenants(TENANTS_PATH)}
    return tenant if tenant in known_tenants else None
USERS_PATH = os.environ.get("USERS_PATH", "/app/data/users.json")
ASTERISK_CONF_DIR = os.environ.get("ASTERISK_CONF_DIR", "/app/asterisk-conf")
STATIC_DIR = Path(os.environ.get("STATIC_DIR", "/app/static"))

# Usuário admin inicial (backlog #19): usado só pra popular o primeiro
# usuário caso ainda não exista nenhum em USERS_PATH - depois disso,
# o gerenciamento de usuários é todo pelo painel (seção "Usuários").
# Sem hash pré-configurado E sem usuários já cadastrados = login
# sempre falha (desligado por padrão, mesmo padrão de segurança já
# usado em notificações e click-to-call).
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

AMI_HOST = os.environ.get("AMI_HOST", "127.0.0.1")
AMI_PORT = int(os.environ.get("AMI_PORT", "5038"))
AMI_USERNAME = os.environ.get("AMI_USERNAME", "admin-api")
AMI_SECRET = os.environ.get("AMI_SECRET", "troque_esta_senha_ami")

# 2FA (backlog #20). Papel-sentinela usado só na sessão pré-login,
# entre "senha confirmada" e "código TOTP confirmado" - nunca bate em
# nenhum _require_role() de verdade, então uma sessão pendente nunca
# consegue fazer nada além de terminar a verificação.
TOTP_PENDING_ROLE = "__pending_totp__"
TOTP_ISSUER = "PABX Admin"

sessions = SessionStore()


def ensure_bootstrap_admin():
    """
    Roda na inicialização: se USERS_PATH ainda não tem ninguém e as
    variáveis ADMIN_USERNAME/ADMIN_PASSWORD_HASH estão configuradas,
    cria o primeiro usuário (papel admin) a partir delas. Se
    ADMIN_PASSWORD_HASH estiver vazio, não cria nada - login continua
    desabilitado até alguém configurar isso de propósito.
    """
    if load_users(USERS_PATH):
        return
    if not ADMIN_PASSWORD_HASH:
        return
    save_users(USERS_PATH, [{
        "username": ADMIN_USERNAME,
        "password_hash": ADMIN_PASSWORD_HASH,
        "role": "admin",
        "totp_secret": None,
        "totp_enabled": False,
    }])


def regenerate_and_reload():
    """Regera os arquivos dinâmicos (um por tenant pra dial/hints/voicemail, ver manual 38) e pede pro Asterisk recarregar."""
    extensions = load_store(STORE_PATH)
    files = render_all(extensions)
    for filename, content in files.items():
        Path(ASTERISK_CONF_DIR, filename).write_text(content, encoding="utf-8")

    client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
    try:
        client.connect_and_login()
        return client.reload_pjsip_and_dialplan()
    finally:
        client.close()


def public_view(extension: dict) -> dict:
    """Remove a senha antes de mandar pro navegador."""
    return {k: v for k, v in extension.items() if k != "password"}


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return None

    def _authenticated_username(self):
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        return sessions.validate(auth_header[len("Bearer "):])

    def _authenticated_role(self):
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        return sessions.get_role(auth_header[len("Bearer "):])

    def _require_auth(self):
        username = self._authenticated_username()
        if not username:
            self._send_json(401, {"error": "não autenticado"})
        return username

    def _require_role(self, allowed_roles):
        """
        Checa autenticação E papel. Retorna o username se tudo ok,
        None caso contrário (já tendo mandado a resposta de erro).
        """
        username = self._authenticated_username()
        if not username:
            self._send_json(401, {"error": "não autenticado"})
            return None
        role = self._authenticated_role()
        if role not in allowed_roles:
            self._send_json(403, {"error": f"papel '{role}' não tem permissão para esta ação"})
            return None
        return username

    def log_message(self, format, *args):
        pass

    # ---------- GET ----------
    def do_GET(self):
        if self.path.startswith("/api/extensions"):
            if not self._require_role({"admin", "supervisor"}):
                return
            tenant_filter = parse_qs(urlparse(self.path).query).get("tenant", [None])[0]
            extensions = [
                public_view(e) for e in load_store(STORE_PATH)
                if not tenant_filter or e.get("tenant", DEFAULT_TENANT) == tenant_filter
            ]
            self._send_json(200, {"extensions": extensions})
        elif self.path.startswith("/api/blocklist"):
            if not self._require_role({"admin", "supervisor"}):
                return
            self._handle_list_blocklist()
        elif self.path.startswith("/api/vip"):
            if not self._require_role({"admin", "supervisor"}):
                return
            self._handle_list_vip()
        elif self.path.startswith("/api/config/modo-feriado"):
            if not self._require_role({"admin", "supervisor"}):
                return
            self._handle_get_holiday_mode()
        elif self.path.startswith("/api/users"):
            if not self._require_role({"admin"}):
                return
            users = [public_user(u) for u in load_users(USERS_PATH)]
            self._send_json(200, {"users": users})
        elif self.path.startswith("/api/tenants"):
            if not self._require_role({"admin"}):
                return
            self._send_json(200, {"tenants": load_tenants(TENANTS_PATH)})
        elif self.path in ("/", "/index.html"):
            self._serve_static("index.html", "text/html")
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_list_blocklist(self):
        tenant = validate_tenant(parse_qs(urlparse(self.path).query).get("tenant", [None])[0])
        if not tenant:
            self._send_json(400, {"error": "tenant inválido ou não cadastrado"})
            return
        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            numbers = client.list_blocked_numbers(tenant)
            self._send_json(200, {"numbers": numbers, "tenant": tenant})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _handle_list_vip(self):
        tenant = validate_tenant(parse_qs(urlparse(self.path).query).get("tenant", [None])[0])
        if not tenant:
            self._send_json(400, {"error": "tenant inválido ou não cadastrado"})
            return
        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            vips = client.list_vips(tenant)
            self._send_json(200, {"vips": vips, "tenant": tenant})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _handle_get_holiday_mode(self):
        tenant = validate_tenant(parse_qs(urlparse(self.path).query).get("tenant", [None])[0])
        if not tenant:
            self._send_json(400, {"error": "tenant inválido ou não cadastrado"})
            return
        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            enabled = client.get_holiday_mode(tenant)
            self._send_json(200, {"enabled": enabled, "tenant": tenant})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _serve_static(self, filename, content_type):
        file_path = STATIC_DIR / filename
        if not file_path.is_file():
            self._send_json(404, {"error": "not found"})
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------- POST ----------
    def do_POST(self):
        if self.path == "/api/login":
            self._handle_login()
        elif self.path == "/api/logout":
            self._handle_logout()
        elif self.path == "/api/extensions":
            self._handle_create_extension()
        elif self.path == "/api/blocklist":
            self._handle_add_to_blocklist()
        elif self.path == "/api/vip":
            self._handle_add_vip()
        elif self.path == "/api/config/modo-feriado":
            self._handle_set_holiday_mode()
        elif self.path == "/api/users":
            self._handle_create_user()
        elif self.path == "/api/tenants":
            self._handle_create_tenant()
        elif self.path == "/api/login/verify-totp":
            self._handle_verify_totp_login()
        elif self.path == "/api/totp/setup":
            self._handle_totp_setup()
        elif self.path == "/api/totp/confirm":
            self._handle_totp_confirm()
        elif self.path == "/api/totp/disable":
            self._handle_totp_disable()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_totp_setup(self):
        """
        Autoatendimento: qualquer usuário logado configura o 2FA da
        PRÓPRIA conta, não de terceiros - por isso só _require_auth(),
        sem checar papel (admin e supervisor podem ativar 2FA igual).
        """
        username = self._require_auth()
        if not username:
            return

        secret = generate_secret()
        # Guarda o segredo já, mas com totp_enabled=False - só vira
        # "de verdade" depois de confirmado com um código válido
        # (senão a pessoa poderia travar a própria conta com um
        # segredo que nunca configurou no app dela).
        ok, error, cleaned = update_user(USERS_PATH, username, {"totp_secret": secret, "totp_enabled": False})
        if not ok:
            self._send_json(400, {"error": error})
            return

        uri = build_provisioning_uri(secret, username, issuer=TOTP_ISSUER)
        self._send_json(200, {"secret": secret, "otpauth_uri": uri})

    def _handle_totp_confirm(self):
        username = self._require_auth()
        if not username:
            return

        data = self._read_json_body()
        code = (data or {}).get("code", "")

        user = find_user(load_users(USERS_PATH), username)
        if not user or not user.get("totp_secret"):
            self._send_json(400, {"error": "nenhuma configuração de 2FA pendente - chame /api/totp/setup primeiro"})
            return

        if not verify_totp(user["totp_secret"], code):
            self._send_json(401, {"error": "código inválido"})
            return

        update_user(USERS_PATH, username, {"totp_enabled": True})
        self._send_json(200, {"enabled": True})

    def _handle_totp_disable(self):
        """Exige a senha de novo - desativar 2FA é sensível o bastante pra reconfirmar identidade."""
        username = self._require_auth()
        if not username:
            return

        data = self._read_json_body()
        password = (data or {}).get("password", "")

        user = find_user(load_users(USERS_PATH), username)
        if not user or not verify_password(password, user["password_hash"]):
            self._send_json(401, {"error": "senha incorreta"})
            return

        update_user(USERS_PATH, username, {"totp_secret": None, "totp_enabled": False})
        self._send_json(200, {"enabled": False})

    def _handle_create_user(self):
        if not self._require_role({"admin"}):
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        ok, error, cleaned = add_user(USERS_PATH, data)
        if not ok:
            self._send_json(400, {"error": error})
            return
        self._send_json(201, {"user": public_user(cleaned)})

    def _handle_create_tenant(self):
        """
        Wizard de preparação de ambiente (backlog #39): cria um tenant
        novo de ponta a ponta - gera os 4 arquivos de config (um por
        tenant, incluídos via wildcard - ver manual 39), registra o
        DID no AstDB, e persiste o tenant na lista de conhecidos.
        Pede reload no final igual ao resto do painel.
        """
        if not self._require_role({"admin"}):
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        existing = load_tenants(TENANTS_PATH)
        ok, error, cleaned = validate_tenant_creation_input(data, existing)
        if not ok:
            self._send_json(400, {"error": error})
            return

        tenant_id = cleaned["tenant_id"]
        for subdir, filename_prefix, render_fn in (
            ("pjsip_tenants", "", render_tenant_pjsip),
            ("queues_tenants", "", render_tenant_queues),
            ("extensions_tenants", "", render_tenant_extensions),
            ("voicemail_tenants", "", render_tenant_voicemail),
        ):
            target_dir = Path(ASTERISK_CONF_DIR, subdir)
            target_dir.mkdir(parents=True, exist_ok=True)
            Path(target_dir, f"{tenant_id}.conf").write_text(render_fn(tenant_id), encoding="utf-8")

        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            client.register_tenant_did(cleaned["did"], tenant_id)
            reload_result = client.reload_pjsip_and_dialplan()
        except Exception as exc:  # noqa: BLE001
            existing.append(cleaned)
            save_tenants(TENANTS_PATH, existing)
            self._send_json(201, {"tenant": cleaned, "reload_error": str(exc)})
            return
        finally:
            client.close()

        existing.append(cleaned)
        save_tenants(TENANTS_PATH, existing)
        self._send_json(201, {"tenant": cleaned, "reload": reload_result})

    def _handle_set_holiday_mode(self):
        if not self._require_role({"admin", "supervisor"}):
            return
        data = self._read_json_body()
        if data is None or "enabled" not in data:
            self._send_json(400, {"error": "campo 'enabled' obrigatório"})
            return
        tenant = validate_tenant(data.get("tenant"))
        if not tenant:
            self._send_json(400, {"error": "tenant inválido ou não cadastrado"})
            return

        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            client.set_holiday_mode(bool(data["enabled"]), tenant)
            self._send_json(200, {"enabled": bool(data["enabled"]), "tenant": tenant})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _handle_add_to_blocklist(self):
        if not self._require_role({"admin"}):
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        number = validate_blocklist_number(data.get("number", ""))
        if not number:
            self._send_json(400, {"error": "número inválido"})
            return
        tenant = validate_tenant(data.get("tenant"))
        if not tenant:
            self._send_json(400, {"error": "tenant inválido ou não cadastrado"})
            return

        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            response = client.block_number(number, tenant)
            if response.get("Response") == "Success":
                self._send_json(201, {"number": number, "tenant": tenant})
            else:
                self._send_json(502, {"error": "falha ao bloquear", "detail": response})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _handle_add_vip(self):
        if not self._require_role({"admin"}):
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        ok, error, cleaned = validate_vip_input(data)
        if not ok:
            self._send_json(400, {"error": error})
            return
        tenant = validate_tenant(data.get("tenant"))
        if not tenant:
            self._send_json(400, {"error": "tenant inválido ou não cadastrado"})
            return

        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            response = client.set_vip(cleaned["number"], cleaned["target_extension"], tenant)
            if response.get("Response") == "Success":
                self._send_json(201, {**cleaned, "tenant": tenant})
            else:
                self._send_json(502, {"error": "falha ao cadastrar VIP", "detail": response})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _handle_login(self):
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        username = (data.get("username") or "").strip().lower()
        password = data.get("password", "")

        users = load_users(USERS_PATH)
        if not users:
            self._send_json(503, {"error": "painel não configurado (nenhum usuário cadastrado)"})
            return

        user = find_user(users, username)
        if not user or not verify_password(password, user["password_hash"]):
            self._send_json(401, {"error": "usuário ou senha inválidos"})
            return

        if user.get("totp_enabled"):
            # Senha confirmada, mas falta o segundo fator - emite um
            # token pendente de curta duração em vez da sessão de verdade.
            pending_token = sessions.create(username, role=TOTP_PENDING_ROLE)
            self._send_json(200, {"requires_totp": True, "pending_token": pending_token})
            return

        token = sessions.create(username, role=user["role"])
        self._send_json(200, {"token": token, "role": user["role"]})

    def _handle_verify_totp_login(self):
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        pending_token = data.get("pending_token", "")
        code = data.get("code", "")

        username = sessions.validate(pending_token)
        role_check = sessions.get_role(pending_token)
        if not username or role_check != TOTP_PENDING_ROLE:
            self._send_json(401, {"error": "sessão de verificação inválida ou expirada"})
            return

        user = find_user(load_users(USERS_PATH), username)
        if not user or not verify_totp(user.get("totp_secret", ""), code):
            self._send_json(401, {"error": "código de verificação inválido"})
            return

        sessions.revoke(pending_token)
        token = sessions.create(username, role=user["role"])
        self._send_json(200, {"token": token, "role": user["role"]})

    def _handle_logout(self):
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            sessions.revoke(auth_header[len("Bearer "):])
        self._send_json(200, {"ok": True})

    def _handle_create_extension(self):
        if not self._require_role({"admin"}):
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        ok, error, cleaned = add_extension(STORE_PATH, data)
        if not ok:
            self._send_json(400, {"error": error})
            return

        try:
            reload_result = regenerate_and_reload()
        except Exception as exc:  # noqa: BLE001
            self._send_json(200, {"extension": public_view(cleaned), "reload_error": str(exc)})
            return

        self._send_json(201, {"extension": public_view(cleaned), "reload": reload_result})

    # ---------- PUT / DELETE ----------
    def do_PUT(self):
        if self.path.startswith("/api/extensions/"):
            self._handle_update_extension()
        elif self.path.startswith("/api/users/"):
            self._handle_update_user()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_update_extension(self):
        if not self._require_role({"admin"}):
            return

        name = self.path[len("/api/extensions/"):]
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        ok, error, cleaned = update_extension(STORE_PATH, name, data)
        if not ok:
            self._send_json(400, {"error": error})
            return

        try:
            reload_result = regenerate_and_reload()
        except Exception as exc:  # noqa: BLE001
            self._send_json(200, {"extension": public_view(cleaned), "reload_error": str(exc)})
            return

        self._send_json(200, {"extension": public_view(cleaned), "reload": reload_result})

    def _handle_update_user(self):
        if not self._require_role({"admin"}):
            return

        username = self.path[len("/api/users/"):]
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        ok, error, cleaned = update_user(USERS_PATH, username, data)
        if not ok:
            self._send_json(400, {"error": error})
            return
        self._send_json(200, {"user": public_user(cleaned)})

    def do_DELETE(self):
        if self.path.startswith("/api/extensions/"):
            self._handle_delete_extension()
        elif self.path.startswith("/api/blocklist/"):
            self._handle_remove_from_blocklist()
        elif self.path.startswith("/api/vip/"):
            self._handle_remove_vip()
        elif self.path.startswith("/api/users/"):
            self._handle_delete_user()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_delete_extension(self):
        if not self._require_role({"admin"}):
            return

        name = self.path[len("/api/extensions/"):]
        ok, error = delete_extension(STORE_PATH, name)
        if not ok:
            self._send_json(404, {"error": error})
            return

        try:
            reload_result = regenerate_and_reload()
        except Exception as exc:  # noqa: BLE001
            self._send_json(200, {"ok": True, "reload_error": str(exc)})
            return

        self._send_json(200, {"ok": True, "reload": reload_result})

    def _handle_remove_from_blocklist(self):
        if not self._require_role({"admin"}):
            return

        path, _, query = self.path.partition("?")
        number = path[len("/api/blocklist/"):]
        tenant = validate_tenant(parse_qs(query).get("tenant", [None])[0])
        if not tenant:
            self._send_json(400, {"error": "tenant inválido ou não cadastrado"})
            return

        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            client.unblock_number(number, tenant)
            self._send_json(200, {"ok": True})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _handle_remove_vip(self):
        if not self._require_role({"admin"}):
            return

        path, _, query = self.path.partition("?")
        number = path[len("/api/vip/"):]
        tenant = validate_tenant(parse_qs(query).get("tenant", [None])[0])
        if not tenant:
            self._send_json(400, {"error": "tenant inválido ou não cadastrado"})
            return

        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            client.remove_vip(number, tenant)
            self._send_json(200, {"ok": True})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _handle_delete_user(self):
        if not self._require_role({"admin"}):
            return

        username = self.path[len("/api/users/"):]
        ok, error = delete_user(USERS_PATH, username)
        if not ok:
            self._send_json(400, {"error": error})
            return
        self._send_json(200, {"ok": True})


def main():
    Path(STORE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(ASTERISK_CONF_DIR).mkdir(parents=True, exist_ok=True)
    ensure_bootstrap_admin()
    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"admin-api ouvindo em :{HTTP_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
