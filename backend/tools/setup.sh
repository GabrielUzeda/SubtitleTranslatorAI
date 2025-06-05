#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[SETUP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if port is available
check_port() {
    local port=$1
    if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
        return 1  # Port is busy
    else
        return 0  # Port is available
    fi
}

# Check if port is being used by our own containers
check_port_by_our_containers() {
    local port=$1
    local expected_service=$2  # "translator" or "ollama"
    
    # Check if our containers are running and using this port
    if docker compose ps --status running 2>/dev/null | grep -q "$expected_service"; then
        # Try multiple methods to get the port mapping
        local mapped_port=""
        
        # Method 1: Use docker compose port command
        mapped_port=$(docker compose port "$expected_service" $([ "$expected_service" = "translator" ] && echo "8000" || echo "11434") 2>/dev/null | cut -d: -f2)
        
        # Method 2: Parse docker compose ps output
        if [ -z "$mapped_port" ]; then
            mapped_port=$(docker compose ps --format "table {{.Service}}\t{{.Ports}}" 2>/dev/null | grep "$expected_service" | sed 's/.*:\([0-9]\+\)->.*/\1/')
        fi
        
        # Method 3: Use docker inspect
        if [ -z "$mapped_port" ]; then
            local container_name
            container_name=$(docker compose ps --format "{{.Name}}" 2>/dev/null | grep "$expected_service")
            if [ -n "$container_name" ]; then
                mapped_port=$(docker inspect "$container_name" 2>/dev/null | jq -r '.[0].NetworkSettings.Ports | to_entries[] | select(.value != null) | .value[0].HostPort' 2>/dev/null | head -1)
            fi
        fi
        
        # Method 4: Direct netstat/ss check for the container process
        if [ -z "$mapped_port" ]; then
            # Get container PID and check what ports it's using
            local container_name
            container_name=$(docker compose ps --format "{{.Name}}" 2>/dev/null | grep "$expected_service")
            if [ -n "$container_name" ]; then
                local container_pid
                container_pid=$(docker inspect "$container_name" 2>/dev/null | jq -r '.[0].State.Pid' 2>/dev/null)
                if [ -n "$container_pid" ] && [ "$container_pid" != "null" ]; then
                    # Check if this PID is listening on our port
                    if netstat -tlnp 2>/dev/null | grep ":$port " | grep -q "$container_pid" || ss -tlnp 2>/dev/null | grep ":$port " | grep -q "$container_pid"; then
                        mapped_port="$port"
                    fi
                fi
            fi
        fi
        
        if [ -n "$mapped_port" ] && [ "$mapped_port" = "$port" ]; then
            return 0  # Port is used by our container - this is OK
        fi
    fi
    
    return 1  # Port is not used by our containers
}

# Check if port is available or used by our containers
is_port_usable() {
    local port=$1
    local service=$2
    
    # If port is available, it's usable
    if check_port "$port"; then
        return 0  # Port is available
    fi
    
    # If port is busy, check if it's our container using it
    if check_port_by_our_containers "$port" "$service"; then
        return 0  # Port is used by our container - OK to use
    fi
    
    return 1  # Port is busy by external process
}

# Find next available port starting from a given port
find_available_port() {
    local start_port=$1
    local port=$start_port
    
    while ! check_port $port; do
        ((port++))
        if [ $port -gt 65535 ]; then
            print_error "No available ports found starting from $start_port"
            exit 1
        fi
    done
    
    echo $port
}

# Update or add environment variable in .env file
update_env_var() {
    local var_name=$1
    local var_value=$2
    local env_file=${3:-.env}
    
    if [ ! -f "$env_file" ]; then
        print_warning ".env file not found, creating it..."
        touch "$env_file"
    fi
    
    # Check if variable exists
    if grep -q "^${var_name}=" "$env_file"; then
        # Variable exists, update it
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS sed syntax
            sed -i '' "s/^${var_name}=.*/${var_name}=${var_value}/" "$env_file"
        else
            # Linux sed syntax
            sed -i "s/^${var_name}=.*/${var_name}=${var_value}/" "$env_file"
        fi
        print_success "Updated ${var_name}=${var_value} in $env_file"
    else
        # Variable doesn't exist, add it
        echo "${var_name}=${var_value}" >> "$env_file"
        print_success "Added ${var_name}=${var_value} to $env_file"
    fi
}

# Create docker-compose override based on GPU type
create_docker_override() {
    local gpu_type=$1
    local docker_runtime=$2
    
    print_status "Creating docker-compose override for $gpu_type GPU..."
    
    case $gpu_type in
        "nvidia")
            cat > docker-compose.override.yml << EOF
version: '3'
services:
  ollama:
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    runtime: $docker_runtime
EOF
            print_success "Created NVIDIA GPU configuration"
            ;;
        "amd")
            cat > docker-compose.override.yml << EOF
version: '3'
services:
  ollama:
    environment:
      - ROC_VISIBLE_DEVICES=all
    device_cgroup_rules:
      - 'c 226:* rmw'
    devices:
      - /dev/kfd:/dev/kfd
      - /dev/dri:/dev/dri
    runtime: $docker_runtime
EOF
            print_success "Created AMD GPU configuration"
            ;;
        "intel")
            cat > docker-compose.override.yml << EOF
version: '3'
services:
  ollama:
    devices:
      - /dev/dri:/dev/dri
    runtime: $docker_runtime
EOF
            print_success "Created Intel GPU configuration"
            ;;
        *)
            cat > docker-compose.override.yml << EOF
version: '3'
services:
  ollama:
    runtime: $docker_runtime
EOF
            print_success "Created CPU-only configuration"
            ;;
    esac
}

# Detect GPU type and configure runtime
detect_and_configure_gpu() {
    print_status "Detecting GPU configuration..." >&2
    
    local gpu_type="none"
    local docker_runtime="runc"
    
    # Check for NVIDIA GPU
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi &> /dev/null; then
            gpu_type="nvidia"
            docker_runtime="nvidia"
            print_success "NVIDIA GPU detected" >&2
        fi
    fi
    
    # Check for AMD GPU (ROCm) only if no NVIDIA found
    if [ "$gpu_type" = "none" ]; then
        if command -v rocm-smi &> /dev/null; then
            if rocm-smi &> /dev/null; then
                gpu_type="amd"
                docker_runtime="runc"  # AMD uses standard runtime with device mapping
                print_success "AMD GPU detected" >&2
            fi
        elif lspci 2>/dev/null | grep -i amd | grep -i vga &> /dev/null; then
            gpu_type="amd"
            docker_runtime="runc"
            print_warning "AMD GPU detected but ROCm tools not found. Using CPU runtime." >&2
        fi
    fi
    
    # Check for Intel GPU only if no other GPU found
    if [ "$gpu_type" = "none" ]; then
        if lspci 2>/dev/null | grep -i intel | grep -i vga &> /dev/null; then
            gpu_type="intel"
            docker_runtime="runc"
            print_warning "Intel GPU detected. Using CPU runtime (GPU acceleration not configured)." >&2
        fi
    fi
    
    if [ "$gpu_type" = "none" ]; then
        print_warning "No GPU detected or GPU tools not available. Using CPU runtime." >&2
    fi
    
    # Update .env with the detected runtime
    update_env_var "DOCKER_RUNTIME" "$docker_runtime" >&2
    
    # Return GPU type and runtime for use in main function
    echo "$gpu_type:$docker_runtime"
}

# Check and configure ports
configure_ports() {
    print_status "Checking port availability..."
    
    # Load current .env values or use defaults
    local translator_port=8000
    local ollama_port=11434
    
    if [ -f ".env" ]; then
        # Try to extract current ports from .env
        if grep -q "^TRANSLATOR_PORT=" .env; then
            translator_port=$(grep "^TRANSLATOR_PORT=" .env | cut -d'=' -f2)
        fi
        if grep -q "^OLLAMA_PORT=" .env; then
            ollama_port=$(grep "^OLLAMA_PORT=" .env | cut -d'=' -f2)
        fi
    fi
    
    # Check translator port
    if is_port_usable "$translator_port" "translator"; then
        if check_port_by_our_containers "$translator_port" "translator"; then
            print_success "Port $translator_port is already being used by our translator service"
        else
            print_success "Port $translator_port is available for translator service"
        fi
    else
        print_warning "Port $translator_port is busy by external process, finding alternative..."
        translator_port=$(find_available_port $((translator_port + 1)))
        print_success "Using port $translator_port for translator service"
    fi
    
    # Check ollama port
    if is_port_usable "$ollama_port" "ollama"; then
        if check_port_by_our_containers "$ollama_port" "ollama"; then
            print_success "Port $ollama_port is already being used by our ollama service"
        else
            print_success "Port $ollama_port is available for ollama service"
        fi
    else
        print_warning "Port $ollama_port is busy by external process, finding alternative..."
        ollama_port=$(find_available_port $((ollama_port + 1)))
        print_success "Using port $ollama_port for ollama service"
    fi
    
    # Update .env with available ports
    update_env_var "TRANSLATOR_PORT" "$translator_port"
    update_env_var "OLLAMA_PORT" "$ollama_port"
}

# Check system dependencies
check_system_dependencies() {
    print_status "Checking system dependencies..."
    
    local missing_deps=()
    local missing_optional=()
    
    # Core dependencies - required for basic functionality
    local core_deps=(
        "docker:Docker"
        "curl:curl"
        "jq:jq"
        "find:findutils"
        "sed:sed"
    )
    
    # Media processing dependencies - required for subtitle processing
    local media_deps=(
        "mkvmerge:mkvtoolnix"
        "mkvextract:mkvtoolnix" 
        "ffmpeg:ffmpeg"
        "ffprobe:ffmpeg"
    )
    
    # System utilities - usually available but good to check
    local system_deps=(
        "file:file"
        "grep:grep"
    )
    
    # Network utilities - at least one required for port checking
    local network_deps=(
        "netstat:net-tools"
        "ss:iproute2"
    )
    
    # GPU detection utilities (optional)
    local gpu_deps=(
        "nvidia-smi:nvidia-utils"
        "rocm-smi:rocm-smi"
        "lspci:pciutils"
    )
    
    print_status "  → Checking core dependencies..."
    for dep_info in "${core_deps[@]}"; do
        local cmd="${dep_info%:*}"
        local package="${dep_info#*:}"
        
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd ($package)")
            print_error "Missing required dependency: $cmd"
        else
            print_success "$cmd is available"
        fi
    done
    
    print_status "  → Checking media processing dependencies..."
    for dep_info in "${media_deps[@]}"; do
        local cmd="${dep_info%:*}"
        local package="${dep_info#*:}"
        
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd ($package)")
            print_error "Missing required dependency: $cmd"
        else
            print_success "$cmd is available"
        fi
    done
    
    print_status "  → Checking system utilities..."
    for dep_info in "${system_deps[@]}"; do
        local cmd="${dep_info%:*}"
        local package="${dep_info#*:}"
        
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd ($package)")
            print_error "Missing system utility: $cmd"
        else
            print_success "$cmd is available"
        fi
    done
    
    print_status "  → Checking network utilities..."
    local network_available=false
    for dep_info in "${network_deps[@]}"; do
        local cmd="${dep_info%:*}"
        local package="${dep_info#*:}"
        
        if command -v "$cmd" &> /dev/null; then
            print_success "$cmd is available"
            network_available=true
            break
        fi
    done
    
    if [ "$network_available" = false ]; then
        missing_deps+=("netstat or ss (net-tools or iproute2)")
        print_error "Missing network utility: need either netstat or ss"
    fi
    
    print_status "  → Checking GPU detection utilities (optional)..."
    local gpu_utils_found=false
    for dep_info in "${gpu_deps[@]}"; do
        local cmd="${dep_info%:*}"
        local package="${dep_info#*:}"
        
        if command -v "$cmd" &> /dev/null; then
            print_success "$cmd is available"
            gpu_utils_found=true
        else
            missing_optional+=("$cmd ($package)")
        fi
    done
    
    if [ "$gpu_utils_found" = false ]; then
        print_warning "No GPU detection utilities found - will use basic detection"
    fi
    
    # Report missing dependencies
    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_error "Missing required dependencies:"
        for dep in "${missing_deps[@]}"; do
            echo -e "  ${RED}✗${NC} $dep"
        done
        echo
        print_error "Please install missing dependencies:"
        
        # Provide installation instructions based on the system
        if command -v apt-get &> /dev/null; then
            echo -e "${YELLOW}Ubuntu/Debian:${NC}"
            echo "  sudo apt-get update"
            echo "  sudo apt-get install docker.io docker-compose mkvtoolnix ffmpeg jq curl net-tools pciutils file"
        elif command -v yum &> /dev/null; then
            echo -e "${YELLOW}RHEL/CentOS/Fedora:${NC}"
            echo "  sudo dnf install docker docker-compose mkvtoolnix ffmpeg jq curl net-tools pciutils file"
        elif command -v pacman &> /dev/null; then
            echo -e "${YELLOW}Arch Linux:${NC}"
            echo "  sudo pacman -S docker docker-compose mkvtoolnix ffmpeg jq curl net-tools pciutils file"
        elif command -v brew &> /dev/null; then
            echo -e "${YELLOW}macOS:${NC}"
            echo "  brew install docker docker-compose mkvtoolnix ffmpeg jq curl"
        else
            echo -e "${YELLOW}Please install the missing dependencies using your system's package manager.${NC}"
        fi
        
        exit 1
    fi
    
    if [ ${#missing_optional[@]} -gt 0 ]; then
        print_warning "Optional dependencies not found (GPU detection may be limited):"
        for dep in "${missing_optional[@]}"; do
            echo -e "  ${YELLOW}!${NC} $dep"
        done
    fi
    
    print_success "All required dependencies are available!"
}

# Check Docker installation and permissions
check_docker() {
    print_status "Checking Docker installation..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    print_success "Docker is installed"
    
    # Check if user can run docker commands
    if ! docker info &> /dev/null; then
        print_error "You don't have permission to run Docker commands."
        print_error "Consider running: sudo usermod -aG docker \$USER && newgrp docker"
        print_error "Or run this script with sudo."
        exit 1
    fi
    
    print_success "Docker permissions are correct"
}

# Check Docker Compose
check_docker_compose() {
    print_status "Checking Docker Compose..."
    
    if ! docker compose version &> /dev/null && ! docker-compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Docker Compose is available"
}

# Check if Docker containers are running
check_docker_containers() {
    print_status "Checking Docker containers status..."
    
    local compose_status
    if ! compose_status=$(docker compose ps --status running 2>/dev/null | grep -E 'translator|ollama'); then
        print_warning "Docker containers are not running."
        print_status "Will start containers when needed..."
    else
        print_success "Docker containers are already running"
    fi
}

# Test API connectivity (moved from main.sh)
test_api_connectivity() {
    print_status "Testing API connectivity..."
    
    local translator_port="${TRANSLATOR_PORT:-8000}"
    local api_url="http://localhost:${translator_port}/translate"
    
    # Only test if containers are running
    if docker compose ps --status running 2>/dev/null | grep -q translator; then
        if curl -s "$api_url" -d '{"text":"test"}' &>/dev/null; then
            print_success "Translation API is responding"
        else
            print_warning "Translation API is not responding (containers may need time to start)"
        fi
    else
        print_status "Containers not running - API test will be performed later"
    fi
}

# Create .env from example if it doesn't exist
ensure_env_file() {
    if [ ! -f ".env" ]; then
        if [ -f "env.example" ]; then
            print_status "Creating .env file from env.example..."
            cp env.example .env
            print_success ".env file created from env.example"
        else
            print_warning "Neither .env nor env.example found, creating basic .env..."
            cat > .env << EOF
# Docker container configuration
TRANSLATOR_PORT=8000
OLLAMA_PORT=11434
OLLAMA_HOST=ollama
DOCKER_RUNTIME=runc

# Model configuration: tibellium/towerinstruct-mistral
OLLAMA_MODEL=tibellium/towerinstruct-mistral
EOF
            print_success "Basic .env file created"
        fi
    else
        print_success ".env file already exists"
    fi
}

# Ensure required environment variables exist
ensure_required_env_vars() {
    print_status "Ensuring required environment variables..."
    
    # Set defaults for missing variables
    local vars=(
        "OLLAMA_HOST:ollama"
        "OLLAMA_MODEL:tibellium/towerinstruct-mistral"
    )
    
    for var_def in "${vars[@]}"; do
        local var_name="${var_def%:*}"
        local var_default="${var_def#*:}"
        
        if ! grep -q "^${var_name}=" .env; then
            update_env_var "$var_name" "$var_default"
        fi
    done
}

# Main setup function
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║        SubtitleTranslatorAI Setup Script       ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
    echo
    
    # Check all system dependencies first
    check_system_dependencies
    
    # Check Docker (now redundant but kept for explicit Docker-specific checks)
    check_docker
    check_docker_compose
    
    # Ensure .env file exists
    ensure_env_file
    
    # Detect and configure GPU
    local gpu_info
    gpu_info=$(detect_and_configure_gpu)
    local gpu_type="${gpu_info%:*}"
    local docker_runtime="${gpu_info#*:}"
    
    # Configure ports
    configure_ports
    
    # Ensure all required env vars exist
    ensure_required_env_vars
    
    # Create docker-compose override
    create_docker_override "$gpu_type" "$docker_runtime"
    
    # Check container status
    check_docker_containers
    
    # Test API connectivity if possible
    test_api_connectivity
    
    echo
    print_success "Setup completed successfully!"
    print_status "Current configuration:"
    
    if [ -f ".env" ]; then
        echo -e "${YELLOW}Current .env settings:${NC}"
        grep -E "^(TRANSLATOR_PORT|OLLAMA_PORT|DOCKER_RUNTIME|OLLAMA_MODEL)=" .env | while read line; do
            echo -e "  ${GREEN}$line${NC}"
        done
    fi
    
    echo
    print_status "GPU Configuration: $gpu_type ($docker_runtime runtime)"
    print_status "You can now run: ./main.sh <your-file.mkv>"
}

# Run main function
main "$@" 