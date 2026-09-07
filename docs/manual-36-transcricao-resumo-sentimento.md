# Manual 36 — Transcrição, resumo e análise de sentimento (itens #21, #22, #23)

## Leia isto primeiro: mudança de natureza do projeto
Até aqui, **todo** este projeto rodava com biblioteca padrão do
Python, sem nenhuma dependência externa e sem custo computacional
relevante. Esta é a **primeira funcionalidade que quebra isso** — de
propósito, porque não existe forma honesta de fazer reconhecimento de
voz sem um modelo de IA de verdade por trás.

**Decisão de provedor**: modelos **locais**, sem nuvem, sem custo por
requisição:
- **Whisper** (via `faster-whisper`) pra transcrição de áudio → texto
- **Llama 3** (via **Ollama**, rodando localmente) pro resumo e
  análise de sentimento a partir do texto transcrito

**Importante**: eu (Claude) não consigo rodar nem testar o Whisper ou
o Llama de verdade no ambiente onde este código foi escrito — não há
GPU disponível, nem como baixar os pesos dos modelos (vários GB cada).
Por isso, toda a lógica de decisão (prompts, parsing de resposta,
orquestração) tem teste automatizado completo usando *mocks* no lugar
das chamadas de IA reais — mesmo padrão de honestidade já usado neste
projeto pra AMI, SMTP e webhooks. **A integração de verdade com
Whisper/Ollama nunca foi executada** - só a lógica ao redor dela.

## O que é feito
1. **Transcrição** (#21): cada gravação de chamada (as mesmas do
   manual 09) é transcrita pra texto usando Whisper local
2. **Resumo automático** (#22): a transcrição vira um resumo de até 3
   frases via Llama 3 (só se a transcrição tiver conteúdo suficiente -
   uma chamada de 2 segundos não gera resumo nenhum)
3. **Análise de sentimento** (#23): a mesma transcrição é classificada
   como positivo/neutro/negativo via Llama 3

## Arquitetura
Um novo serviço, `ai-worker` (a primeira parte do projeto com
`Dockerfile` próprio, porque precisa instalar `faster-whisper` via
pip - todo o resto do projeto usa `python:3.12-slim` sem instalar
nada). Mais o serviço `ollama`, rodando o Llama 3.

```
Gravação (.wav) → Whisper (local) → texto
                                      ├→ Llama 3 → resumo
                                      └→ Llama 3 → sentimento
```

**Desligado por padrão** (`AI_FEATURES_ENABLED=false`) - processamento
de IA local consome CPU/tempo de verdade (minutos por chamada em
hardware modesto), bem diferente do resto das integrações "grátis"
deste projeto.

## Como ativar (leia as instruções de hardware antes)
1. Configure no `docker-compose.yml`:
   ```yaml
   AI_FEATURES_ENABLED: "true"
   WHISPER_MODEL_SIZE: "base"   # tiny/base/small/medium/large - maior = mais preciso e mais lento
   OLLAMA_MODEL: "llama3"
   ```
2. `docker compose up -d` (a primeira subida do `ai-worker` baixa e
   instala `faster-whisper` - só nessa etapa já precisa de internet)
3. **Baixe o modelo do Llama** (não vem embutido na imagem do Ollama,
   precisa ser baixado manualmente uma vez, vários GB):
   ```bash
   docker exec pabx-ollama ollama pull llama3
   ```
4. O `ai-worker` passa a varrer `./recordings/` a cada 60 segundos
   (configurável via `SCAN_INTERVAL_SECONDS`), processando uma
   gravação nova por vez

## Expectativa de hardware
- **CPU**: Whisper "base" + Llama 3 8B rodam em CPU comum, mas
  **lentamente** - um resumo pode levar de alguns segundos a
  minutos dependendo do hardware
- **RAM**: reserve pelo menos 8GB livres pro Llama 3 8B
- **GPU**: melhora muito a velocidade, mas configurar Ollama com GPU
  (NVIDIA + `nvidia-docker`) está fora do escopo deste manual

## Como consultar os resultados
```bash
curl "http://<ip>:8092/api/transcripts"                        # todas
curl "http://<ip>:8092/api/transcripts/20240101-100000-...wav"  # uma específica
curl -X POST "http://<ip>:8092/api/process/20240101-100000-...wav"  # forçar reprocessamento
```

## Como testar (o que dá pra testar sem IA real)
1. `docker compose up -d` (com `AI_FEATURES_ENABLED=false`, o padrão)
2. Confirme que `curl http://<ip>:8092/api/transcripts` responde
   normalmente (`ai_enabled: false`), mesmo sem nenhum processamento
   rodando
3. Pra testar de verdade com IA ativa, siga os passos de ativação
   acima com uma gravação real e confira o resultado em
   `/api/transcripts`

## Teste automatizado
**43 testes na suíte `ai-worker/tests/`** (nova, 6ª suíte do projeto),
cobrindo 100% da lógica de decisão com mocks:
- `test_llm_client.py` — montagem/parsing das chamadas ao Ollama
- `test_transcription.py` — só a parte pura (validação de formato de
  arquivo); a transcrição de verdade não é testável neste ambiente
- `test_summarizer.py` / `test_sentiment.py` — prompts e parsing de
  resposta, inclusive tolerância a respostas fora do formato esperado
- `test_pipeline.py` — o fluxo completo (transcrição→resumo→
  sentimento) com mocks, incluindo o caso de pular resumo/sentimento
  quando a transcrição é curta demais
- `test_recordings_scanner.py` — varredura de gravações pendentes
- `test_store.py` — persistência
- `test_server_security.py` — a flag `AI_FEATURES_ENABLED` é checada
  **antes** de processar, em todos os pontos de entrada (varredura
  automática e disparo manual)

## Limitações conhecidas (honestidade técnica)
- **Nunca testado contra Whisper/Ollama reais** (ver aviso no topo)
- **Processa uma gravação por vez**, sem paralelismo - Whisper/Llama
  em CPU já competem por recursos sozinhos
- **Sem retry automático** se o Ollama estiver fora do ar no momento
  do processamento - a gravação fica pendente até a próxima varredura
- **Resumo/sentimento em português fixo no prompt** - não adapta pro
  idioma da chamada (mesmo que o atendimento tenha sido em
  inglês/espanhol, manual 35)
- **Sem interface visual dedicada** - só API JSON; um painel mostrando
  transcrição/resumo/sentimento junto com o histórico de chamadas
  (manual 18) seria uma evolução natural
