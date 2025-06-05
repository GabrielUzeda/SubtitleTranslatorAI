#!/bin/bash

# SubtitleTranslatorAI Wrapper Script
# This script ensures proper execution of main.sh with host system access

set -euo pipefail

# Function to log with timestamp
log() {
    echo "[$(date '+%H:%M:%S')] $*" >&2
}

# Function to get the packaged backend directory
get_packaged_backend() {
    local script_dir="$(dirname "$(realpath "$0")")"
    
    # In AppImage, try multiple possible locations
    local possible_paths=(
        # Standard Electron packaging location
        "${APPDIR:-}/resources/backend"
        # Relative to wrapper script in asar
        "$(dirname "$script_dir")/resources/backend"
        "$(dirname "$(dirname "$script_dir")")/resources/backend"
        # Fallback locations
        "$script_dir/../backend"
        "$script_dir/../../backend" 
        "$script_dir/../resources/backend"
        "$script_dir/../../resources/backend"
        "$script_dir/../extraResources/backend"
        "$script_dir/../../extraResources/backend"
        # AppImage environment paths
        "${APPDIR:-}/usr/share/subtitletranslatorai/backend"
        "${APPDIR:-}/opt/subtitletranslatorai/backend"
        # Electron builder paths
        "$(dirname "$script_dir")/resources/backend"
        "$(dirname "$(dirname "$script_dir")")/resources/backend"
    )
    
    log "Looking for packaged backend from script directory: $script_dir"
    log "APPDIR environment: ${APPDIR:-'not set'}"
    
    for path in "${possible_paths[@]}"; do
        local real_path="$(realpath "$path" 2>/dev/null || echo "$path")"
        log "Checking path: $real_path"
        if [[ -f "$real_path/main.sh" && -r "$real_path/main.sh" ]]; then
            log "Found packaged backend at: $real_path"
            echo "$real_path"
            return 0
        fi
    done
    
    return 1
}

# Function to check if system has active subtitletranslatorai containers
check_system_containers() {
    # Check if there are active containers that look like our services
    if docker ps --format "table {{.Names}}\t{{.Ports}}" 2>/dev/null | grep -E "(8000|11434)" | grep -E "(ollama|translator)" >/dev/null 2>&1; then
        log "🔍 Detected active SubtitleTranslatorAI containers in system"
        return 0
    fi
    
    # Also check for containers with our standard names
    if docker ps --filter "name=ollama" --filter "name=translator" --format "{{.Names}}" 2>/dev/null | grep -E "(ollama|translator)" >/dev/null 2>&1; then
        log "🔍 Detected containers with SubtitleTranslatorAI names"
        return 0
    fi
    
    return 1
}

# Function to find host backend directory (fallback)
find_host_backend() {
    local possible_paths=(
        "$HOME/Projects/SubtitleTranslatorAI/backend"
        "$HOME/Projects/subTranslator/backend"  # Keep for backward compatibility
        "/opt/subtitletranslatorai/backend"
        "/usr/local/subtitletranslatorai/backend"
        "$(pwd)/backend"
        "$(dirname "$(pwd)")/backend"
        # Check relative to where AppImage was started
        "$(dirname "$PWD")/backend"
        # Check if user extracted backend manually
        "$HOME/.local/share/subtitletranslatorai/backend"
    )
    
    log "Looking for host backend directory..."
    
    for path in "${possible_paths[@]}"; do
        if [[ -f "$path/main.sh" && -r "$path/main.sh" ]]; then
            log "Found host backend at: $path"
            echo "$path"
            return 0
        fi
    done
    
    return 1
}

# Function to check Docker accessibility
check_docker() {
    if ! command -v docker &> /dev/null; then
        log "❌ Docker not found in PATH"
        return 1
    fi
    
    if ! docker info &> /dev/null; then
        log "❌ Cannot connect to Docker daemon"
        return 1
    fi
    
    log "✅ Docker is accessible"
    return 0
}

# Function to setup a complete working backend in the user's directory
setup_working_backend() {
    local backend_dir="$1"
    local working_dir="$(pwd)"
    
    log "🔍 Debug - Backend dir: $backend_dir"
    log "🔍 Debug - Working dir: $working_dir"
    log "🔍 Debug - Backend writable: $(test -w "$backend_dir" && echo "yes" || echo "no")"
    
    # Check if this is a host backend (not from AppImage)
    if [[ "$backend_dir" != /tmp/.mount_* && "$backend_dir" != *squashfs-root* ]]; then
        log "🏠 Detected host backend - using directly without copying"
        log "🔄 Will execute from host backend directory to reuse existing containers"
        
        # For host backend, we'll execute from the backend directory
        # Just set environment variables
        export TMPDIR="${working_dir}/tmp"
        mkdir -p "$TMPDIR" 2>/dev/null || true
        
        # Tell scripts to output to current directory
        export SUBTITLE_WORK_DIR="$working_dir"
        export USER_WORK_DIR="$working_dir"
        export OUTPUT_DIR="$working_dir"
        
        log "✅ Host backend configured - will execute from: $backend_dir"
        return 0
    fi
    
    # AppImage backend - need to set up working environment
    log "📁 Setting up complete working backend for AppImage..."
    
    # Setup working environment in current directory
    log "📁 Setting up complete working backend..."
    
    # Copy essential files to current working directory
    local files_to_copy=(".env" "env.example" "docker-compose.yml" "main.sh")
    
    for file in "${files_to_copy[@]}"; do
        if [[ -f "$backend_dir/$file" && ! -f "$working_dir/$file" ]]; then
            cp "$backend_dir/$file" "$working_dir/$file" 2>/dev/null || true
            log "📄 Copied $file to working directory"
        fi
    done
    
    # Fix docker-compose.yml to avoid container name conflicts
    if [[ -f "$working_dir/docker-compose.yml" ]]; then
        log "🐳 Removing fixed container names from docker-compose.yml..."
        # Remove container_name lines to let Docker Compose auto-generate unique names
        sed -i '/container_name:/d' "$working_dir/docker-compose.yml" 2>/dev/null || true
        log "✅ Fixed docker-compose.yml for AppImage usage"
    fi
    
    # Copy tools directory
    if [[ -d "$backend_dir/tools" && ! -d "$working_dir/tools" ]]; then
        cp -r "$backend_dir/tools" "$working_dir/tools" 2>/dev/null || true
        log "📁 Copied tools/ directory to working directory"
    fi
    
    # Handle translatorApi directory - remove existing completely first
    if [[ -e "$working_dir/translatorApi" ]]; then
        rm -rf "$working_dir/translatorApi" 2>/dev/null || true
        log "🗑️ Removed existing translatorApi"
    fi
    
    if [[ -d "$backend_dir/translatorApi" ]]; then
        log "🔗 Setting up translatorApi directory..."
        # For AppImage, always copy to avoid Docker volume mount issues with symlinks
        if [[ -n "${APPIMAGE:-}" ]]; then
            if cp -r "$backend_dir/translatorApi" "$working_dir/translatorApi" 2>/dev/null; then
                log "📁 Copied translatorApi directory (AppImage mode)"
            else
                log "❌ Failed to copy translatorApi directory"
                return 1
            fi
        else
            # For non-AppImage, try symlink first, then copy as fallback
            if ln -sf "$backend_dir/translatorApi" "$working_dir/translatorApi" 2>/dev/null; then
                log "🔗 Linked translatorApi directory (symlink)"
            else
                log "⚠️ Symlink failed, trying copy..."
                if cp -r "$backend_dir/translatorApi" "$working_dir/translatorApi" 2>/dev/null; then
                    log "📁 Copied translatorApi directory"
                else
                    log "❌ Failed to link/copy translatorApi directory"
                    return 1
                fi
            fi
        fi
    fi
    
    # Verify we have a working main.sh in the current directory
    if [[ ! -f "$working_dir/main.sh" ]]; then
        log "❌ Failed to setup main.sh in working directory"
        return 1
    fi
    
    # Make main.sh executable
    chmod +x "$working_dir/main.sh" 2>/dev/null || true
    
    # Also make tools executable if they exist
    if [[ -d "$working_dir/tools" ]]; then
        chmod +x "$working_dir/tools"/*.sh 2>/dev/null || true
    fi
    
    # Set environment variables for proper execution
    export TMPDIR="${working_dir}/tmp"
    mkdir -p "$TMPDIR" 2>/dev/null || true
    
    # Tell scripts to use current directory for file operations
    export SUBTITLE_WORK_DIR="$working_dir"
    export USER_WORK_DIR="$working_dir"
    export OUTPUT_DIR="$working_dir"
    
    log "✅ Complete working backend set up in: $working_dir"
    
    # Verify the setup
    log "🔍 Verifying setup:"
    log "  - main.sh: $(test -f "$working_dir/main.sh" && echo "✅" || echo "❌")"
    log "  - tools/: $(test -d "$working_dir/tools" && echo "✅" || echo "❌")"
    log "  - translatorApi/: $(test -d "$working_dir/translatorApi" && echo "✅" || echo "❌")"
    log "  - .env: $(test -f "$working_dir/.env" && echo "✅" || echo "❌")"
    log "  - docker-compose.yml: $(test -f "$working_dir/docker-compose.yml" && echo "✅" || echo "❌")"
    
    return 0
}

# Main execution
main() {
    log "🚀 SubtitleTranslatorAI Wrapper Starting..."
    log "📍 Arguments: $*"
    
    # Preserve original working directory for output files
    local original_cwd="$(pwd)"
    log "📂 Working directory: $original_cwd"
    
    # Show environment info
    if [[ -n "${APPIMAGE:-}" ]]; then
        log "🖼️ Running from AppImage: $APPIMAGE"
    fi
    if [[ -n "${APPDIR:-}" ]]; then
        log "📁 AppImage directory: $APPDIR"
    fi
    
    # Check Docker first
    if ! check_docker; then
        log "⚠️ Docker issues detected, but continuing..."
    fi
    
    # Try to find backend directory - prioritize host backend if containers are active
    local backend_dir
    
    # Check if there are active containers from the application
    if check_system_containers; then
        log "🔄 Active containers detected - prioritizing host backend to reuse them"
        if backend_dir=$(find_host_backend); then
            log "✅ Using host backend to reuse active containers: $backend_dir"
        else
            log "⚠️ Active containers detected but no host backend found"
            log "📦 Falling back to packaged backend (may create duplicate containers)"
            if backend_dir=$(get_packaged_backend); then
                log "✅ Using packaged backend: $backend_dir"
            else
                log "❌ Could not find any backend directory with main.sh"
                exit 1
            fi
        fi
    else
        log "📦 No active containers detected - using packaged backend"
        if backend_dir=$(get_packaged_backend); then
            log "✅ Using packaged backend: $backend_dir"
        elif backend_dir=$(find_host_backend); then
            log "✅ Using host backend: $backend_dir"
        else
            log "❌ Could not find backend directory with main.sh"
            log "💡 Searched in common locations. Please ensure the backend is available."
            exit 1
        fi
    fi
    
    # Setup complete working backend in user's directory
    if ! setup_working_backend "$backend_dir"; then
        log "❌ Failed to setup working backend"
        exit 1
    fi
    
    # Execute main.sh from appropriate directory
    if [[ "$backend_dir" != /tmp/.mount_* && "$backend_dir" != *squashfs-root* ]]; then
        # Host backend - execute from backend directory to reuse containers
        log "🏃 Executing main.sh from host backend directory: $backend_dir"
        log "📂 Output will be saved to: $original_cwd"
        cd "$backend_dir"
        exec bash ./main.sh "$@"
    else
        # AppImage backend - execute from working directory
        log "🏃 Executing main.sh from working directory: $original_cwd"
        exec bash ./main.sh "$@"
    fi
}

# Execute main function with all arguments
main "$@" 