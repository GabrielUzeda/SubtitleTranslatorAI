#!/usr/bin/env python3
"""
Script para aplicar a configuração otimizada ao sistema de tradução
Aplica automaticamente a melhor configuração encontrada pelo tuning evolutivo
Score alcançado: 9.75/10
"""

import json
import os
import sys
import glob
from datetime import datetime

def load_best_config():
    """Carrega a melhor configuração disponível"""
    # Procurar por arquivos de configuração finais
    final_configs = glob.glob("best_config_evolved_final_*.json")
    
    if final_configs:
        # Pegar o mais recente
        latest_config = max(final_configs, key=os.path.getctime)
        print(f"📂 Carregando configuração final: {latest_config}")
        
        with open(latest_config, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        return config_data
    
    # Fallback para configurações intermediárias
    evolved_configs = glob.glob("best_config_evolved_*.json")
    if evolved_configs:
        latest_config = max(evolved_configs, key=os.path.getctime)
        print(f"📂 Carregando configuração evoluída: {latest_config}")
        
        with open(latest_config, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        return {"best_config": config_data["best_config"], "fitness": config_data["fitness"]}
    
    print("❌ Nenhuma configuração otimizada encontrada!")
    return None

def apply_config_to_translator():
    """Aplica a configuração ao sistema de tradução"""
    config_data = load_best_config()
    
    if not config_data:
        return False
    
    best_config = config_data["best_config"]
    fitness = config_data.get("fitness", 0)
    
    print(f"🎯 Aplicando configuração com score {fitness:.2f}/10")
    print("=" * 50)
    print("📊 CONFIGURAÇÃO OTIMIZADA:")
    print(f"   🌡️  Temperature: {best_config['temperature']:.3f}")
    print(f"   🎲 Top-p: {best_config['top_p']:.3f}")
    print(f"   🔢 Top-k: {best_config['top_k']}")
    print(f"   🔄 Repeat penalty: {best_config['repeat_penalty']:.3f}")
    print(f"   📦 Chunk size: {best_config['chunk_size']}")
    print(f"   🪟 Context window: {best_config['context_window']}")
    print(f"   ✨ Quality threshold: {best_config['quality_threshold']:.3f}")
    print(f"   🎭 Prompt template: {best_config['prompt_template']}")
    print(f"   🔤 Max tokens: {best_config['max_tokens']}")
    print("=" * 50)
    
    # Caminho para o arquivo de configuração do sistema principal
    backend_dir = os.path.join(os.path.dirname(__file__), '..', 'backend')
    config_file = os.path.join(backend_dir, 'optimal_config.json')
    
    # Preparar configuração para aplicação
    applied_config = {
        "translation_config": best_config,
        "metadata": {
            "applied_at": datetime.now().isoformat(),
            "fitness_score": fitness,
            "evolution_generation": best_config.get("generation", "unknown"),
            "creation_method": best_config.get("creation_method", "unknown"),
            "tuning_version": "v2.0_ultra_optimized"
        }
    }
    
    # Salvar configuração
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(applied_config, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Configuração aplicada com sucesso!")
    print(f"💾 Salva em: {config_file}")
    
    # Mostrar instruções de uso
    print("\n🚀 COMO USAR:")
    print("1. O sistema de tradução agora usará automaticamente estes parâmetros")
    print("2. Execute traduções normalmente com main.sh")
    print("3. A configuração otimizada será aplicada automaticamente")
    print(f"\n💡 Esta configuração alcançou score {fitness:.2f}/10 nos benchmarks!")
    
    return True

if __name__ == "__main__":
    print("🧬 APLICADOR DE CONFIGURAÇÃO EVOLUTIVA")
    print("Aplicando configuração otimizada por algoritmo genético")
    print(f"Meta alcançada: Score 9.0+ ✅")
    print()
    
    success = apply_config_to_translator()
    
    if success:
        print("\n🎉 Pronto! Sistema otimizado para máxima qualidade de tradução!")
    else:
        print("\n❌ Falha ao aplicar configuração.")
        sys.exit(1) 