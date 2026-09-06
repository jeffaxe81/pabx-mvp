"""
Cliente AMI mínimo, só pra disparar reload de config depois que o
painel gera os arquivos dinâmicos. Mesma situação já documentada pro
queue-api: isso é a parte que só dá pra validar contra um Asterisk de
verdade, sem teste de integração automatizado aqui.
"""
import socket

from ami_protocol import parse_ami_blocks, build_action


class AMIClient:
    def __init__(self, host, port, username, secret):
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self._sock = None

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
        """Recarrega PJSIP e dialplan sem derrubar chamadas em andamento."""
        pjsip_response = self._send_action({"Action": "Command", "Command": "pjsip reload"})
        dialplan_response = self._send_action({"Action": "Command", "Command": "dialplan reload"})
        voicemail_response = self._send_action({"Action": "Command", "Command": "voicemail reload"})
        return {
            "pjsip": pjsip_response.get("Response"),
            "dialplan": dialplan_response.get("Response"),
            "voicemail": voicemail_response.get("Response"),
        }

    def close(self):
        if self._sock:
            self._sock.close()
