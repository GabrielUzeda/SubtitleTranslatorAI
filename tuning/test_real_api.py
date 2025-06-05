#!/usr/bin/env python3
"""
Teste da API real do translator para verificar se a configuração otimizada está funcionando
"""

import requests
import json
import time

# URL da API real que o sistema usa
TRANSLATOR_URL = "http://localhost:8000/translate"

def test_with_real_api():
    """Testa usando exatamente a mesma API que o sistema real usa"""
    
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
    
    print("🔬 TESTE COM API REAL DO TRANSLATOR")
    print("Testando configuração otimizada via API port 8000")
    print("=" * 60)
    
    total_score = 0
    max_score = len(critical_tests) * 10
    
    for i, test in enumerate(critical_tests, 1):
        print(f"\n[{i}/{len(critical_tests)}] Testando: {test['name']}")
        print(f"Entrada: '{test['text']}'")
        print(f"Esperado: '{test['expected']}'")
        
        # Criar payload para API real
        payload = {
            "text": test['text'],
            "source_lang": "en",
            "target_lang": "pt-br",
            "use_optimized": True
        }
        
        try:
            start_time = time.time()
            response = requests.post(TRANSLATOR_URL, json=payload, timeout=60)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                translated = result.get("translated_text", "").strip()
                
                print(f"Resultado: '{translated}'")
                print(f"Tempo: {elapsed:.1f}s")
                
                # Mostrar informações da API
                if "processing_info" in result:
                    info = result["processing_info"]
                    print(f"Método: {info.get('translation_method', 'unknown')}")
                    print(f"Tokens entrada: {info.get('input_tokens', 'unknown')}")
                    print(f"Tokens saída: {info.get('output_tokens', 'unknown')}")
                
                # Calcular score
                if test['expected'].lower() in translated.lower():
                    score = 10
                    status = "✅ PERFEITO"
                elif any(word in translated.lower() for word in test['expected'].lower().split()):
                    score = 5
                    status = "🟡 PARCIAL"
                else:
                    score = 0
                    status = "❌ FALHOU"
                
                total_score += score
                print(f"Score: {score}/10 - {status}")
                
            else:
                print(f"❌ Erro na API: {response.status_code}")
                print(f"Resposta: {response.text}")
                
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
        print("⚠️ Configuração precisa de ajustes.")
    
    return final_score

if __name__ == "__main__":
    test_with_real_api() 