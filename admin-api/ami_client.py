"""
Cliente AMI mínimo, só pra disparar reload de config depois que o
painel gera os arquivos dinâmicos. Mesma situação já documentada pro
queue-api: isso é a parte que só dá pra validar contra um Asterisk de
verdade, sem teste de integração automatizado aqui.
"""
import secrets
import socket
import threading

from ami_protocol import parse_ami_blocks, build_action

MAX_AMI_REPLY_BYTES = 128 * 1024
MAX_AMI_EVENTS_PER_ACTION = 32


class AMIClient:
    def __init__(self, host, port, username, secret):
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self._sock = None
        self._lock = threading.RLock()
        self._recv_buffer = b""
        self._last_frame = b""

    def _receive(self):
        """Recebe mais bytes, preservando limites e erros da rede."""
        chunk = self._sock.recv(4096)
        if not chunk:
            raise ConnectionError("AMI fechou a conexão antes da resposta completa")
        self._recv_buffer += chunk
        if len(self._recv_buffer) > MAX_AMI_REPLY_BYTES:
            raise ConnectionError("AMI respondeu além do limite permitido")

    def _read_frame(self):
        """Extrai um único bloco CRLF CRLF sem perder bytes do próximo."""
        while b"\r\n\r\n" not in self._recv_buffer:
            self._receive()
        frame, self._recv_buffer = self._recv_buffer.split(b"\r\n\r\n", 1)
        self._last_frame = frame + b"\r\n\r\n"
        return self._last_frame

    def _consume_follows_output(self):
        """Compatibilidade com AMI antigo: Command Follows até END COMMAND."""
        terminator = b"--END COMMAND--"
        while True:
            index = self._recv_buffer.find(terminator)
            if index >= 0:
                trailer = self._recv_buffer.find(b"\r\n\r\n", index + len(terminator))
                if trailer >= 0:
                    self._recv_buffer = self._recv_buffer[trailer + 4:]
                    return
            self._receive()

    def connect_and_login(self, timeout=5):
        self._sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self._recv_buffer = b""
        try:
            while b"\n" not in self._recv_buffer:
                self._receive()
            banner, self._recv_buffer = self._recv_buffer.split(b"\n", 1)
            if not banner.strip().startswith(b"Asterisk Call Manager/"):
                raise ConnectionError("Banner AMI inválido")
            response = self._send_action({
                "Action": "Login",
                "Username": self.username,
                "Secret": self.secret,
            })
            if response.get("Response") != "Success":
                raise ConnectionError("Autenticação AMI recusada")
        except Exception:
            self.close()
            raise

    def _send_action(self, fields: dict) -> dict:
        """Espera resposta completa e ActionID certo; ignora eventos assíncronos."""
        with self._lock:
            action_id = "axe-pabx-" + secrets.token_hex(12)
            values = {**fields, "ActionID": action_id}
            self._sock.sendall(build_action(values).encode("utf-8"))
            for _ in range(MAX_AMI_EVENTS_PER_ACTION):
                block = parse_ami_blocks(self._read_frame().decode("utf-8", errors="replace"))
                if not block:
                    raise ConnectionError("Resposta AMI vazia")
                response = block[0]
                if "Event" in response and "Response" not in response:
                    continue
                if response.get("ActionID") != action_id or "Response" not in response:
                    raise ConnectionError("Resposta AMI não corresponde à ação solicitada")
                if response["Response"] == "Follows":
                    # Algumas versões antigas do Asterisk emitem a saída
                    # do comando após os headers, até --END COMMAND--.
                    if b"--END COMMAND--" not in self._last_frame:
                        self._consume_follows_output()
                return response
            raise ConnectionError("Eventos AMI excessivos antes da resposta")

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

    def _read_db_tree(self, family: str):
        """Aguarda o evento DBGetTreeComplete, sem depender de timeout.

        DBGetTree emite resposta inicial + eventos com o mesmo ActionID.
        As consultas ficam serializadas com as outras ações AMI.
        """
        with self._lock:
            result = self._send_action({"Action": "DBGetTree", "Family": family})
            if result.get("Response") != "Success":
                raise ConnectionError("Consulta AstDB não autorizada ou falhou")
            action_id = result["ActionID"]
            entries = []
            unrelated = 0
            for _ in range(2048):
                blocks = parse_ami_blocks(self._read_frame().decode(
                    "utf-8", errors="replace"
                ))
                if not blocks:
                    raise ConnectionError("Evento AMI vazio")
                event = blocks[0]
                if event.get("ActionID") != action_id:
                    # Outras notificações podem aparecer entre as
                    # respostas de uma listagem, mas são limitadas.
                    unrelated += 1
                    if unrelated > 32:
                        raise ConnectionError("Excesso de eventos AMI não relacionados")
                    continue
                event_name = event.get("Event")
                if event_name == "DBGetTreeComplete":
                    return entries
                if event_name in ("DBGetTreeResponse", "DBGetTreeEntry"):
                    if len(entries) >= 1000:
                        raise ConnectionError("Listagem AstDB excede o limite")
                    key = event.get("Key", "")
                    if isinstance(key, str) and key.startswith("/" + family + "/"):
                        entries.append(event)
                    continue
                raise ConnectionError("Evento inesperado durante listagem AstDB")
            raise ConnectionError("Listagem AstDB sem evento de conclusão")

    def get_overflow_timeout(self, tenant: str = "t1"):
        """Valor configurado do overflow ou None, com evento final confirmado."""
        items = self._read_db_tree(f"config-{tenant}")
        for item in items:
            if item["Key"] == f"/config-{tenant}/overflow-timeout-segundos":
                return item.get("Val")
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
        """Lista VIPs somente da família do tenant solicitado."""
        items = self._read_db_tree(f"vip-{tenant}")
        return [
            {"number": item["Key"].rsplit("/", 1)[-1],
             "target_extension": item.get("Val", "")}
            for item in items
        ]

    def list_blocked_numbers(self, tenant: str = "t1"):
        """Números bloqueados somente da família do tenant solicitado."""
        return [
            item["Key"].rsplit("/", 1)[-1]
            for item in self._read_db_tree(f"blocklist-{tenant}")
        ]

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
