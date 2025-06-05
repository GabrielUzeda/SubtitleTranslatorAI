#!/bin/bash
set -euo pipefail

# Run setup to configure environment
SETUP_SCRIPT="./tools/setup.sh"
if [ -f "$SETUP_SCRIPT" ]; then
    echo "Running environment setup..."
    "$SETUP_SCRIPT"
    echo ""
else
    echo "Warning: Setup script not found at $SETUP_SCRIPT"
    echo "Proceeding with manual environment checks..."
    
    # Check for .env file
    if [ ! -f ".env" ] && [ -f "env.example" ]; then
        echo "Creating .env file from env.example..."
        cp env.example .env
    fi
fi

# Load environment variables from .env
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# Define operational modes
MODE_ALL="all"       # Process all subtitles
MODE_SELECT="select" # Select best subtitle by language priority

# Default mode: ALTERADO para SELECT (invertendo a lógica anterior)
OPERATION_MODE="$MODE_SELECT"

# Default translation model
MODEL="tibellium/towerinstruct-mistral"

# Flag to control cleanup behavior
COMPLETE_CLEANUP_DONE="false"

# Export environment variables for child scripts
export TRANSLATOR_URL="http://localhost:${TRANSLATOR_PORT:-8000}/translate"
export TRANSLATOR_PORT="${TRANSLATOR_PORT:-8000}"
export OLLAMA_MODEL="$MODEL"

# Correct relative paths for execution from translatorApi/
EXTRACT_SCRIPT="./tools/extract.sh"
CONVERT_SCRIPT="./tools/convert.sh"
TRANSLATE_SCRIPT="./tools/translate.sh"
MERGE_SCRIPT="./tools/merge.sh"
FILTER_SCRIPT="./tools/filter.sh"
SELECT_SCRIPT="./tools/select.sh"

# Check if Docker containers are running (specific check for this run)
check_docker_compose() {
    local compose_status
    if ! compose_status=$(docker compose ps --status running 2>/dev/null | grep -E 'translator|ollama'); then
        echo "Docker containers are not running. Starting them now..."
        docker compose up -d
        echo "Waiting for containers to be ready..."
        sleep 10  # Give some time for containers to start
    else
        echo "Docker containers are already running."
    fi
}

# Check if API is responding (runtime check)
check_api() {
    echo "Checking if translation API is available..."
    if ! curl -s "http://localhost:${TRANSLATOR_PORT:-8000}/translate" -d '{"text":"test"}' &>/dev/null; then
        echo "Error: Translation API is not responding at http://localhost:${TRANSLATOR_PORT:-8000}"
        echo "Make sure the translatorApi service is running."
        exit 1
    fi
}

# Function to cleanup any temporary files at the end
cleanup() {
    local mkv_file="$1"
    
    # Skip if complete cleanup was already done
    if [ "$COMPLETE_CLEANUP_DONE" = "true" ]; then
        return 0
    fi
    
    if [ -n "$mkv_file" ]; then
        dir=$(dirname "$mkv_file")
        base=$(basename "${mkv_file%.mkv}")
        
        # Remove processed marker if it exists
        processed_marker="$dir/${base}.processed"
        if [ -f "$processed_marker" ]; then
            rm -f "$processed_marker"
            echo "✓ Removed temporary tracking file"
        fi
        
        # Remove orphaned .best.srt symbolic links
        best_srt_link="$dir/${base}.best.srt"
        if [ -L "$best_srt_link" ]; then
            rm -f "$best_srt_link"
            echo "✓ Removed orphaned symbolic link: $best_srt_link"
        fi
        
        # Clean up extracted subtitle files (keeping only pt-br.srt)
        echo "🧹 Cleaning up temporary subtitle files..."
        
        # Remove .ass files
        find "$dir" -name "*.ass" 2>/dev/null | grep -F "$base" | xargs -r rm -f && echo "✓ Removed .ass files"
        
        # Remove intermediate .srt files (except pt-br.srt)
        find "$dir" -name "*.srt" 2>/dev/null | grep -F "$base" | grep -v "\.pt-br\.srt$" | xargs -r rm -f && echo "✓ Removed intermediate .srt files"
        
        # Remove any backup or temporary files
        find "$dir" -name "${base}*.bak" -delete 2>/dev/null
        find "$dir" -name "${base}*.tmp" -delete 2>/dev/null
        
        echo "✅ Cleanup completed - only ${base}.mkv and ${base}.pt-br.srt remain"
    fi
    
    # Remove debug files from backend
    debug_file="./debug_full_translation.srt"
    if [ -f "$debug_file" ]; then
        rm -f "$debug_file"
        echo "✓ Removed debug file: $debug_file"
    fi
}

# Function for complete cleanup after successful merge
cleanup_after_merge() {
    local mkv_file="$1"
    
    if [ -n "$mkv_file" ]; then
        dir=$(dirname "$mkv_file")
        base=$(basename "${mkv_file%.mkv}")
        
        echo "🧹 Final cleanup - removing all subtitle files (now embedded in MKV)..."
        
        # Remove ALL subtitle files including pt-br.srt since they're now in the MKV
        find "$dir" -name "*.srt" 2>/dev/null | grep -F "$base" | xargs -r rm -f && echo "✓ Removed all .srt files"
        find "$dir" -name "*.ass" 2>/dev/null | grep -F "$base" | xargs -r rm -f && echo "✓ Removed all .ass files"
        
        # Remove any backup or temporary files
        find "$dir" -name "${base}*.bak" -delete 2>/dev/null
        find "$dir" -name "${base}*.tmp" -delete 2>/dev/null
        
        # Remove processed marker if it exists
        processed_marker="$dir/${base}.processed"
        if [ -f "$processed_marker" ]; then
            rm -f "$processed_marker"
        fi
        
        # Remove orphaned .best.srt symbolic links
        best_srt_link="$dir/${base}.best.srt"
        if [ -L "$best_srt_link" ]; then
            rm -f "$best_srt_link"
        fi
        
        echo "✅ Final cleanup completed - only ${base}.mkv remains"
    fi
    
    # Remove debug files from backend
    debug_file="./debug_full_translation.srt"
    if [ -f "$debug_file" ]; then
        rm -f "$debug_file"
    fi
    
    # Mark that complete cleanup was done
    COMPLETE_CLEANUP_DONE="true"
}

usage() {
    echo "Usage: $0 [options] <file.mkv>"
    echo "Options:"
    echo "  -s, --select  Select best subtitle by language priority (default)"
    echo "  -a, --all     Process all subtitles"
    echo ""
    echo "Example: $0 ./examples/example.mkv"
    echo "Example: $0 --all ./examples/example.mkv"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--all)
            OPERATION_MODE="$MODE_ALL"
            shift
            ;;
        -s|--select)
            OPERATION_MODE="$MODE_SELECT"
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            # Assume it's the MKV file
            MKV_FILE="$1"
            shift
            ;;
    esac
done

# Verify we have an MKV file
if [ -z "${MKV_FILE:-}" ]; then
    usage
fi

echo "Using translation model: $MODEL"

# Ensure cleanup runs on exit
trap 'cleanup "$MKV_FILE"' EXIT

# Check Docker and Docker Compose
check_docker_compose

# Check if file exists and is an .mkv
if [ ! -f "$MKV_FILE" ]; then
    echo "Error: file '$MKV_FILE' not found."
    exit 1
fi

if [[ "$MKV_FILE" != *.mkv ]]; then
    echo "Error: file must be an .mkv"
    exit 1
fi

# Check if API is running
check_api

# Process based on the selected mode
if [ "$OPERATION_MODE" = "$MODE_ALL" ]; then
    # Mode: Process all subtitles
    echo "==> Starting subtitle extraction and translation process..."

    # Find existing subtitles before extraction
    dir=$(dirname "$MKV_FILE")
    base=$(basename "${MKV_FILE%.mkv}")
    echo -e "\n[0/5] Checking existing subtitles..."
    mapfile -t existing_srt_files < <(find "$dir" -name "${base}*.srt")

    if [ ${#existing_srt_files[@]} -gt 0 ]; then
        echo "Existing subtitles found:"
        printf '%s\n' "${existing_srt_files[@]}"
    fi

    # Extract subtitles
    echo -e "\n[1/5] Extracting subtitles from file..."
    "$EXTRACT_SCRIPT" "$MKV_FILE"

    # Convert all subtitle formats to SRT
    echo -e "\n[2/5] Converting subtitle formats to SRT..."
    "$CONVERT_SCRIPT" "$dir" "$base"

    # Run filters on extracted subtitles
    echo -e "\n[3/5] Running filters on extracted subtitles..."
    "$FILTER_SCRIPT" "$dir" "$base"

    # Find all extracted subtitles and translate
    echo -e "\n[4/5] Translating extracted subtitles..."
    # Look for .srt subtitles that are not pt-br
    mapfile -t srt_files < <(find "$dir" -name "*.srt" 2>/dev/null | grep -F "$base" | grep -v "\.pt-br\.srt$" || true)

    if [ ${#srt_files[@]} -eq 0 ]; then
        echo "No .srt subtitles found to translate."
        exit 1
    fi

    # Run translation and continue even if it fails
    "$TRANSLATE_SCRIPT" "${srt_files[@]}" || echo "Warning: Translation completed with errors"

    # Check if we have a pt-br.srt file using robust detection
    pt_br_found=false
    
    # Method 1: Direct filename match (most reliable)
    if find "$dir" -name "${base}.pt-br.srt" -type f -size +0c 2>/dev/null | grep -q .; then
        pt_br_found=true
    fi
    
    # Method 2: Pattern search using base filename pattern
    if [ "$pt_br_found" = false ]; then
        # Extract identifier from filename for more flexible matching
        identifier=""
        if [[ "$base" =~ -[[:space:]]*([0-9]+)[^0-9]*$ ]]; then
            identifier="${BASH_REMATCH[1]}"
        fi
        
        if [ -n "$identifier" ] && find "$dir" -name "*${identifier}*.pt-br.srt" -type f -size +0c 2>/dev/null | grep -q .; then
            pt_br_found=true
        fi
    fi
    
    # Method 3: General search for recent pt-br files (last resort)
    if [ "$pt_br_found" = false ]; then
        if find "$dir" -name "*.pt-br.srt" -type f -size +0c -newer "$MKV_FILE" 2>/dev/null | grep -q .; then
            pt_br_found=true
        fi
    fi
    
    if [ "$pt_br_found" = false ]; then
        echo "Error: No translated subtitle (pt-br) was created!"
        exit 1
    fi

    # Merge subtitles into MKV file
    echo -e "\n[5/5] Merging subtitles into MKV file..."
    "$MERGE_SCRIPT" "$MKV_FILE"

    echo -e "\n==> Process complete!"
    echo "MKV file updated with all subtitles at: $MKV_FILE"

    # Perform complete cleanup after successful merge
    cleanup_after_merge "$MKV_FILE"
else
    # Mode: Select best subtitle
    echo "==> Starting subtitle selection process..."
    
    # Select the best subtitle
    "$SELECT_SCRIPT" "$MKV_FILE" || echo "Warning: Subtitle selection completed with warnings"
    
    # Check if we have a translated pt-br subtitle and merge it
    dir=$(dirname "$MKV_FILE")
    base=$(basename "${MKV_FILE%.mkv}")
    
    # Extract a simpler identifier from the filename for pattern matching
    # Look for episode numbers or similar patterns to identify related files
    identifier=""
    if [[ "$base" =~ -[[:space:]]*([0-9]+)[^0-9]*$ ]]; then
        identifier="${BASH_REMATCH[1]}"
    fi
    
    # Try multiple detection methods for pt-br files
    pt_br_found=false
    
    # Method 1: Direct filename match (most reliable)
    if [ -f "$dir/${base}.pt-br.srt" ] && [ -s "$dir/${base}.pt-br.srt" ]; then
        pt_br_found=true
    fi
    
    # Method 2: Pattern search using identifier if available
    if [ "$pt_br_found" = false ] && [ -n "$identifier" ]; then
        if find "$dir" -name "*${identifier}*.pt-br.srt" -type f -size +0c 2>/dev/null | grep -q .; then
            pt_br_found=true
        fi
    fi
    
    # Method 3: General search in directory (last resort)
    if [ "$pt_br_found" = false ]; then
        if find "$dir" -name "*.pt-br.srt" -type f -size +0c -newer "$MKV_FILE" 2>/dev/null | grep -q .; then
            pt_br_found=true
        fi
    fi
    
    if [ "$pt_br_found" = true ]; then
        echo -e "\n[Final Step] Merging translated subtitle into MKV file..."
        "$MERGE_SCRIPT" "$MKV_FILE" || echo "Warning: Merge failed, but translation was successful"
        echo -e "\n==> Process complete!"
        echo "MKV file updated with translated subtitle at: $MKV_FILE"

        # Perform complete cleanup after successful merge
        cleanup_after_merge "$MKV_FILE"
    else
        echo -e "\n==> Process complete!"
        echo "Best subtitle selected and translated for: $MKV_FILE"
        echo "Note: No valid Portuguese translation was created for merging."
    fi
fi
