import requests
import os
from typing import Optional, List, Dict, Any, Tuple
import time
from functools import lru_cache
from langdetect import detect
import re
import tiktoken
import json

# Ollama configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
OLLAMA_MODEL = "tibellium/towerinstruct-mistral"

def load_evolutionary_config():
    """Load optimized configuration from evolutionary tuning"""
    config_path = "/app/optimal_config.json"
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                print("✅ Optimized configuration loaded from optimal_config.json")
                return config
        else:
            print(f"⚠️ File {config_path} not found, using default configuration")
    except Exception as e:
        print(f"⚠️ Error loading configuration: {e}")
    
    return {
        "temperature": 0.05,
        "top_p": 0.95,
        "top_k": 20,
        "repeat_penalty": 1.15,
        "max_tokens": 4000,
        "chunk_size": 10,
        "prompt_template": "stand_authority"
    }

EVOLUTIONARY_CONFIG = load_evolutionary_config()

MODEL_CONFIG = {
    "max_tokens": EVOLUTIONARY_CONFIG.get("max_tokens", 32768),
    "safe_chunk_size": 256,        
    "temperature": EVOLUTIONARY_CONFIG.get("temperature", 0.05),
    "top_p": EVOLUTIONARY_CONFIG.get("top_p", 0.95),               
    "top_k": EVOLUTIONARY_CONFIG.get("top_k", 20),                  
    "repeat_penalty": EVOLUTIONARY_CONFIG.get("repeat_penalty", 1.15),       
    "encoding": "cl100k_base",
    "chunk_size": EVOLUTIONARY_CONFIG.get("chunk_size", 10),
    "prompt_template": EVOLUTIONARY_CONFIG.get("prompt_template", "stand_authority")
}

def get_model_config(model_name: str) -> Dict[str, Any]:
    """Get model configuration parameters"""
    return MODEL_CONFIG.copy()

@lru_cache(maxsize=1000)
def detect_language(text: str) -> str:
    try:
        detected = detect(text)
        return detected
    except:
        return "en"

def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        return len(text) // 4

def split_srt_into_chunks(srt_text: str, max_chunk_tokens: int, encoding_name: str = "cl100k_base") -> List[str]:
    subtitle_pattern = r'(\d+\n(?:\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n)(?:.*?(?:\n|$))*?)(?=\n\d+\n|\n*$)'
    subtitles = re.findall(subtitle_pattern, srt_text, re.MULTILINE | re.DOTALL)
    
    if not subtitles:
        subtitles = [block.strip() for block in srt_text.split('\n\n') if block.strip()]
    
    chunks = []
    current_chunk = ""
    current_tokens = 0
    effective_max_tokens = max_chunk_tokens - 200
    
    for subtitle in subtitles:
        subtitle_tokens = count_tokens(subtitle, encoding_name)
        
        if subtitle_tokens > effective_max_tokens:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
                current_tokens = 0
            chunks.append(subtitle.strip())
            continue
        
        if current_tokens + subtitle_tokens > effective_max_tokens:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = subtitle
            current_tokens = subtitle_tokens
        else:
            if current_chunk:
                current_chunk += "\n\n" + subtitle
            else:
                current_chunk = subtitle
            current_tokens += subtitle_tokens
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def create_optimized_prompt(text: str, source_lang: str, target_lang: str, is_chunked: bool = False, chunk_info: str = "") -> str:
    """Create optimized prompt for subtitle translation"""
    
    base_prompt = f"""You are a professional SRT subtitle translator specializing in translation from {source_lang} to {target_lang}.

TASK: Translate the SRT subtitle content below while preserving EXACT formatting.

CRITICAL SRT FORMATTING RULES:
1. Maintain EXACT SRT structure:
   - Block number (e.g., 1, 2, 3...)
   - Timestamp line (e.g., 00:01:23,456 --> 00:01:26,789)
   - Text content (one or more lines)
   - Empty line between blocks

2. PRESERVE ALL FORMATTING:
   - Keep ALL HTML tags: <font>, <b>, <i>, etc. with exact attributes
   - Keep ALL special characters: {{\\an8}}, color codes, etc.
   - Keep ALL sound effects in brackets: [Explosion], (footsteps), etc.
   - Keep line breaks within subtitle blocks
   - Preserve empty lines between subtitle blocks

3. TRANSLATION RULES:
   - Translate ONLY readable text content, NOT the formatting
   - Keep character names consistent
   - Preserve timing information exactly as provided
   - Maintain appropriate reading speed for subtitles

4. OUTPUT FORMAT REQUIREMENTS:
   - Return ONLY the translated SRT content
   - NO explanations, NO comments, NO additional text
   - Start immediately with the first subtitle block
   - Maintain exact spacing and line breaks"""

    if is_chunked:
        base_prompt += f"""

CHUNKING NOTE:
{chunk_info}
- Maintain consistency with previous/following chunks
- Ensure smooth narrative flow
- Keep character names and terminology consistent"""

    base_prompt += f"""

SOURCE LANGUAGE: {source_lang}
TARGET LANGUAGE: {target_lang}

SRT CONTENT TO TRANSLATE:
---START SRT---
{text}
---END SRT---

Translated SRT output:"""

    return base_prompt

def translate_chunk_with_ollama(text: str, source_lang: str, target_lang: str, chunk_info: str = "") -> str:
    is_chunked = bool(chunk_info)
    
    prompt = create_optimized_prompt(text, source_lang, target_lang, is_chunked, chunk_info)
    prompt_tokens = count_tokens(prompt, MODEL_CONFIG["encoding"])
    print(f"Processing chunk with {prompt_tokens} tokens using {OLLAMA_MODEL}")
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": MODEL_CONFIG["temperature"],
            "top_p": MODEL_CONFIG["top_p"],
            "top_k": MODEL_CONFIG["top_k"],
            "repeat_penalty": MODEL_CONFIG["repeat_penalty"],
            "num_predict": min(MODEL_CONFIG["max_tokens"] - prompt_tokens - 100, 4096)
        }
    }

    max_retries = 3
    base_delay = 1
    max_delay = 10

    for attempt in range(max_retries):
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
            if response.status_code == 200:
                result = response.json()
                translated = result.get("response", "").strip()
                
                # Clean up response - remove common AI model artifacts
                lines = translated.split('\n')
                start_idx = 0
                
                # Find the first line that looks like a subtitle number
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line.isdigit() and int(line) > 0:
                        start_idx = i
                        break
                
                if start_idx > 0:
                    translated = '\n'.join(lines[start_idx:])
                
                # Remove common prompt artifacts
                cleanup_patterns = [
                    r'\n---END SRT---.*$',
                    r'\nTranslated SRT output:.*$',
                    r'\n\*\*.*\*\*.*$',
                    r'\nNote:.*$',
                    r'\nNOTE:.*$',
                    r'\n\d+\.\s+[A-Z][^:]*:.*$',
                    r'\n[A-Z\s]+:.*$',
                ]
                
                for pattern in cleanup_patterns:
                    translated = re.sub(pattern, '', translated, flags=re.DOTALL | re.IGNORECASE)
                
                translated = translated.strip()
                return translated
            else:
                print(f"API Error (attempt {attempt + 1}/{max_retries}): {response.status_code}")
        except Exception as e:
            print(f"API Exception (attempt {attempt + 1}/{max_retries}): {str(e)}")
        
        if attempt < max_retries - 1:
            delay = min(base_delay * (2 ** attempt), max_delay)
            time.sleep(delay)
    
    return text

def translate_with_ollama(text: str, source_lang: str, target_lang: str) -> str:
    if not text or len(text.strip()) < 2:
        return text

    print(f"Using model: {OLLAMA_MODEL} (max_tokens: {MODEL_CONFIG['max_tokens']}, chunk_size: {MODEL_CONFIG['safe_chunk_size']})")

    text_tokens = count_tokens(text, MODEL_CONFIG["encoding"])
    
    if text_tokens <= MODEL_CONFIG["safe_chunk_size"]:
        print(f"Processing in single chunk ({text_tokens} tokens)")
        return translate_chunk_with_ollama(text, source_lang, target_lang)
    
    print(f"Text too large ({text_tokens} tokens), splitting into chunks...")
    chunks = split_srt_into_chunks(text, MODEL_CONFIG["safe_chunk_size"], MODEL_CONFIG["encoding"])
    
    print(f"Split into {len(chunks)} chunks")
    
    translated_chunks = []
    
    for i, chunk in enumerate(chunks):
        chunk_tokens = count_tokens(chunk, MODEL_CONFIG["encoding"])
        chunk_info = f"Processing chunk {i+1}/{len(chunks)} ({chunk_tokens} tokens)"
        print(chunk_info)
        
        translated_chunk = translate_chunk_with_ollama(
            chunk, 
            source_lang, 
            target_lang, 
            chunk_info
        )
        
        translated_chunks.append(translated_chunk)
        
        if i < len(chunks) - 1:
            time.sleep(0.5)
    
    final_translation = "\n\n".join(translated_chunks)
    
    print(f"Translation complete: {len(chunks)} chunks combined")
    return final_translation

def extract_text_from_srt(srt_content: str) -> Tuple[List[str], List[Dict]]:
    """Extract translatable text from SRT while preserving structure for reconstruction"""
    
    blocks = re.split(r'\n\s*\n', srt_content.strip())
    
    texts_to_translate = []
    structure_map = []
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        lines = block.split('\n')
        if len(lines) < 2:
            continue
            
        try:
            block_number = lines[0].strip()
            int(block_number)
        except ValueError:
            continue
            
        timestamp_line = lines[1].strip() if len(lines) > 1 else ""
        if not re.match(r'\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', timestamp_line):
            continue
            
        content_lines = lines[2:] if len(lines) > 2 else []
        content = '\n'.join(content_lines).strip()
        
        if not content:
            structure_map.append({
                'block_number': block_number,
                'timestamp': timestamp_line,
                'content': '',
                'text_index': None,
                'has_text': False,
                'original_block': block
            })
            continue
        
        # Extract text from HTML tags
        extracted_texts = []
        
        if '<font' in content:
            font_starts = []
            for match in re.finditer(r'<font[^>]*>', content, re.IGNORECASE):
                font_starts.append(match.start())
            
            used_ranges = set()
            
            for start_pos in font_starts:
                remainder = content[start_pos:]
                
                stack = []
                text_content = ""
                in_text = False
                i = 0
                
                while i < len(remainder):
                    if remainder[i:i+5].lower() == '<font':
                        tag_end = remainder.find('>', i)
                        if tag_end != -1:
                            stack.append('font')
                            i = tag_end + 1
                            in_text = True
                        else:
                            i += 1
                    elif remainder[i:i+7].lower() == '</font>':
                        if stack and stack[-1] == 'font':
                            stack.pop()
                            if not stack:
                                break
                        i += 7
                    elif remainder[i:i+3].lower() == '<b>':
                        i += 3
                    elif remainder[i:i+4].lower() == '</b>':
                        i += 4
                    elif remainder[i] == '<':
                        tag_end = remainder.find('>', i)
                        if tag_end != -1:
                            i = tag_end + 1
                        else:
                            i += 1
                    else:
                        if in_text and stack:
                            text_content += remainder[i]
                        i += 1
                
                if text_content:
                    clean_text = re.sub(r'\s+', ' ', text_content).strip()
                    clean_text = re.sub(r'\{[^}]*\}', '', clean_text).strip()
                    
                    if clean_text and clean_text not in extracted_texts:
                        extracted_texts.append(clean_text)
        
        if not extracted_texts:
            clean_text = re.sub(r'<[^>]+>', '', content)
            clean_text = re.sub(r'\{[^}]*\}', '', clean_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            if clean_text:
                extracted_texts.append(clean_text)
        
        if extracted_texts:
            combined_text = ' '.join(extracted_texts)
            combined_text = re.sub(r'\{[^}]*\}', '', combined_text)
            combined_text = re.sub(r'\s+', ' ', combined_text).strip()
            
            if not combined_text or len(combined_text) < 2:
                structure_map.append({
                    'block_number': block_number,
                    'timestamp': timestamp_line,
                    'content': content,
                    'text_index': None,
                    'has_text': False,
                    'original_block': block
                })
                continue
            
            text_index = len(texts_to_translate)
            texts_to_translate.append(combined_text)
            
            structure_map.append({
                'block_number': block_number,
                'timestamp': timestamp_line,
                'content': content,
                'text_index': text_index,
                'has_text': True,
                'extracted_texts': extracted_texts,
                'original_block': block
            })
        else:
            structure_map.append({
                'block_number': block_number,
                'timestamp': timestamp_line,
                'content': content,
                'text_index': None,
                'has_text': False,
                'original_block': block
            })
    
    return texts_to_translate, structure_map

def reconstruct_srt_from_translations(translated_texts: List[str], structure_map: List[Dict]) -> str:
    """Reconstruct SRT file with translated texts while preserving formatting"""
    result_blocks = []
    
    for struct in structure_map:
        block_number = struct['block_number']
        timestamp = struct['timestamp']
        
        if not struct['has_text']:
            result_blocks.append(struct['original_block'])
        else:
            text_index = struct['text_index']
            if text_index is None or text_index >= len(translated_texts):
                result_blocks.append(struct['original_block'])
                continue
                
            translated_text = translated_texts[text_index]
            original_content = struct['content']
            
            block = f"{block_number}\n{timestamp}\n"
            
            if '<font' in original_content:
                new_content = original_content
                
                # Preserve HTML structure and replace only text
                temp_content = re.sub(r'<[^>]+>', '', original_content)
                temp_content = re.sub(r'\{[^}]*\}', '', temp_content)
                original_text = re.sub(r'\s+', ' ', temp_content).strip()
                
                if original_text:
                    if '<b>' in original_content:
                        # Complex tags with <b>
                        complex_pattern = r'(<font[^>]*><b[^>]*>(?:\{[^}]*\})*(?:<font[^>]*>)?)(.*?)((?:</font>)?(?:\{[^}]*\})*</b></font>)'
                        match = re.search(complex_pattern, original_content, re.DOTALL | re.IGNORECASE)
                        
                        if match:
                            prefix = match.group(1)
                            suffix = match.group(3)
                            new_content = f"{prefix}{translated_text}{suffix}"
                        else:
                            simple_complex_pattern = r'(<font[^>]*><b[^>]*>(?:\{[^}]*\})*)(.*?)((?:\{[^}]*\})*</b></font>)'
                            simple_match = re.search(simple_complex_pattern, original_content, re.DOTALL | re.IGNORECASE)
                            
                            if simple_match:
                                prefix = simple_match.group(1)
                                suffix = simple_match.group(3)
                                new_content = f"{prefix}{translated_text}{suffix}"
                            else:
                                new_content = original_content.replace(original_text, translated_text)
                    else:
                        # Simple tags
                        def replace_font_content(match):
                            tag_start = match.group(1)
                            middle_content = match.group(2)
                            tag_end = match.group(3)
                            
                            if '<' in middle_content:
                                clean_middle = re.sub(r'<[^>]+>', '', middle_content)
                                clean_middle = re.sub(r'\{[^}]*\}', '', clean_middle).strip()
                                if clean_middle:
                                    new_middle = middle_content.replace(clean_middle, translated_text)
                                    return f"{tag_start}{new_middle}{tag_end}"
                            return f"{tag_start}{translated_text}{tag_end}"
                        
                        simple_font_pattern = r'(<font[^>]*>)(.*?)(</font>)'
                        new_content = re.sub(simple_font_pattern, replace_font_content, original_content, count=1, flags=re.DOTALL | re.IGNORECASE)
                
                block += new_content
            else:
                block += translated_text
            
            result_blocks.append(block)
    
    return '\n\n'.join(result_blocks)

def create_text_only_prompt(texts: List[str], source_lang: str, target_lang: str) -> str:
    """Create optimized prompt for text-only translation"""
    
    target_lang_full = "Brazilian Portuguese" if target_lang == "pt-br" else target_lang
    
    prompt = f"""PRECISE SUBTITLE TRANSLATION - ANIME TO BRAZILIAN PORTUGUESE

SPECIFIC CONTEXT:
- Action/adventure anime with supernatural elements
- Temporal references may be symbolic
- "flame on the table completes twelve" = "antes do meio dia" (temporal expression)
- Preserve Japanese/French character names
- Translate power/Stand names poetically

STRICT INSTRUCTIONS FOR AUTHENTIC BRAZILIAN PORTUGUESE:
1. Translate each numbered text to fluent Brazilian Portuguese
2. Consider cultural context and implicit meanings  
3. Use natural Brazilian expressions (NEVER European Portuguese)
4. Maintain terminological consistency
5. For stuttering/hesitation: H-Hold → H-Aguarde, W-What → Q-Que
6. Use "você/vocês" (NEVER "tu"), "xícaras" (NEVER "chávenas"), "ônibus" (NEVER "autocarro")
7. Return ONLY the final translations, one per line

EXAMPLES OF BRAZILIAN VS EUROPEAN PORTUGUESE:
❌ AVOID (European Portuguese): chávenas, autocarro, telemóvel, apanhar, frigorífico
✅ USE (Brazilian Portuguese): xícaras, ônibus, celular, pegar, geladeira

INPUT:
{chr(10).join(f"{i+1}. {text}" for i, text in enumerate(texts))}

OUTPUT IN AUTHENTIC BRAZILIAN PORTUGUESE:"""
    
    return prompt

def translate_text_only_with_ollama(texts: List[str], source_lang: str, target_lang: str) -> List[str]:
    """Translate extracted text only using optimized configuration"""
    if not texts:
        return []
    
    prompt = create_text_only_prompt(texts, source_lang, target_lang)
    prompt_tokens = count_tokens(prompt, MODEL_CONFIG["encoding"])
    print(f"Translating {len(texts)} text segments with {prompt_tokens} tokens using {OLLAMA_MODEL} (HIGH PRECISION)")
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.05,
            "top_p": MODEL_CONFIG["top_p"],             
            "top_k": MODEL_CONFIG["top_k"],               
            "repeat_penalty": MODEL_CONFIG["repeat_penalty"],    
            "num_predict": min(MODEL_CONFIG["max_tokens"] - prompt_tokens - 100, 4096)
        }
    }

    max_retries = 3
    base_delay = 1
    max_delay = 10

    for attempt in range(max_retries):
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
            if response.status_code == 200:
                result = response.json()
                translated = result.get("response", "").strip()
                
                lines = translated.split('\n')
                
                translations = []
                found_translations_start = False
                
                for line in lines:
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    if any(marker in line.upper() for marker in ['TRANSLATION', 'TRADUÇÃO', 'RESPOSTA']):
                        found_translations_start = True
                        continue
                    
                    # Filter translated instructions and meta-information
                    skip_patterns = [
                        r'^(?:as\s+)?instruções?\s+importantes?:?',
                        r'^\d+\.\s*(?:traduza|devolva|mantenha|preserve|use|não\s+inclua)',
                        r'^\d+\.\s*(?:translate|return|keep|preserve|use|do\s+not)',
                        r'important\s+instruções?:?',
                        r'retorne\s+apenas',
                        r'return\s+only',
                        r'uma\s+por\s+linha',
                        r'one\s+per\s+line',
                        r'textos?\s+de\s+entrada',
                        r'input\s+texts?',
                        r'same\s+number\s+of\s+lines',
                        r'mesmo\s+número\s+de\s+linhas',
                        r'^\d+\.$',
                        r'^\d+\s*$',
                        r'^(?:input\s+)?texts?:?\s*$',
                        r'^translations?:?\s*$',
                        r'^tradução|traduções:?\s*$',
                        r'important\s+instructions?',
                        r'texto\s+numerado',
                        r'sound\s+effects',
                        r'efeitos?\s+sonoros?',
                        r'natural.*express',
                        r'original\s+text',
                        r'texto\s+original',
                        r'explanations?',
                        r'explicações?',
                        r'numbering',
                        r'numeração',
                        r'important\s+instrução',
                        r'textos\s+de\s+entrada:?',
                        r'retorne?\s+apenas\s+as\s+traduções',
                        r'return\s+only\s+the\s+translations',
                        r'uma\s+por\s+linha',
                        r'mantenha\s+o\s+mesmo\s+número',
                        r'keep\s+the\s+same\s+number'
                    ]
                    
                    should_skip = any(re.search(pattern, line, re.IGNORECASE) for pattern in skip_patterns)
                    
                    if should_skip:
                        continue
                    
                    if re.match(r'^\d+\.\s+', line):
                        line = re.sub(r'^\d+\.\s+', '', line)
                    
                    if line and len(line) > 0:
                        translations.append(line)
                
                if len(translations) < len(texts):
                    while len(translations) < len(texts):
                        idx = len(translations)
                        translations.append(texts[idx] if idx < len(texts) else "")
                elif len(translations) > len(texts):
                    translations = translations[:len(texts)]
                
                return translations
            else:
                print(f"API Error (attempt {attempt + 1}/{max_retries}): {response.status_code}")
        except Exception as e:
            print(f"API Exception (attempt {attempt + 1}/{max_retries}): {str(e)}")
        
        if attempt < max_retries - 1:
            delay = min(base_delay * (2 ** attempt), max_delay)
            time.sleep(delay)

def translate_srt_optimized(srt_content: str, source_lang: str, target_lang: str) -> str:
    """Optimized translation using evolutionary configuration"""
    print("Using optimized evolutionary configuration...")
    
    if re.search(r'\d+\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', srt_content):
        print("SRT content detected, using SRT translation method...")
        
        texts_to_translate, structure_map = extract_text_from_srt(srt_content)
        
        print(f"Extracted {len(texts_to_translate)} text segments from {len(structure_map)} subtitle blocks")
        
        if not texts_to_translate:
            print("No translatable text found")
            return srt_content
        
        all_translations = translate_texts_with_evolutionary_config(texts_to_translate, source_lang, target_lang)
        
        print("Reconstructing SRT file with evolutionary translated texts...")
        translated_srt = reconstruct_srt_from_translations(all_translations, structure_map)
        
        print(f"EVOLUTIONARY SRT translation complete: {len(all_translations)} texts translated and reinserted")
        return translated_srt
    else:
        print("Simple text detected, translating directly...")
        return translate_simple_text_with_evolutionary_config(srt_content, source_lang, target_lang)

def add_quotes_to_proper_nouns(text: str) -> tuple[str, list]:
    """Add quotes to proper nouns (words starting with capital letters)"""
    import re
    
    added_quotes_positions = []
    
    def replace_proper_noun(match):
        phrase = match.group(0)
        start_pos = match.start()
        
        text_before = text[:start_pos]
        quotes_before = text_before.count('"') % 2
        
        if quotes_before == 1:
            return phrase  # Already quoted
        
        added_quotes_positions.append(start_pos)
        return f'"{phrase}"'
    
    # Pattern to capture proper nouns (1-3 consecutive capitalized words)
    pattern = r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2}\b'
    
    modified_text = re.sub(pattern, replace_proper_noun, text)
    
    return modified_text, added_quotes_positions

def remove_added_quotes(text: str, added_positions: list) -> str:
    """Remove only automatically added quotes if content was preserved"""
    import re
    
    def should_remove_quotes(match):
        quoted_content = match.group(1)
        
        # Remove quotes only if content is properly preserved English proper nouns
        if re.match(r'^[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*$', quoted_content):
            english_words = quoted_content.split()
            if all(word[0].isupper() and word.isalpha() for word in english_words):
                return quoted_content  # Remove quotes
        
        return match.group(0)  # Keep quotes
    
    pattern = r'"([^"]+)"'
    result = re.sub(pattern, should_remove_quotes, text)
    
    return result

def translate_simple_text_with_evolutionary_config(text: str, source_lang: str, target_lang: str) -> str:
    """Translate simple text using evolutionary optimized configuration"""
    
    # Add quotes to proper nouns automatically
    text_with_quotes, added_positions = add_quotes_to_proper_nouns(text)
    
    template_type = MODEL_CONFIG.get('prompt_template', 'stand_authority')
    
    if template_type == 'stand_authority':
        prompt = f"""NEVER translate words inside quotes IF they start with capital letters. Keep quoted capitalized words exactly as they are.

Example:
Input: "John" likes apples → Output: "John" gosta de maçãs
Input: "Mary" is smart → Output: "Mary" é inteligente
Input: He said "hello world" → Output: Ele disse "olá mundo"

Now translate to Portuguese:
{text_with_quotes}

Translation:"""
    else:
        prompt = f"Translate to Brazilian Portuguese: {text_with_quotes}"
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": MODEL_CONFIG["temperature"],
            "top_p": MODEL_CONFIG["top_p"],
            "top_k": MODEL_CONFIG["top_k"],
            "repeat_penalty": MODEL_CONFIG["repeat_penalty"],
            "num_predict": min(MODEL_CONFIG["max_tokens"], 500)
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            translated = result.get("response", "").strip()
            
            if translated:
                translated = re.sub(r'^(?:tradução|translation):\s*', '', translated, flags=re.IGNORECASE)
                translated = translated.strip()
                
                # Remove automatically added quotes
                final_result = remove_added_quotes(translated, added_positions)
                
                return final_result
        
        print(f"API Error: {response.status_code}")
        return text
        
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def translate_texts_with_evolutionary_config(texts: List[str], source_lang: str, target_lang: str) -> List[str]:
    """Translate list of texts using evolutionary configuration in chunks"""
    
    chunk_size = 10  # High precision setting
    text_chunks = [texts[i:i + chunk_size] for i in range(0, len(texts), chunk_size)]
    
    print(f"Processing in {len(text_chunks)} chunks of max {chunk_size} texts each (EVOLUTIONARY CONFIG)")
    
    all_translations = []
    
    for i, chunk in enumerate(text_chunks):
        print(f"Translating chunk {i+1}/{len(text_chunks)} ({len(chunk)} texts) with EVOLUTIONARY settings...")
        
        translated_chunk = translate_text_chunk_with_evolutionary_config(chunk, source_lang, target_lang)
        all_translations.extend(translated_chunk)
        
        if i < len(text_chunks) - 1:
            time.sleep(1)
    
    return all_translations

def translate_text_chunk_with_evolutionary_config(texts: List[str], source_lang: str, target_lang: str) -> List[str]:
    """Translate chunk of texts using evolutionary template"""
    
    prompt = f"""NEVER translate words inside quotes IF they start with capital letters.

DO NOT translate:
- Person names (John, Maria, etc.)
- Place names (Tokyo, New York, etc.) 
- Technique/ability names (especially capitalized ones)
- Any word starting with capital letter

Translate ONLY the numbered texts to Brazilian Portuguese.

TEXTS:
{chr(10).join(f'{i+1}. {text}' for i, text in enumerate(texts))}

TRANSLATIONS:"""
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": MODEL_CONFIG["temperature"],
            "top_p": MODEL_CONFIG["top_p"],
            "top_k": MODEL_CONFIG["top_k"],
            "repeat_penalty": MODEL_CONFIG["repeat_penalty"],
            "num_predict": min(MODEL_CONFIG["max_tokens"], 2000)
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        if response.status_code == 200:
            result = response.json()
            translated = result.get("response", "").strip()
            
            translations = extract_translations_from_evolutionary_response(translated, texts)
            return translations
        
        print(f"API Error: {response.status_code}")
        return texts
        
    except Exception as e:
        print(f"Translation error: {e}")
        return texts

def extract_translations_from_evolutionary_response(response: str, original_texts: List[str]) -> List[str]:
    """Extract translations from model response intelligently"""
    lines = response.split('\n')
    translations = []
    
    # Remove leaked instruction lines
    clean_lines = []
    for line in lines:
        line = line.strip()
        if line and not any(skip in line.lower() for skip in [
            'never translate', 'do not translate', 'person names', 
            'place names', 'technique/ability', 'capital letter', 'translate only', 'texts:', 'translations:'
        ]):
            clean_lines.append(line)
    
    for line in clean_lines:
        if line:
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            if line:
                translations.append(line)
    
    # Ensure same number of translations
    while len(translations) < len(original_texts):
        idx = len(translations)
        if idx < len(original_texts):
            translations.append(original_texts[idx])
        else:
            translations.append("")
    
    return translations[:len(original_texts)]
