"""
Cliente AMI de verdade, via socket TCP. Diferente de ami_protocol.py
(parsing puro) e queue_state.py (lógica de estado), este arquivo
depende de rede e por isso NÃO tem teste automatizado de integração
aqui - só dá pra validar de fato contra um Asterisk real. É a mesma
situação, já documentada no projeto, do tronco TDM (manual 04).
"""
import socket
import threading
import time

from ami_protocol import parse_ami_blocks, build_action


class AMIClient:
    def __init__(self, host, port, username, secret, on_event=None):
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self.on_event = on_event  # callback(event_dict)

        self._sock = None
        self._buffer = ""
        self._running = False
        self._lock = threading.Lock()

    def connect_and_login(self, timeout=5):
        self._sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self._sock.recv(4096)  # banner "Asterisk Call Manager/x.x.x"

        response = self._send_action_and_wait({
            "Action": "Login",
            "Username": self.username,
            "Secret": self.secret,
        })
        if response.get("Response") != "Success":
            raise ConnectionError(f"Falha no login AMI: {response}")

    def _send_action_and_wait(self, fields: dict) -> dict:
        with self._lock:
            self._sock.sendall(build_action(fields).encode("utf-8"))
            data = self._sock.recv(4096).decode("utf-8", errors="replace")
        blocks = parse_ami_blocks(data)
        return blocks[0] if blocks else {}

    def send_action(self, fields: dict) -> dict:
        return self._send_action_and_wait(fields)

    def redirect_channel(self, channel: str, context: str, exten: str = "s", priority: int = 1) -> dict:
        """
        Ação usada pelo pickup dirigido: puxa um canal específico
        (uma chamada esperando na fila) e manda ele pra um contexto
        diferente do dialplan - no nosso caso, o contexto que disca
        pro ramal da telefonista.
        """
        return self.send_action({
            "Action": "Redirect",
            "Channel": channel,
            "Context": context,
            "Exten": exten,
            "Priority": str(priority),
        })

    def start_event_loop(self):
        """Roda em thread separada, lendo eventos continuamente."""
        self._running = True
        thread = threading.Thread(target=self._read_loop, daemon=True)
        thread.start()

    def stop(self):
        self._running = False
        if self._sock:
            self._sock.close()

    def _read_loop(self):
        self._sock.settimeout(1.0)
        while self._running:
            try:
                chunk = self._sock.recv(4096).decode("utf-8", errors="replace")
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                time.sleep(0.5)
                continue

            self._buffer += chunk
            while "\r\n\r\n" in self._buffer:
                block_text, self._buffer = self._buffer.split("\r\n\r\n", 1)
                blocks = parse_ami_blocks(block_text + "\r\n\r\n")
                for block in blocks:
                    if block.get("Event") and self.on_event:
                        self.on_event(block)
