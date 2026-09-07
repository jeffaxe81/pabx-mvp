"""
Orquestra o processamento de IA de uma gravação: transcreve, resume,
analisa sentimento, e guarda tudo. As funções de IA (transcribe_fn,
llm_fn) são injetáveis - por padrão usam as implementações de
verdade (transcription.transcribe_audio, llm_client.generate), mas
nos testes são substituídas por mocks, deixando toda a lógica de
orquestração 100% testável sem precisar do Whisper/Ollama de verdade.
"""
from transcription import transcribe_audio, is_supported_audio_file
from summarizer import build_summary_prompt, is_transcript_worth_summarizing, clean_summary_response
from sentiment import build_sentiment_prompt, parse_sentiment_response
from llm_client import generate as llm_generate


def process_recording(
    recording_path,
    filename: str,
    ollama_url: str,
    model: str = "llama3",
    whisper_model_size: str = "base",
    transcribe_fn=transcribe_audio,
    llm_fn=llm_generate,
) -> dict:
    """
    Processa uma gravação de ponta a ponta. Retorna um dict pronto
    pra guardar no TranscriptStore. Se a transcrição vier vazia/curta
    demais, resumo e sentimento ficam None (sem gastar chamada de LLM
    à toa, sem inventar conteúdo de uma transcrição inexistente).
    """
    if not is_supported_audio_file(recording_path):
        return {
            "filename": filename,
            "error": "formato de arquivo não suportado",
            "transcript": None,
            "summary": None,
            "sentiment": None,
        }

    transcript = transcribe_fn(recording_path, model_size=whisper_model_size)

    if not is_transcript_worth_summarizing(transcript):
        return {
            "filename": filename,
            "transcript": transcript,
            "summary": None,
            "sentiment": None,
        }

    summary_raw = llm_fn(ollama_url, build_summary_prompt(transcript), model=model)
    summary = clean_summary_response(summary_raw)

    sentiment_raw = llm_fn(ollama_url, build_sentiment_prompt(transcript), model=model)
    sentiment = parse_sentiment_response(sentiment_raw)

    return {
        "filename": filename,
        "transcript": transcript,
        "summary": summary,
        "sentiment": sentiment,
    }
