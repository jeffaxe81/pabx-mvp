"""
Cliente AMI mínimo, só pra disparar reload de config depois que o
painel gera os arquivos dinâmicos. Mesma situação já documentada pro
queue-api: isso é a parte que só dá pra validar contra um Asterisk de
verdade, sem teste de integração automatizado aqui.
"""
import socket
import threading

from ami_protocol import parse_ami_blocks, build_action


class AMIClient:
    def __init__(self, host, port, username, secret):
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self._sock = None
        self._lock = threading.Lock()

    def connect_and_login(self, timeout=5):
        self._sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self._sock.recv(4096)  # banner

        response = self._send_action({
            "Action": "Login",
            "Username": self.username,
            "Secret": self.secret,
        })
        if response.get("Response") != "Success":
            raise ConnectionError(f"Falha no login AMI: {response}")

    def _send_action(self, fields: dict) -> dict:
        self._sock.sendall(build_action(fields).encode("utf-8"))
        data = self._sock.recv(4096).decode("utf-8", errors="replace")
        blocks = parse_ami_blocks(data)
        return blocks[0] if blocks else {}

    def reload_pjsip_and_dialplan(self):
        """Recarrega PJSIP, dialplan, voicemail, filas e estacionamento sem derrubar chamadas em andamento."""
        pjsip_response = self._send_action({"Action": "Command", "Command": "pjsip reload"})
        dialplan_response = self._send_action({"Action": "Command", "Command": "dialplan reload"})
        voicemail_response = self._send_action({"Action": "Command", "Command": "voicemail reload"})
        queue_response = self._send_action({"Action": "Command", "Command": "queue reload all"})
        parking_response = self._send_action({"Action": "Command", "Command": "parking reload"})
        return {
            "pjsip": pjsip_response.get("Response"),
            "dialplan": dialplan_response.get("Response"),
            "voicemail": voicemail_response.get("Response"),
            "queue": queue_response.get("Response"),
            "parking": parking_response.get("Response"),
        }

    def block_number(self, number: str, tenant: str = "t1"):
        """Adiciona um número na família 'blocklist-{tenant}' do AstDB (usado pelo dialplan)."""
        return self._send_action({
            "Action": "DBPut", "Family": f"blocklist-{tenant}", "Key": number, "Val": "1",
        })

    def unblock_number(self, number: str, tenant: str = "t1"):
        return self._send_action({
            "Action": "DBDel", "Family": f"blocklist-{tenant}", "Key": number,
        })

    def set_holiday_mode(self, enabled: bool, tenant: str = "t1"):
        """Liga/desliga o modo feriado da URA (AstDB família 'config-{tenant}')."""
        if enabled:
            return self._send_action({
                "Action": "DBPut", "Family": f"config-{tenant}", "Key": "modo-feriado", "Val": "1",
            })
        return self._send_action({
            "Action": "DBDel", "Family": f"config-{tenant}", "Key": "modo-feriado",
        })

    def get_holiday_mode(self, tenant: str = "t1") -> bool:
        response = self._send_action({
            "Action": "DBGet", "Family": f"config-{tenant}", "Key": "modo-feriado",
        })
        return response.get("Response") == "Success"

    def set_vip(self, number: str, target_extension: str, tenant: str = "t1"):
        """Associa um número de cliente a um ramal de destino direto (AstDB família 'vip-{tenant}')."""
        return self._send_action({
            "Action": "DBPut", "Family": f"vip-{tenant}", "Key": number, "Val": target_extension,
        })

    def remove_vip(self, number: str, tenant: str = "t1"):
        return self._send_action({
            "Action": "DBDel", "Family": f"vip-{tenant}", "Key": number,
        })

    def list_vips(self, tenant: str = "t1"):
        """
        Igual a list_blocked_numbers, mas precisa capturar Key E Val -
        o destino de cada cliente VIP é o que importa, não só o número.
        """
        with self._lock:
            self._sock.sendall(build_action({
                "Action": "DBGetTree", "Family": f"vip-{tenant}",
            }).encode("utf-8"))
            self._sock.settimeout(2.0)
            data = b""
            try:
                while True:
                    chunk = self._sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            except socket.timeout:
                pass
            finally:
                self._sock.settimeout(None)

        blocks = parse_ami_blocks(data.decode("utf-8", errors="replace"))
        return [
            {"number": b["Key"].split("/")[-1], "target_extension": b.get("Val", "")}
            for b in blocks if b.get("Key")
        ]

    def list_blocked_numbers(self, tenant: str = "t1"):
        """
        DBGetTree retorna uma Action ID com múltiplos eventos
        DBGetTreeEntry - simplificado aqui: lê tudo que vier do socket
        num intervalo curto, já que é uma lista pequena por natureza.
        """
        with self._lock:
            self._sock.sendall(build_action({
                "Action": "DBGetTree", "Family": f"blocklist-{tenant}",
            }).encode("utf-8"))
            self._sock.settimeout(2.0)
            data = b""
            try:
                while True:
                    chunk = self._sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            except socket.timeout:
                pass
            finally:
                self._sock.settimeout(None)

        blocks = parse_ami_blocks(data.decode("utf-8", errors="replace"))
        return [b["Key"].split("/")[-1] for b in blocks if b.get("Key")]

    def register_tenant_did(self, did: str, tenant_id: str):
        """
        Wizard de preparação de ambiente (backlog #39): associa um DID
        ao tenant, na mesma família AstDB que from-tdm-gateway consulta
        pra decidir ${TENANT} de chamadas de entrada não mapeadas
        explicitamente no dialplan.
        """
        return self._send_action({
            "Action": "DBPut", "Family": "tenant-did", "Key": did, "Val": tenant_id,
        })

    def unregister_tenant_did(self, did: str):
        return self._send_action({
            "Action": "DBDel", "Family": "tenant-did", "Key": did,
        })

    def close(self):
        if self._sock:
            self._sock.close()
