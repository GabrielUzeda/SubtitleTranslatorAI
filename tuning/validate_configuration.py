#!/usr/bin/env python3
"""
Script de validação da configuração otimizada
Testa a configuração com score 9.75 nos benchmarks críticos
"""

import json
import os
import sys
import requests
import time

# Adicionar o caminho do backend ao sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from translatorApi.app.utils import extract_text_from_srt, reconstruct_srt_from_translations

OLLAMA_URL = "http://localhost:11434/api/generate"

def load_optimal_config():
    """Carrega a configuração otimizada"""
    config_file = os.path.join(os.path.dirname(__file__), '..', 'backend', 'optimal_config.json')
    
    if not os.path.exists(config_file):
        print("❌ Configuração otimizada não encontrada!")
        return None
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    return config_data['translation_config']

def create_prompt_template(prompt_type: str, texts: list) -> str:
    """Cria o prompt usando o template otimizado"""
    base_instruction = f"Traduza cada texto para português brasileiro natural e fluente.\n\nTEXTOS:\n{chr(10).join(f'{i+1}. {text}' for i, text in enumerate(texts))}\n\nTRADUÇÕES:"
    
    if prompt_type == "stand_authority":
        return f"AUTORIDADE EM STANDS: NUNCA traduza nomes de Stands (Silver Chariot, Star Platinum, Hermit Purple). Traduza apenas descrições e diálogos. {base_instruction}"
    else:
        return f"Traduza para português brasileiro: {base_instruction}"

def test_critical_benchmarks(config):
    """Testa os benchmarks mais críticos"""
    critical_tests = [
        {
            "name": "Expressão idiomática temporal",
            "text": "before that flame on the table completes twelve",
            "expected": "antes do meio dia"
        },
        {
            "name": "Preservação de Stand name",
            "text": "Silver Chariot",
            "expected": "Silver Chariot"
        },
        {
            "name": "Stand name composto",
            "text": "Magician's Red",
            "expected": "Magician's Red"
        },
        {
            "name": "Nome de personagem",
            "text": "Jean Pierre Polnareff",
            "expected": "Jean Pierre Polnareff"
        },
        {
            "name": "Gagueira brasileira",
            "text": "W-What are you doing",
            "expected": "Q-Que você está fazendo"
        }
    ]
    
    print(f"🧪 TESTANDO CONFIGURAÇÃO OTIMIZADA")
    print(f"Score nos benchmarks: {config.get('fitness', 'N/A'):.2f}/10")
    print("=" * 60)
    
    total_score = 0
    max_score = len(critical_tests) * 10
    
    for i, test in enumerate(critical_tests, 1):
        print(f"\n[{i}/{len(critical_tests)}] Testando: {test['name']}")
        print(f"Entrada: '{test['text']}'")
        print(f"Esperado: '{test['expected']}'")
        
        # Fazer tradução
        prompt = create_prompt_template(config['prompt_template'], [test['text']])
        
        payload = {
            "model": "tibellium/towerinstruct-mistral",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": config['temperature'],
                "top_p": config['top_p'],
                "top_k": config['top_k'],
                "repeat_penalty": config['repeat_penalty'],
                "num_predict": config['max_tokens']
            }
        }
        
        try:
            start_time = time.time()
            response = requests.post(OLLAMA_URL, json=payload, timeout=60)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                translated = result.get("response", "").strip()
                
                # Extrair tradução
                lines = translated.split('\n')
                translation = ""
                for line in lines:
                    line = line.strip()
                    if line and not any(skip in line.lower() for skip in ['tradução', 'translation']):
                        line = line.lstrip('0123456789. ')
                        if line:
                            translation = line
                            break
                
                print(f"Resultado: '{translation}'")
                print(f"Tempo: {elapsed:.1f}s")
                
                # Calcular score
                if test['expected'].lower() in translation.lower():
                    score = 10
                    status = "✅ PERFEITO"
                elif any(word in translation.lower() for word in test['expected'].lower().split()):
                    score = 5
                    status = "🟡 PARCIAL"
                else:
                    score = 0
                    status = "❌ FALHOU"
                
                total_score += score
                print(f"Score: {score}/10 - {status}")
                
            else:
                print(f"❌ Erro na API: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")
    
    final_score = (total_score / max_score) * 10
    print("\n" + "=" * 60)
    print(f"🏆 SCORE FINAL: {final_score:.1f}/10")
    print(f"📊 Acertos: {total_score}/{max_score} pontos")
    
    if final_score >= 9.0:
        print("🎉 EXCELENTE! Configuração validada com sucesso!")
    elif final_score >= 7.0:
        print("✅ BOM! Configuração funcionando adequadamente.")
    else:
        print("⚠️ Configuração pode precisar de ajustes.")
    
    return final_score

def main():
    print("🔬 VALIDADOR DE CONFIGURAÇÃO EVOLUTIVA")
    print("Testando configuração otimizada por algoritmo genético")
    print()
    
    # Carregar configuração
    config = load_optimal_config()
    if not config:
        sys.exit(1)
    
    print(f"📋 Configuração carregada:")
    print(f"   Temperature: {config['temperature']:.3f}")
    print(f"   Top-p: {config['top_p']:.3f}")
    print(f"   Top-k: {config['top_k']}")
    print(f"   Repeat penalty: {config['repeat_penalty']:.3f}")
    print(f"   Prompt: {config['prompt_template']}")
    print()
    
    # Testar configuração
    score = test_critical_benchmarks(config)
    
    print(f"\n💡 Configuração {'VALIDADA' if score >= 7.0 else 'PRECISA REVISÃO'}!")

if __name__ == "__main__":
    main() 