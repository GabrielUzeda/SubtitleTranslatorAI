# SubtitleTranslatorAI

**🎬 Tradutor de Legendas com IA para Arquivos MKV**

Uma aplicação completa com interface gráfica para traduzir legendas de arquivos MKV usando inteligência artificial. O projeto oferece tanto uma interface de linha de comando quanto uma GUI em Electron para facilitar o uso.

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Características](#-características)
- [Requisitos do Sistema](#-requisitos-do-sistema)
- [Instalação dos Requisitos](#-instalação-dos-requisitos)
- [Instalação e Uso](#-instalação-e-uso)
- [Interface Gráfica (GUI)](#-interface-gráfica-gui)
- [Linha de Comando](#-linha-de-comando)
- [Configuração GPU NVIDIA](#-configuração-gpu-nvidia)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Solução de Problemas](#-solução-de-problemas)
- [TODO](#-todo)
- [Licença](#-licença)

## 🎯 Visão Geral

O SubtitleTranslatorAI automatiza o processo de tradução de legendas em arquivos MKV usando modelos de IA. A aplicação:

- Extrai legendas automaticamente de arquivos MKV
- Traduz o conteúdo usando modelos de linguagem avançados (LLM)
- Preserva formatação e timing das legendas
- Oferece interface gráfica amigável e linha de comando
- Suporta processamento em lote
- Utiliza Docker para isolamento e facilidade de configuração

## ✨ Características

- **🖥️ Interface Gráfica:** Aplicação Electron com design moderno
- **⚡ Verificação de Pré-requisitos:** Validação automática de dependências
- **🤖 IA Avançada:** Usa modelos Ollama para traduções de alta qualidade  
- **🎬 Suporte MKV:** Manipulação nativa de arquivos Matroska
- **📁 Processamento Flexível:** Seleção de faixas específicas ou processamento completo
- **🐳 Containerizado:** Execução isolada via Docker
- **🎮 Aceleração GPU:** Suporte para NVIDIA, AMD e Intel GPUs
- **📊 Feedback em Tempo Real:** Acompanhamento do progresso de tradução

## 💻 Requisitos do Sistema

### Sistema Operacional
- **Linux** (testado em Ubuntu, Fedora, Debian, Arch)
- Windows (planejado para versões futuras)
- macOS (planejado para versões futuras)

### Dependências Obrigatórias

#### Core do Sistema
- **🐳 Docker Engine** (v20.10+)
- **🐳 Docker Compose** (v2.0+)
- **💻 Bash** (v4.0+)
- **🌐 curl** - download de arquivos
- **📝 jq** - parser JSON
- **🔍 findutils** - utilitários de busca
- **📝 sed** - editor de stream
- **📄 file** - identificador de tipos
- **🔍 grep** - busca de texto

#### Processamento de Mídia
- **🎬 mkvtoolnix** (mkvmerge, mkvextract)
- **🎥 FFmpeg** (ffmpeg, ffprobe)

#### Utilitários de Rede
- **🌐 netstat** OU **ss** (pelo menos um)

#### Opcionais (para GPU)
- **🎮 nvidia-smi** (GPUs NVIDIA)
- **🎮 rocm-smi** (GPUs AMD)
- **🎮 lspci** (detecção geral de hardware)

## 🔧 Instalação dos Requisitos

### Ubuntu/Debian
```bash
# Atualizar repositórios
sudo apt-get update

# Instalar dependências básicas
sudo apt-get install -y docker.io docker-compose mkvtoolnix ffmpeg jq curl net-tools file findutils sed grep bash

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER
newgrp docker

# Verificar instalação
docker --version
docker compose version
```

### Fedora/RHEL/CentOS
```bash
# Instalar dependências
sudo dnf install -y docker docker-compose mkvtoolnix ffmpeg jq curl net-tools file findutils sed grep bash

# Habilitar e iniciar Docker
sudo systemctl enable docker
sudo systemctl start docker

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER
newgrp docker
```

### Arch Linux
```bash
# Instalar dependências
sudo pacman -S docker docker-compose mkvtoolnix ffmpeg jq curl net-tools file findutils sed grep bash

# Habilitar e iniciar Docker
sudo systemctl enable docker
sudo systemctl start docker

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER
newgrp docker
```

### macOS (via Homebrew)
```bash
# Instalar dependências (Docker Desktop separadamente)
brew install mkvtoolnix ffmpeg jq curl

# Docker Desktop deve ser instalado separadamente
# Download: https://www.docker.com/products/docker-desktop
```

## 🚀 Instalação e Uso

### Método 1: AppImage (Recomendado)
1. **Baixar** o AppImage da seção de releases
2. **Tornar executável:**
   ```bash
   chmod +x SubtitleTranslatorAI-GUI-1.0.0.AppImage
   ```
3. **Executar:**
   ```bash
   ./SubtitleTranslatorAI-GUI-1.0.0.AppImage
   ```

### Método 2: Compilar do Código Fonte
1. **Clonar o repositório:**
   ```bash
   git clone https://github.com/seu-usuario/SubtitleTranslatorAI.git
   cd SubtitleTranslatorAI
   ```

2. **Configurar backend:**
   ```bash
   cd backend/tools
   ./setup.sh
   ```

3. **Compilar GUI:**
   ```bash
   cd ../../frontend
   ./setup.sh
   ./build.sh --target linux
   ```

## 🖥️ Interface Gráfica (GUI)

### Primeiros Passos
1. **Verificar Pré-requisitos:**
   - Clique em "Check Prerequisites"
   - Aguarde a verificação completa
   - Instale dependências faltantes se necessário

2. **Selecionar Arquivo:**
   - Clique em "Browse" 
   - Escolha um arquivo MKV

3. **Configurar Opções:**
   - **Select Mode:** Seleciona automaticamente a melhor legenda
   - **All Mode:** Processa todas as legendas encontradas

4. **Executar:**
   - Clique em "Execute"
   - Acompanhe o progresso em tempo real

### Recursos da GUI
- **✅ Validação de Pré-requisitos:** Impede execução sem dependências
- **📁 Navegador de Arquivos:** Seleção fácil de arquivos MKV
- **⚙️ Configurações Flexíveis:** Múltiplos modos de processamento
- **📊 Output em Tempo Real:** Acompanhamento detalhado do progresso
- **💾 Histórico:** Salvar e revisar execuções anteriores

## ⌨️ Linha de Comando

### Configuração Inicial
```bash
cd backend/tools
./setup.sh  # Configura portas, GPU e dependências
```

### Uso Básico
```bash
cd backend
./main.sh [opções] arquivo.mkv
```

### Opções Disponíveis
- `--select` - Seleciona automaticamente a melhor legenda (padrão)
- `--all` - Processa todas as legendas
- `--help` - Mostra ajuda completa

### Exemplos
```bash
# Traduzir melhor legenda automaticamente
./main.sh --select "Filme.mkv"

# Processar todas as legendas
./main.sh --all "Serie_S01E01.mkv"

# Múltiplos arquivos
./main.sh --select *.mkv
```

## 🎮 Configuração GPU NVIDIA

Para melhor performance com GPUs NVIDIA, instale o NVIDIA Container Toolkit:

### Ubuntu/Debian
```bash
# Configurar repositório
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Instalar
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configurar Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Fedora/RHEL/CentOS
```bash
# Configurar repositório
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
  sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo

# Instalar
sudo dnf install -y nvidia-container-toolkit

# Configurar Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Verificar Instalação
```bash
# Testar acesso à GPU
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi
```

**📖 Documentação Completa:** [NVIDIA Container Toolkit Installation Guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

## 📁 Estrutura do Projeto

```
SubtitleTranslatorAI/
├── 📁 backend/                 # API e lógica de processamento
│   ├── 📁 tools/              # Scripts de configuração
│   │   └── setup.sh           # Configuração automática do sistema
│   ├── 📁 translatorApi/      # API de tradução
│   ├── main.sh                # Script principal
│   └── docker-compose.yml     # Configuração de containers
├── 📁 frontend/               # Interface gráfica Electron
│   ├── 📁 src/               # Código fonte da GUI
│   ├── 📁 assets/            # Ícones e recursos
│   ├── package.json          # Dependências Node.js
│   ├── build.sh              # Script de compilação
│   └── setup.sh              # Configuração do frontend
├── 📁 tuning/                # Scripts de otimização e benchmarks
├── README.md                 # Este arquivo
└── LICENSE                   # Licença do projeto
```

## 🔧 Solução de Problemas

### Problemas Comuns

#### Docker não funciona
```bash
# Verificar se Docker está rodando
sudo systemctl status docker

# Verificar permissões
groups $USER  # deve incluir 'docker'

# Reiniciar Docker se necessário
sudo systemctl restart docker
```

#### Erro de dependências
```bash
# Executar verificação completa
cd backend/tools
./setup.sh

# Verificar dependências manualmente na GUI
# Clique em "Check Prerequisites"
```

#### GPU não detectada
```bash
# Verificar driver NVIDIA
nvidia-smi

# Verificar Container Toolkit
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi
```

#### Problemas com arquivos MKV
```bash
# Verificar integridade do arquivo
ffprobe "arquivo.mkv"

# Listar faixas de legenda
mkvmerge -i "arquivo.mkv"
```

### Logs e Debug
- **GUI:** Logs aparecem na área de output
- **CLI:** Logs diretos no terminal
- **Docker:** `docker compose logs -f`

## 📋 TODO

### Recursos Planejados

#### 🎯 Próximas Versões
- [ ] **📁 Suporte a múltiplos arquivos:** Processamento em lote via GUI
- [ ] **🪟 Suporte ao Windows:** AppImage/executável nativo 
- [ ] **🍎 Suporte ao macOS:** DMG e compatibilidade completa
- [ ] **🌐 Mais idiomas:** Suporte além de Português/Inglês
- [ ] **⚙️ Configurações avançadas:** Personalização de modelos IA
- [ ] **📊 Relatórios detalhados:** Estatísticas de tradução
- [ ] **🔄 Auto-update:** Atualização automática do aplicativo

#### 🔧 Melhorias Técnicas
- [ ] **🐳 Containers otimizados:** Imagens Docker menores
- [ ] **⚡ Performance:** Cache de traduções
- [ ] **🧪 Testes automatizados:** Cobertura completa
- [ ] **📱 Interface responsiva:** Design adaptável
- [ ] **🔐 Configuração segura:** Gerenciamento de chaves API

#### 🌟 Recursos Avançados
- [ ] **🎬 Mais formatos:** Suporte SRT, ASS, VTT direto
- [ ] **🤖 Modelos customizados:** Integração com outros LLMs
- [ ] **☁️ Processamento em nuvem:** Opção de usar APIs externas
- [ ] **👥 Colaboração:** Revisão colaborativa de traduções

### Contribuições
Contribuições são bem-vindas! Veja nosso guia de contribuição para mais detalhes.

## 📄 Licença

Este projeto está licenciado sob a Licença MIT. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## 📞 Suporte

- **🐛 Bugs:** Abra uma issue no GitHub
- **💡 Sugestões:** Discussions no repositório  
- **📚 Documentação:** Wiki do projeto

**⭐ Se este projeto foi útil para você, considere dar uma estrela no GitHub!** 