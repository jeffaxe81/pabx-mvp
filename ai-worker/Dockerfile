# Diferente do resto dos serviços deste projeto (queue-api, admin-api
# etc., que usam python:3.12-slim puro sem instalar nada), este
# precisa da biblioteca faster-whisper pra transcrição de áudio -
# é a primeira dependência externa real do projeto, ver manual 36.
FROM python:3.12-slim

WORKDIR /app

# ffmpeg é necessário pro faster-whisper processar os formatos de
# áudio gerados pelo Asterisk (wav/gsm)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

COPY . .

CMD ["python3", "server.py"]
