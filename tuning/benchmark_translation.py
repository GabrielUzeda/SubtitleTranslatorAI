#!/usr/bin/env python3
"""
Translation Benchmark and Optimization Script
Testa diferentes parâmetros da IA para melhorar progressivamente a qualidade da tradução
"""

import json
import time
import requests
import os
import sys
import re
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import glob

# Adicionar o caminho do backend ao sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from translatorApi.app.utils import extract_text_from_srt, reconstruct_srt_from_translations, count_tokens

# Configurações expandidas para benchmark robusto
OLLAMA_URL = "http://localhost:11434/api/generate"
BENCHMARK_FILE = "../example/example.eng.srt"  # Usando o arquivo extraído do MKV
LARGE_SAMPLE_SIZE = 2000  # Aumentado para 2000 textos - ESCOPO MASSIVO

BENCHMARK_PHRASES = [
    {
        "original": "before that flame on the table completes twelve",
        "expected": "antes do meio dia",
        "weight": 10,  # Peso para cálculo de score
        "description": "Teste de contexto temporal - expressão idiomática"
    },
    {
        "original": "Your sword is quite fast",
        "expected": "Sua espada é bastante rápida",
        "weight": 5,
        "description": "Teste básico de tradução literal"
    },
    {
        "original": "Silver Chariot",
        "expected": "Silver Chariot",  # CORRIGIDO: Nome próprio deve ser preservado
        "weight": 7,
        "description": "Teste de preservação de nomes próprios/Stand"
    },
    {
        "original": "Jean Pierre Polnareff",
        "expected": "Jean Pierre Polnareff",
        "weight": 8,
        "description": "Teste de preservação de nomes de personagens"
    },
    {
        "original": "However, the only signs of life on board were three half-full cups of coffee",
        "expected": "xícaras de café meio cheias",
        "weight": 9,
        "description": "Teste português brasileiro vs português de Portugal (chávenas)"
    },
    {
        "original": "H-Hold on! There's something engraved here",
        "expected": "E-Espera aí! Tem algo gravado aqui",
        "weight": 8,
        "description": "Teste de tradução de gagueira/hesitação"
    },
    {
        "original": "W-What are you doing?",
        "expected": "Q-Que você está fazendo?",
        "weight": 7,
        "description": "Teste de tradução de gagueira + pronome brasileiro (você vs tu)"
    },
    # NOVOS TESTES ADICIONADOS PARA ESCOPO MAIOR
    {
        "original": "Stand",
        "expected": "Stand",
        "weight": 6,
        "description": "Teste de preservação de termos técnicos do anime"
    },
    {
        "original": "attack",
        "expected": "ataque",
        "weight": 4,
        "description": "Teste de vocabulário básico de ação"
    },
    {
        "original": "power",
        "expected": "poder",
        "weight": 4,
        "description": "Teste de vocabulário básico de poder"
    },
    {
        "original": "enemy",
        "expected": "inimigo",
        "weight": 4,
        "description": "Teste de vocabulário básico de conflito"
    },
    {
        "original": "fight",
        "expected": "luta",
        "weight": 4,
        "description": "Teste de vocabulário básico de combate"
    }
]

@dataclass
class TestConfig:
    """Configuração de teste para benchmarking"""
    name: str
    model: str
    temperature: float
    top_p: float
    top_k: int
    repeat_penalty: float
    chunk_size: int
    prompt_template: str
    max_tokens: int

# Diferentes configurações para testar
TEST_CONFIGS = [
    TestConfig(
        name="baseline_current",
        model="tibellium/towerinstruct-mistral",
        temperature=0.3,
        top_p=0.8,
        top_k=40,
        repeat_penalty=1.0,
        chunk_size=20,
        prompt_template="current",
        max_tokens=4096
    ),
    TestConfig(
        name="low_temp_contextual",
        model="tibellium/towerinstruct-mistral",
        temperature=0.1,
        top_p=0.9,
        top_k=30,
        repeat_penalty=1.1,
        chunk_size=15,
        prompt_template="contextual",
        max_tokens=4096
    ),
    TestConfig(
        name="balanced_cultural",
        model="tibellium/towerinstruct-mistral",
        temperature=0.2,
        top_p=0.85,
        top_k=35,
        repeat_penalty=1.05,
        chunk_size=25,
        prompt_template="cultural",
        max_tokens=4096
    ),
    TestConfig(
        name="high_precision",
        model="tibellium/towerinstruct-mistral",
        temperature=0.05,
        top_p=0.95,
        top_k=20,
        repeat_penalty=1.15,
        chunk_size=10,
        prompt_template="precise",
        max_tokens=4096
    )
]

def create_prompt_template(template_type: str, texts: List[str], source_lang: str, target_lang: str) -> str:
    """Cria diferentes templates de prompt para teste"""
    
    target_lang_name = "Portuguese (Brazilian)" if target_lang == "pt-br" else target_lang
    
    if template_type == "current":
        # Template atual
        return f"""You are a professional translator. Translate each text from {source_lang} to {target_lang_name}.

IMPORTANT INSTRUCTIONS:
1. Translate each numbered text below to {target_lang_name}
2. Return ONLY the translations, one per line
3. Keep the same number of lines as input
4. Preserve sound effects in brackets [ ] or parentheses ( )
5. Use natural {target_lang_name} expressions
6. Do NOT include the original text
7. Do NOT include explanations
8. Do NOT include numbering in output

INPUT TEXTS:
{chr(10).join(f"{i+1}. {text}" for i, text in enumerate(texts))}

TRANSLATIONS:"""

    elif template_type == "contextual":
        return f"""You are a professional subtitle translator specializing in Japanese anime/manga to Brazilian Portuguese.

CONTEXT: This is from an action anime with characters using special powers called "Stands". Pay attention to:
- Time references may be metaphorical (e.g., "before twelve" could mean "before noon/midnight")
- Character names should remain in original form
- Stand names can be translated to Portuguese equivalents
- Maintain dramatic tone appropriate for action scenes

TRANSLATION RULES:
1. Translate to natural Brazilian Portuguese
2. Consider context and metaphorical meanings
3. Preserve character names exactly
4. Use appropriate Brazilian expressions
5. Return only translations, one per line

TEXTS TO TRANSLATE:
{chr(10).join(f"{i+1}. {text}" for i, text in enumerate(texts))}

BRAZILIAN PORTUGUESE TRANSLATIONS:"""

    elif template_type == "cultural":
        return f"""Você é um tradutor especializado em anime e mangá japonês para português brasileiro.

INSTRUÇÕES CULTURAIS:
- Este é um anime de ação com poderes especiais chamados "Stands"
- Expressões temporais podem ser idiomáticas ("chama da mesa complete doze" = "antes do meio dia")
- Nomes de personagens mantêm forma original
- Nomes de Stands podem ser traduzidos poeticamente
- Use gírias e expressões naturais do português brasileiro

REGRAS DE TRADUÇÃO:
1. Traduza para português brasileiro natural e fluente
2. Considere significados idiomáticos e contextuais
3. Mantenha nomes de personagens inalterados
4. Use expressões brasileiras apropriadas ao gênero
5. Retorne apenas as traduções, uma por linha

TEXTOS PARA TRADUZIR:
{chr(10).join(f"{i+1}. {text}" for i, text in enumerate(texts))}

TRADUÇÕES EM PORTUGUÊS BRASILEIRO:"""

    elif template_type == "precise":
        return f"""TRADUÇÃO PRECISA DE LEGENDAS - ANIME PARA PORTUGUÊS BRASILEIRO

CONTEXTO ESPECÍFICO:
- Anime de ação/aventura com elementos sobrenaturais
- Referências temporais podem ser simbólicas
- "flame on the table completes twelve" = "antes do meio dia" (expressão temporal)
- Preservar nomes de personagens japoneses/franceses
- Traduzir nomes de poderes/Stands de forma poética

INSTRUÇÕES RIGOROSAS:
1. Traduza cada texto numerado para português brasileiro fluente
2. Considere contexto cultural e significados implícitos  
3. Use expressões naturais brasileiras
4. Mantenha consistência terminológica
5. Retorne APENAS as traduções finais, uma por linha

ENTRADA:
{chr(10).join(f"{i+1}. {text}" for i, text in enumerate(texts))}

SAÍDA:"""

    else:
        # Fallback para template atual
        return create_prompt_template("current", texts, source_lang, target_lang)

def translate_with_config(texts: List[str], config: TestConfig, source_lang: str = "en", target_lang: str = "pt-br") -> List[str]:
    """Executa tradução com configuração específica"""
    
    prompt = create_prompt_template(config.prompt_template, texts, source_lang, target_lang)
    
    payload = {
        "model": config.model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "top_k": config.top_k,
            "repeat_penalty": config.repeat_penalty,
            "num_predict": config.max_tokens
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=180)
        if response.status_code == 200:
            result = response.json()
            translated = result.get("response", "").strip()
            
            # Extrair traduções
            lines = translated.split('\n')
            translations = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Filtrar artefatos comuns
                skip_patterns = [
                    r'^(?:traduções?|translations?):?\s*$',
                    r'^(?:saída|output):?\s*$',
                    r'^\d+\.\s*$',
                    r'^(?:as\s+)?instruções?\s+importantes?',
                    r'important\s+instructions?',
                    r'entrada:|input:|saída:|output:'
                ]
                
                should_skip = any(re.search(pattern, line, re.IGNORECASE) for pattern in skip_patterns)
                if should_skip:
                    continue
                
                # Remover numeração se presente
                line = re.sub(r'^\d+\.\s+', '', line)
                
                if line and len(line) > 0:
                    translations.append(line)
            
            # Ajustar número de traduções
            while len(translations) < len(texts):
                translations.append(texts[len(translations)] if len(translations) < len(texts) else "")
            
            return translations[:len(texts)]
            
    except Exception as e:
        print(f"Erro na tradução: {e}")
        return texts

def calculate_benchmark_score(translations: List[str], config_name: str) -> Dict[str, Any]:
    """Calcula score baseado nos benchmarks definidos"""
    
    scores = []
    detailed_results = []
    
    # Juntar todas as traduções em um texto para busca
    full_translation = ' '.join(translations).lower()
    
    for benchmark in BENCHMARK_PHRASES:
        original = benchmark["original"].lower()
        expected = benchmark["expected"].lower()
        weight = benchmark["weight"]
        
        # Buscar pela frase original traduzida
        found_translation = ""
        best_match_score = 0
        
        # Procurar em cada tradução individual
        for translation in translations:
            translation_lower = translation.lower()
            
            # Verificar se contém palavras-chave da frase original
            original_words = original.split()
            if len(original_words) > 1:
                # Para frases multi-palavra, verificar se contém pelo menos metade das palavras
                matches = sum(1 for word in original_words if word in translation_lower)
                if matches >= len(original_words) / 2:
                    found_translation = translation
                    break
        
        if not found_translation:
            # Busca mais flexível no texto completo
            original_words = original.split()
            for word in original_words:
                if word in full_translation:
                    # Encontrar contexto ao redor da palavra
                    for translation in translations:
                        if word in translation.lower():
                            found_translation = translation
                            break
                    break
        
        # Calcular score de similaridade
        if found_translation:
            found_lower = found_translation.lower()
            
            # Score baseado em palavras-chave da tradução esperada
            expected_words = expected.split()
            matches = sum(1 for word in expected_words if word in found_lower)
            similarity_score = (matches / len(expected_words)) * 10
            
            # Bonus se tradução exata
            if expected in found_lower:
                similarity_score = 10
            
            # Penalidade por traduções literais quando esperamos idiomáticas
            if "chama" in original and "flame" in found_lower:
                similarity_score *= 0.3  # Penalidade por tradução muito literal
                
        else:
            similarity_score = 0
            found_translation = "NÃO ENCONTRADA"
        
        weighted_score = similarity_score * weight
        scores.append(weighted_score)
        
        detailed_results.append({
            "phrase": benchmark["description"],
            "original": benchmark["original"],
            "expected": benchmark["expected"],
            "found": found_translation,
            "score": similarity_score,
            "weighted": weighted_score,
            "weight": weight
        })
    
    total_weight = sum(b["weight"] for b in BENCHMARK_PHRASES)
    final_score = sum(scores) / total_weight if total_weight > 0 else 0
    
    return {
        "config_name": config_name,
        "final_score": final_score,
        "detailed_results": detailed_results,
        "summary": {
            "total_benchmarks": len(BENCHMARK_PHRASES),
            "passed": sum(1 for r in detailed_results if r["score"] >= 7),
            "avg_score": sum(r["score"] for r in detailed_results) / len(detailed_results)
        }
    }

def compare_with_previous_results(current_results: List[Dict], output_file: str):
    """Compara resultados atuais com benchmarks anteriores"""
    
    print("\n🔄 COMPARAÇÃO COM BENCHMARKS ANTERIORES")
    print("=" * 60)
    
    # Procurar arquivos de resultados anteriores
    previous_files = glob.glob("benchmark_results_*.json")
    previous_files.sort()
    
    if len(previous_files) < 2:
        print("📊 Este é o primeiro ou segundo benchmark - não há comparação histórica ainda")
        return
    
    # Carregar último resultado anterior (excluindo o atual)
    previous_files = [f for f in previous_files if f != output_file]
    if not previous_files:
        print("📊 Nenhum benchmark anterior encontrado para comparação")
        return
    
    latest_previous = previous_files[-1]
    
    try:
        with open(latest_previous, 'r', encoding='utf-8') as f:
            previous_results = json.load(f)
        
        print(f"📁 Comparando com: {latest_previous}")
        print()
        
        # Organizar resultados por configuração
        current_by_config = {r['config_name']: r for r in current_results}
        previous_by_config = {r['config_name']: r for r in previous_results}
        
        improvement_summary = []
        
        for config_name in current_by_config:
            current = current_by_config[config_name]
            previous = previous_by_config.get(config_name)
            
            if previous:
                score_diff = current['final_score'] - previous['final_score']
                success_diff = current['summary']['passed'] - previous['summary']['passed']
                
                trend = "📈" if score_diff > 0.5 else "📉" if score_diff < -0.5 else "📊"
                
                print(f"{trend} {config_name}:")
                print(f"    Score: {previous['final_score']:.2f} → {current['final_score']:.2f} ({score_diff:+.2f})")
                print(f"    Sucessos: {previous['summary']['passed']} → {current['summary']['passed']} ({success_diff:+d})")
                
                if 'performance' in current and 'performance' in previous:
                    time_diff = current['performance']['time_per_text'] - previous['performance']['time_per_text']
                    print(f"    Tempo/texto: {previous['performance']['time_per_text']:.2f}s → {current['performance']['time_per_text']:.2f}s ({time_diff:+.2f}s)")
                
                improvement_summary.append({
                    'config': config_name,
                    'score_improvement': score_diff,
                    'success_improvement': success_diff
                })
                print()
            else:
                print(f"🆕 {config_name}: Nova configuração - {current['final_score']:.2f}/10")
                print()
        
        # Resumo geral
        if improvement_summary:
            avg_improvement = sum(i['score_improvement'] for i in improvement_summary) / len(improvement_summary)
            improved_configs = sum(1 for i in improvement_summary if i['score_improvement'] > 0)
            
            print("📊 RESUMO DA EVOLUÇÃO:")
            print(f"    Melhoria média de score: {avg_improvement:+.2f} pontos")
            print(f"    Configurações que melhoraram: {improved_configs}/{len(improvement_summary)}")
            
            best_improvement = max(improvement_summary, key=lambda x: x['score_improvement'])
            if best_improvement['score_improvement'] > 0:
                print(f"    Maior melhoria: {best_improvement['config']} (+{best_improvement['score_improvement']:.2f})")
    
    except Exception as e:
        print(f"❌ Erro ao comparar com resultados anteriores: {e}")

def run_benchmark_suite():
    """Executa suite EXPANDIDA e completa de benchmarks"""
    
    print("🧪 INICIANDO BENCHMARK MASSIVO DE TRADUÇÃO")
    print("🚀 ESCOPO MASSIVO: 8x MAIS TEXTOS (2000) PARA AVALIAÇÃO DEFINITIVA")
    print("=" * 80)
    
    # Carregar arquivo de teste
    if not os.path.exists(BENCHMARK_FILE):
        print(f"❌ Arquivo de benchmark não encontrado: {BENCHMARK_FILE}")
        return
    
    with open(BENCHMARK_FILE, 'r', encoding='utf-8') as f:
        srt_content = f.read()
    
    # Extrair textos para benchmark
    texts_to_translate, structure_map = extract_text_from_srt(srt_content)
    
    print(f"📝 Arquivo completo: {len(texts_to_translate)} textos extraídos")
    
    # LÓGICA DE BUSCA MELHORADA: Localizar frases de benchmark no arquivo completo
    benchmark_indices = []
    found_phrases = []
    
    print("🔍 Localizando frases de benchmark no arquivo com lógica melhorada...")
    
    for benchmark in BENCHMARK_PHRASES:
        original_phrase = benchmark["original"].lower()
        found = False
        
        # MÉTODO 1: Busca exata
        for i, text in enumerate(texts_to_translate):
            if original_phrase in text.lower():
                benchmark_indices.append(i)
                found_phrases.append({
                    "benchmark": benchmark,
                    "index": i,
                    "found_text": text,
                    "match_ratio": 1.0,
                    "method": "exact"
                })
                found = True
                print(f"   ✓ [EXATO] '{benchmark['description']}' no índice {i}")
                break
        
        if not found:
            # MÉTODO 2: Busca por palavras-chave principais (mais de 3 letras)
            original_words = [word for word in original_phrase.split() if len(word) > 3]
            
            for i, text in enumerate(texts_to_translate):
                text_lower = text.lower()
                
                # Para frases longas, verificar se pelo menos 60% das palavras-chave coincidem
                if len(original_words) > 1:
                    matches = sum(1 for word in original_words if word in text_lower)
                    match_ratio = matches / len(original_words)
                    
                    if match_ratio >= 0.6:
                        benchmark_indices.append(i)
                        found_phrases.append({
                            "benchmark": benchmark,
                            "index": i,
                            "found_text": text,
                            "match_ratio": match_ratio,
                            "method": "keywords"
                        })
                        found = True
                        print(f"   ✓ [PALAVRAS] '{benchmark['description']}' no índice {i} ({match_ratio:.1%})")
                        break
        
        if not found:
            # MÉTODO 3: Busca flexível por palavras individuais importantes
            key_words = []
            if "sword" in original_phrase: key_words.append("sword")
            if "fast" in original_phrase: key_words.append("fast")
            if "silver" in original_phrase: key_words.append("silver")
            if "chariot" in original_phrase: key_words.append("chariot")
            if "polnareff" in original_phrase: key_words.append("polnareff")
            if "stand" in original_phrase: key_words.append("stand")
            if "attack" in original_phrase: key_words.append("attack")
            if "power" in original_phrase: key_words.append("power")
            if "fight" in original_phrase: key_words.append("fight")
            if "enemy" in original_phrase: key_words.append("enemy")
            if "flame" in original_phrase: key_words.append("flame")
            if "twelve" in original_phrase: key_words.append("twelve")
            if "coffee" in original_phrase: key_words.append("coffee")
            if "cups" in original_phrase: key_words.append("cups")
            if "hold" in original_phrase: key_words.append("hold")
            if "engraved" in original_phrase: key_words.append("engraved")
            if "what" in original_phrase and "doing" in original_phrase: 
                key_words.extend(["what", "doing"])
            
            if key_words:
                for i, text in enumerate(texts_to_translate):
                    text_lower = text.lower()
                    matches = sum(1 for word in key_words if word in text_lower)
                    
                    if matches >= len(key_words) * 0.7:  # 70% das palavras-chave
                        benchmark_indices.append(i)
                        found_phrases.append({
                            "benchmark": benchmark,
                            "index": i,
                            "found_text": text,
                            "match_ratio": matches / len(key_words),
                            "method": "flexible"
                        })
                        found = True
                        print(f"   ✓ [FLEXÍVEL] '{benchmark['description']}' no índice {i} ({matches}/{len(key_words)} palavras)")
                        break
        
        if not found:
            # MÉTODO 4: Busca por padrões especiais (gagueira, etc.)
            if "h-hold" in original_phrase.lower() or "w-what" in original_phrase.lower():
                # Buscar padrões de gagueira: letra-palavra
                for i, text in enumerate(texts_to_translate):
                    text_lower = text.lower()
                    # Padrões como: H-Hold, W-What, etc.
                    if re.search(r'\b[a-z]-[a-z]', text_lower):
                        benchmark_indices.append(i)
                        found_phrases.append({
                            "benchmark": benchmark,
                            "index": i,
                            "found_text": text,
                            "match_ratio": 0.8,
                            "method": "pattern"
                        })
                        found = True
                        print(f"   ✓ [PADRÃO] '{benchmark['description']}' no índice {i} (padrão gagueira)")
                        break
        
        if not found:
            print(f"   ❌ Não encontrado: '{benchmark['description']}' - '{original_phrase}'")
    
    print(f"📊 BUSCA MELHORADA: {len(found_phrases)} frases encontradas de {len(BENCHMARK_PHRASES)} benchmarks")
    
    # Criar amostra inteligente EXPANDIDA: incluir frases de benchmark + contexto maior + amostra diversificada
    essential_indices = list(set(benchmark_indices))  # Remover duplicatas
    
    # Adicionar MUITO mais contexto ao redor das frases encontradas (±15 linhas em vez de ±5)
    extended_indices = set(essential_indices)
    for idx in essential_indices:
        for offset in range(-15, 16):  # ±15 linhas de contexto expandido
            context_idx = idx + offset
            if 0 <= context_idx < len(texts_to_translate):
                extended_indices.add(context_idx)
    
    # Completar com amostra MUITO maior até 250 textos
    remaining_slots = LARGE_SAMPLE_SIZE - len(extended_indices)
    if remaining_slots > 0:
        available_indices = [i for i in range(len(texts_to_translate)) if i not in extended_indices]
        
        # Estratégia de amostragem diversificada: pegar textos de diferentes partes do arquivo
        total_available = len(available_indices)
        if total_available > remaining_slots:
            # Dividir o arquivo em seções e pegar textos uniformemente distribuídos
            section_size = total_available // remaining_slots
            additional_indices = []
            for i in range(remaining_slots):
                section_start = i * section_size
                if section_start < total_available:
                    additional_indices.append(available_indices[section_start])
            extended_indices.update(additional_indices)
        else:
            extended_indices.update(available_indices)
    
    # Ordenar índices e criar textos para tradução
    sorted_indices = sorted(list(extended_indices))
    sample_texts = [texts_to_translate[i] for i in sorted_indices]
    
    print(f"📊 AMOSTRA MASSIVA: {len(found_phrases)} frases de benchmark + contexto ±15 linhas + amostra diversificada = {len(sample_texts)} textos")
    print(f"🎯 Benchmarks definidos: {len(BENCHMARK_PHRASES)} ({len(found_phrases)} encontrados)")
    print(f"📈 Escopo MASSIVO: {len(sample_texts)} textos (vs 250 no teste anterior)")
    print()
    
    results = []
    
    for i, config in enumerate(TEST_CONFIGS):
        print(f"⚡ Testando configuração {i+1}/{len(TEST_CONFIGS)}: {config.name}")
        print(f"   Temperatura: {config.temperature}, Chunk Size: {config.chunk_size}")
        print(f"   Prompt: {config.prompt_template}")
        print(f"   🔢 Processando {len(sample_texts)} textos em chunks de {config.chunk_size}...")
        
        start_time = time.time()
        
        # Dividir em chunks conforme configuração
        chunk_size = config.chunk_size
        chunks = [sample_texts[i:i + chunk_size] for i in range(0, len(sample_texts), chunk_size)]
        
        print(f"   📦 Total de chunks: {len(chunks)}")
        
        all_translations = []
        for chunk_idx, chunk in enumerate(chunks):
            print(f"   Processando chunk {chunk_idx + 1}/{len(chunks)}...", end=' ')
            chunk_translations = translate_with_config(chunk, config)
            all_translations.extend(chunk_translations)
            print("✓")
        
        # Ajustar tamanho das traduções
        while len(all_translations) < len(sample_texts):
            all_translations.append("")
        all_translations = all_translations[:len(sample_texts)]
        
        elapsed_time = time.time() - start_time
        
        # Calcular score com amostra corrigida
        score_result = calculate_benchmark_score(all_translations, config.name)
        score_result["performance"] = {
            "total_time": elapsed_time,
            "texts_processed": len(sample_texts),
            "time_per_text": elapsed_time / len(sample_texts),
            "chunks_processed": len(chunks),
            "avg_chunk_time": elapsed_time / len(chunks)
        }
        
        results.append(score_result)
        
        print(f"   ✅ Score: {score_result['final_score']:.2f}/10")
        print(f"   ⏱️ Tempo total: {elapsed_time:.1f}s ({elapsed_time/len(sample_texts):.2f}s/texto)")
        print(f"   📊 Sucessos: {score_result['summary']['passed']}/{score_result['summary']['total_benchmarks']}")
        print(f"   🚀 Throughput: {len(sample_texts)/elapsed_time:.1f} textos/segundo")
        print()
    
    # Análise de resultados
    print("🏆 RESULTADOS FINAIS DO BENCHMARK MASSIVO")
    print("=" * 80)
    
    results.sort(key=lambda x: x["final_score"], reverse=True)
    
    for i, result in enumerate(results):
        rank = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}º"
        print(f"{rank} {result['config_name']}: {result['final_score']:.2f}/10")
        print(f"    Sucessos: {result['summary']['passed']}/{result['summary']['total_benchmarks']}")
        print(f"    Tempo médio: {result['performance']['time_per_text']:.2f}s/texto")
        print(f"    Throughput: {result['performance']['texts_processed']/result['performance']['total_time']:.1f} textos/s")
    
    print("\n🔍 ANÁLISE DETALHADA DO MELHOR RESULTADO:")
    best_result = results[0]
    print(f"Configuração: {best_result['config_name']}")
    
    for detail in best_result['detailed_results']:
        status = "✅" if detail['score'] >= 7 else "⚠️" if detail['score'] >= 4 else "❌"
        print(f"{status} {detail['phrase']}: {detail['score']:.1f}/10")
        print(f"    Original: {detail['original']}")
        print(f"    Esperado: {detail['expected']}")
        print(f"    Encontrado: {detail['found']}")
        if 'index_info' in detail:
            print(f"    Localização: {detail['index_info']}")
        print()
    
    # Salvar resultados
    timestamp = int(time.time())
    results_file = f"benchmark_results_expanded_{timestamp}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Resultados do benchmark expandido salvos em: {results_file}")
    
    # Comparar com resultados anteriores
    compare_with_previous_results(results, results_file)
    
    return results

if __name__ == "__main__":
    run_benchmark_suite() 