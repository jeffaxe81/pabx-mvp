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

from auth import hash_password, verify_password, SessionStore
from store import add_extension, update_extension, delete_extension, load_store
from conf_generator import render_all
from ami_client import AMIClient
from blocklist import validate_blocklist_number

HTTP_PORT = int(os.environ.get("HTTP_PORT", "8091"))
STORE_PATH = os.environ.get("STORE_PATH", "/app/data/extensions_store.json")
ASTERISK_CONF_DIR = os.environ.get("ASTERISK_CONF_DIR", "/app/asterisk-conf")
STATIC_DIR = Path(os.environ.get("STATIC_DIR", "/app/static"))

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
# Sem hash pré-configurado = login sempre falha (desligado por padrão,
# mesmo padrão de segurança já usado em notificações e click-to-call).
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

AMI_HOST = os.environ.get("AMI_HOST", "127.0.0.1")
AMI_PORT = int(os.environ.get("AMI_PORT", "5038"))
AMI_USERNAME = os.environ.get("AMI_USERNAME", "admin-api")
AMI_SECRET = os.environ.get("AMI_SECRET", "troque_esta_senha_ami")

sessions = SessionStore()


def regenerate_and_reload():
    """Regera os 4 arquivos dinâmicos e pede pro Asterisk recarregar."""
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

    def _require_auth(self):
        username = self._authenticated_username()
        if not username:
            self._send_json(401, {"error": "não autenticado"})
        return username

    def log_message(self, format, *args):
        pass

    # ---------- GET ----------
    def do_GET(self):
        if self.path.startswith("/api/extensions"):
            if not self._require_auth():
                return
            extensions = [public_view(e) for e in load_store(STORE_PATH)]
            self._send_json(200, {"extensions": extensions})
        elif self.path.startswith("/api/blocklist"):
            if not self._require_auth():
                return
            self._handle_list_blocklist()
        elif self.path.startswith("/api/config/modo-feriado"):
            if not self._require_auth():
                return
            self._handle_get_holiday_mode()
        elif self.path in ("/", "/index.html"):
            self._serve_static("index.html", "text/html")
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_list_blocklist(self):
        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            numbers = client.list_blocked_numbers()
            self._send_json(200, {"numbers": numbers})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _handle_get_holiday_mode(self):
        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            enabled = client.get_holiday_mode()
            self._send_json(200, {"enabled": enabled})
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
        elif self.path == "/api/config/modo-feriado":
            self._handle_set_holiday_mode()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_set_holiday_mode(self):
        if not self._require_auth():
            return
        data = self._read_json_body()
        if data is None or "enabled" not in data:
            self._send_json(400, {"error": "campo 'enabled' obrigatório"})
            return

        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            client.set_holiday_mode(bool(data["enabled"]))
            self._send_json(200, {"enabled": bool(data["enabled"])})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _handle_add_to_blocklist(self):
        if not self._require_auth():
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        number = validate_blocklist_number(data.get("number", ""))
        if not number:
            self._send_json(400, {"error": "número inválido"})
            return

        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            response = client.block_number(number)
            if response.get("Response") == "Success":
                self._send_json(201, {"number": number})
            else:
                self._send_json(502, {"error": "falha ao bloquear", "detail": response})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()

    def _handle_login(self):
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "JSON inválido"})
            return

        username = data.get("username", "")
        password = data.get("password", "")

        if not ADMIN_PASSWORD_HASH:
            self._send_json(503, {"error": "painel não configurado (sem senha de admin definida)"})
            return

        if username != ADMIN_USERNAME or not verify_password(password, ADMIN_PASSWORD_HASH):
            self._send_json(401, {"error": "usuário ou senha inválidos"})
            return

        token = sessions.create(username)
        self._send_json(200, {"token": token})

    def _handle_logout(self):
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            sessions.revoke(auth_header[len("Bearer "):])
        self._send_json(200, {"ok": True})

    def _handle_create_extension(self):
        if not self._require_auth():
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
        if not self.path.startswith("/api/extensions/"):
            self._send_json(404, {"error": "not found"})
            return
        if not self._require_auth():
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

    def do_DELETE(self):
        if self.path.startswith("/api/extensions/"):
            self._handle_delete_extension()
        elif self.path.startswith("/api/blocklist/"):
            self._handle_remove_from_blocklist()
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_delete_extension(self):
        if not self._require_auth():
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
        if not self._require_auth():
            return

        number = self.path[len("/api/blocklist/"):]
        client = AMIClient(AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET)
        try:
            client.connect_and_login()
            client.unblock_number(number)
            self._send_json(200, {"ok": True})
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"falha ao consultar AMI: {exc}"})
        finally:
            client.close()


def main():
    Path(STORE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(ASTERISK_CONF_DIR).mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"admin-api ouvindo em :{HTTP_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
