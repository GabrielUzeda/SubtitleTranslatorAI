#!/usr/bin/env python3
"""
Script para aplicar configuração evoluída automaticamente ao translatorApi
"""

import json
import glob
import os
import sys
import subprocess

def find_best_evolved_config():
    """Encontra a melhor configuração evoluída"""
    config_files = glob.glob("best_config_evolved_*.json")
    if not config_files:
        print("❌ Nenhuma configuração evoluída encontrada!")
        return None
    
    # Pegar o mais recente
    latest_config = max(config_files, key=os.path.getctime)
    
    with open(latest_config, 'r') as f:
        data = json.load(f)
    
    print(f"📁 Configuração encontrada: {latest_config}")
    print(f"🎯 Score: {data['fitness']:.2f}/10")
    print(f"🧬 Testadas: {data['total_configs_tested']} configurações")
    print(f"🔄 Gerações: {data['generations']}")
    
    return data['best_config']

def apply_config_to_translator_api(config):
    """Aplica configuração ao translatorApi"""
    api_config_path = "../backend/translatorApi/config.json"
    
    # Mapear configuração evoluída para formato da API
    api_config = {
        "model": "tibellium/towerinstruct-mistral",
        "temperature": config['temperature'],
        "top_p": config['top_p'],
        "top_k": config['top_k'],
        "repeat_penalty": config['repeat_penalty'],
        "chunk_size": config['chunk_size'],
        "max_tokens": config['max_tokens']
    }
    
    # Determinar template baseado no prompt_template evoluído
    template_map = {
        "contextual": "contextual",
        "precise": "precise", 
        "anime_focused": "cultural",
        "technical": "precise",
        "cultural": "cultural",
        "creative": "contextual"
    }
    
    template = template_map.get(config['prompt_template'], "precise")
    api_config['template'] = template
    
    # Salvar configuração
    with open(api_config_path, 'w') as f:
        json.dump(api_config, f, indent=2)
    
    print(f"✅ Configuração aplicada ao translatorApi:")
    print(f"   Temperature: {config['temperature']:.3f}")
    print(f"   Top-p: {config['top_p']:.3f}")
    print(f"   Top-k: {config['top_k']}")
    print(f"   Repeat penalty: {config['repeat_penalty']:.3f}")
    print(f"   Chunk size: {config['chunk_size']}")
    print(f"   Template: {template}")
    
    return True

def restart_translator_service():
    """Reinicia o serviço de tradução"""
    try:
        print("🔄 Reiniciando serviço de tradução...")
        
        # Parar e reiniciar o Docker Compose
        os.chdir("../backend")
        subprocess.run(["docker", "compose", "restart", "translator"], check=True)
        
        print("✅ Serviço reiniciado com sucesso!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao reiniciar serviço: {e}")
        return False

if __name__ == "__main__":
    print("🚀 APLICANDO CONFIGURAÇÃO EVOLUÍDA AO TRANSLATORAPI")
    print("=" * 60)
    
    # Encontrar melhor configuração
    best_config = find_best_evolved_config()
    if not best_config:
        sys.exit(1)
    
    # Aplicar configuração
    if apply_config_to_translator_api(best_config):
        # Reiniciar serviço
        restart_translator_service()
        print("\n🎉 Configuração evoluída aplicada com sucesso!")
        print("🧪 Teste a nova configuração com um arquivo MKV!")
    else:
        print("❌ Falha ao aplicar configuração!")
        sys.exit(1) 