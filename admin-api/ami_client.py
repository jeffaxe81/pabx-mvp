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

    def set_overflow_timeout(self, seconds: int, tenant: str = "t1"):
        """
        Timeout de overflow entre filas (backlog #56) - mesma família
        AstDB do modo feriado ('config-{tenant}'), chave própria.
        """
        return self._send_action({
            "Action": "DBPut", "Family": f"config-{tenant}", "Key": "overflow-timeout-segundos", "Val": str(seconds),
        })

    def get_overflow_timeout(self, tenant: str = "t1"):
        """
        Diferente de get_holiday_mode (que só precisa saber
        sim/não) - aqui precisamos do VALOR de verdade, então usamos
        DBGetTree (mesma técnica de list_blocked_numbers/list_vips)
        em vez de DBGet, que não devolve o valor na resposta imediata.
        Retorna None se não configurado (dialplan cai no padrão global).
        """
        with self._lock:
            self._sock.sendall(build_action({
                "Action": "DBGetTree", "Family": f"config-{tenant}",
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
        for block in blocks:
            if block.get("Key", "").endswith("/overflow-timeout-segundos"):
                return block.get("Val")
        return None

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

    def register_extension_mapping(self, number: str, name: str, tenant: str = "t1"):
        """
        Mapeamento número→endpoint (backlog #55) - permite que o
        monitoramento de chamada (manual 42) alcance qualquer ramal
        dinâmico criado pelo painel, não só as telefonistas fixas
        (1010/1011). Chamado toda vez que um ramal é criado/editado.
        """
        return self._send_action({
            "Action": "DBPut", "Family": f"extension-map-{tenant}", "Key": str(number), "Val": name,
        })

    def unregister_extension_mapping(self, number: str, tenant: str = "t1"):
        """Chamado quando um ramal é removido - evita mapeamento órfão apontando pra um ramal que não existe mais."""
        return self._send_action({
            "Action": "DBDel", "Family": f"extension-map-{tenant}", "Key": str(number),
        })

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

    def set_monitoring_pin(self, pin: str, tenant: str = "t1"):
        """PIN de monitoramento de chamada (backlog #42) - AstDB família 'monitoring-pin-{tenant}'."""
        return self._send_action({
            "Action": "DBPut", "Family": f"monitoring-pin-{tenant}", "Key": "pin", "Val": pin,
        })

    def disable_monitoring(self, tenant: str = "t1"):
        """Remove o PIN - sem PIN configurado, o dialplan bloqueia o monitoramento por completo."""
        return self._send_action({
            "Action": "DBDel", "Family": f"monitoring-pin-{tenant}", "Key": "pin",
        })

    def is_monitoring_configured(self, tenant: str = "t1") -> bool:
        """
        Só informa SE tem PIN configurado - nunca devolve o PIN em si
        (mesmo princípio de nunca expor hash de senha de volta).
        """
        response = self._send_action({
            "Action": "DBGet", "Family": f"monitoring-pin-{tenant}", "Key": "pin",
        })
        return response.get("Response") == "Success"

    def close(self):
        if self._sock:
            self._sock.close()
