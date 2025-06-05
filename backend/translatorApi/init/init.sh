#!/bin/bash
set -e

# Configurações do Ollama
export OLLAMA_HOST=0.0.0.0
export OLLAMA_ORIGINS=*

# Função para detectar e configurar GPU
setup_gpu() {
    echo "Detectando configuração de GPU..."
    
    # Verifica NVIDIA
    if command -v nvidia-smi &> /dev/null; then
        echo "NVIDIA GPU detectada"
        nvidia-smi --query-gpu=gpu_name,memory.total --format=csv,noheader
        return 0
    fi
    
    # Verifica AMD
    if command -v rocm-smi &> /dev/null; then
        echo "AMD GPU detectada"
        rocm-smi --showproductname
        return 0
    fi
    
    # Verifica Intel
    if command -v clinfo &> /dev/null && clinfo | grep -i "intel" &> /dev/null; then
        echo "Intel GPU detectada"
        clinfo | grep "Device Name" | grep -i "intel"
        return 0
    fi
    
    # Fallback para CPU
    echo "Nenhuma GPU detectada, usando CPU"
    return 1
}

# Limpa cache CUDA/OpenCL se existir
if [ -d "/root/.cache/cuda" ]; then
    rm -rf /root/.cache/cuda/*
fi
if [ -d "/root/.cache/opencl" ]; then
    rm -rf /root/.cache/opencl/*
fi

# Configura limites do sistema
ulimit -n 65535
ulimit -u 65535

# Configura GPU
setup_gpu

# Inicia o servidor Ollama
echo "Iniciando servidor Ollama..."
ollama serve &

# Aguarda o servidor estar pronto
echo "Aguardando servidor Ollama..."
until curl -s http://localhost:11434/api/generate -d '{"model":"tibellium/towerinstruct-mistral","prompt":"test"}' > /dev/null 2>&1; do
    sleep 1
done

# Carrega o modelo
echo "Carregando modelo..."
ollama pull tibellium/towerinstruct-mistral

echo "Servidor Ollama iniciado e modelo carregado com sucesso!"
# Monitora o processo Ollama
while true; do
    if ! pgrep -x "ollama" > /dev/null; then
        echo "Erro: Processo Ollama terminou inesperadamente"
        exit 1
    fi
    sleep 5
done
