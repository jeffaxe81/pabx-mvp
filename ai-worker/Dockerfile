# Diferente do resto dos serviços deste projeto (queue-api, admin-api
# etc., que usam python:3.12-slim puro sem instalar nada), este
# precisa de dependências externas reais - primeiro faster-whisper,
# agora whisper.cpp (via pywhispercpp) desde o backlog #47. Ver
# manual 36/47.
FROM python:3.12-slim

WORKDIR /app

# ffmpeg processa os formatos de áudio gerados pelo Asterisk (wav/gsm).
# build-essential e cmake são necessários porque o pywhispercpp
# compila o whisper.cpp (C/C++) durante o `pip install` - não tem
# roda pré-compilada pra toda plataforma. NUNCA testado neste
# ambiente (sem GPU/build de verdade disponível) - se a compilação
# falhar em produção, confira a versão do cmake/gcc disponível na
# imagem base contra o que o pywhispercpp exige na versão instalada.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg build-essential cmake git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

COPY . .

CMD ["python3", "server.py"]
