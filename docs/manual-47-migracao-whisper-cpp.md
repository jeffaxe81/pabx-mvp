# Manual 47 — Migração faster-whisper → whisper.cpp

## O que mudou
A transcrição de áudio (backlog #21, manual 36) trocou de
**faster-whisper** (Python/CTranslate2) pra **whisper.cpp** (C/C++
puro, via o binding `pywhispercpp`) — mais leve pra hardware bem
restrito, roda sem GPU inclusive em máquinas com poucos recursos
(dependendo do tamanho do modelo e da carga).

**O que NÃO mudou**: os pesos do modelo Whisper em si (licença MIT,
sem restrição comercial) — a troca é só de **motor**, não de modelo.
A qualidade de transcrição em português vem do modelo, que é o
mesmo dos dois lados.

## Por que trocar
- `whisper.cpp` é a referência de mercado pra rodar Whisper em
  hardware bem restrito — chega a rodar em Raspberry Pi com modelos
  pequenos
- Sem dependência de PyTorch nem CTranslate2 — footprint menor
- Mesma família de licença (MIT) nos dois lados, sem mudança de risco
  jurídico

## O que foi alterado
- `ai-worker/transcription.py`: `get_whisper_model()` e
  `transcribe_audio()` reescritos pra usar `pywhispercpp.model.Model`
  em vez de `faster_whisper.WhisperModel` — a interface externa
  (`transcribe_audio(path, model_size, language)`) continua igual,
  então nada mais no projeto (`pipeline.py`, `server.py`) precisou
  mudar
- `ai-worker/requirements.txt`: `faster-whisper==1.0.3` →
  `pywhispercpp==1.2.0`
- `ai-worker/Dockerfile`: adicionados `build-essential`, `cmake`,
  `git` — o `pywhispercpp` **compila o whisper.cpp durante o `pip
  install`**, diferente do `faster-whisper` que normalmente já vem
  com binário pré-compilado

## Como ativar
Mesmo processo do manual 36 — nada mudou na configuração
(`AI_FEATURES_ENABLED`, `WHISPER_MODEL_SIZE`), só o motor por baixo.

## Teste automatizado
- `ai-worker/tests/test_transcription.py::test_get_whisper_model_calls_pywhispercpp_and_caches`
  — confirma (com mock) que a chamada é pro `pywhispercpp`, não mais
  pro `faster_whisper`, e que o modelo é cacheado
- Os outros 4 testes de `is_supported_audio_file` continuam passando
  sem alteração (lógica pura, não depende do motor)

## Limitações conhecidas (honestidade técnica)
- **Nunca testado contra o `pywhispercpp` de verdade** — mesma
  limitação já documentada pro `faster-whisper` no manual 36, agora
  válida pro novo motor. A assinatura exata da API
  (`Model(model_size, n_threads=4)`, `model.transcribe(path,
  language=...)`) foi escrita com base no conhecimento geral da
  biblioteca, não confirmada rodando de verdade neste ambiente
- **Compilação em tempo de build, não testada** — o
  `RUN pip install pywhispercpp` no Dockerfile nunca rodou de fato
  neste ambiente; se a compilação falhar em produção, confira a
  versão do `cmake`/`gcc` disponível na imagem base contra o que o
  `pywhispercpp` exige na versão instalada
- **Download do modelo `.bin` (ggml/GGUF)**: a primeira execução
  baixa o arquivo do modelo automaticamente (comportamento esperado
  da biblioteca) — isso exige internet na primeira vez, mesmo rodando
  localmente depois
- **`n_threads=4` fixo** — não configurável via variável de ambiente
  ainda; ajustar conforme o hardware real de produção
