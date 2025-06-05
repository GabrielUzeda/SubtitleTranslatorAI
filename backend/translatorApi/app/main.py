from fastapi import FastAPI, Request
from pydantic import BaseModel
from app.utils import detect_language, translate_with_ollama, translate_srt_optimized, get_model_config, count_tokens
import os
import time

app = FastAPI(title="Advanced Subtitle Translation API", version="3.0.0")

class TranslateRequest(BaseModel):
    text: str
    source_lang: str | None = None
    target_lang: str | None = "pt-br"
    use_optimized: bool | None = True  # Nova opção para usar abordagem otimizada

class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    processing_info: dict

@app.get("/")
async def root():
    model = os.getenv("OLLAMA_MODEL", "tibellium/towerinstruct-mistral")
    model_config = get_model_config(model)
    
    return {
        "service": "Advanced Subtitle Translation API",
        "version": "3.0.0",
        "features": [
            "Text-only extraction for optimized translation",
            "Smart content type detection (dialogue/narrative/sound effects)",
            "Automatic SRT structure preservation",
            "Intelligent chunking for large files",
            "Legacy full-SRT translation support"
        ],
        "current_model": model,
        "model_config": {
            "max_tokens": model_config["max_tokens"],
            "safe_chunk_size": model_config["safe_chunk_size"],
            "temperature": model_config["temperature"]
        }
    }

@app.post("/translate", response_model=TranslateResponse)
async def translate(req: TranslateRequest):
    start_time = time.time()
    
    # Detect source language if not provided
    source_lang = req.source_lang or detect_language(req.text)
    target_lang = req.target_lang or "pt-br"
    use_optimized = req.use_optimized if req.use_optimized is not None else True
    
    # Get model configuration
    model = os.getenv("OLLAMA_MODEL", "tibellium/towerinstruct-mistral")
    model_config = get_model_config(model)
    
    # Count tokens in input
    input_tokens = count_tokens(req.text, model_config["encoding"])
    
    # Log processing start
    print(f"\n=== Translation Request ===")
    print(f"Model: {model}")
    print(f"Input tokens: {input_tokens}")
    print(f"Source: {source_lang} → Target: {target_lang}")
    print(f"Method: {'Optimized (text-only)' if use_optimized else 'Legacy (full-SRT)'}")
    
    # Choose translation method
    if use_optimized:
        translated = translate_srt_optimized(req.text, source_lang, target_lang)
        method_used = "optimized"
    else:
        translated = translate_with_ollama(req.text, source_lang, target_lang)
        method_used = "legacy"
    
    # Calculate processing metrics
    end_time = time.time()
    processing_time = end_time - start_time
    output_tokens = count_tokens(translated, model_config["encoding"])
    
    # Prepare processing info
    processing_info = {
        "model_used": model,
        "translation_method": method_used,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "processing_time_seconds": round(processing_time, 2),
        "model_max_tokens": model_config["max_tokens"]
    }
    
    print(f"=== Translation Complete ===")
    print(f"Method: {method_used}")
    print(f"Processing time: {processing_time:.2f}s")
    print(f"Output tokens: {output_tokens}")
    print("=" * 30)
    
    return TranslateResponse(
        original_text=req.text,
        translated_text=translated,
        source_lang=source_lang,
        target_lang=target_lang,
        processing_info=processing_info
    )
