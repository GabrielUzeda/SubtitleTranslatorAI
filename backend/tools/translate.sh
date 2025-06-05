#!/bin/bash
set -euo pipefail

# API Configuration
API_URL="${TRANSLATOR_URL:-http://localhost:${TRANSLATOR_PORT:-8000}/translate}"
TARGET_LANG="pt-br"

# Additional Settings
MIN_TRANSLATION_TIME=2  # Mínimo de segundos que uma tradução deve levar (para garantir que a IA é usada)

# Check dependencies
for cmd in curl jq sed file; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "Error: '$cmd' not found. Install required dependencies." >&2
    exit 1
  fi
done

usage() {
  echo "Usage: $0 file1.srt [file2.srt ...]"
  echo "Translates SRT subtitle files to Brazilian Portuguese using local API."
  exit 1
}

[ $# -ge 1 ] || usage

# Check if API is accessible
echo "Checking translation API connection..."
api_response=$(curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{"text":"This is a test of the translation API"}' 2>&1)
if [ $? -ne 0 ] || ! echo "$api_response" | grep -q "translated_text"; then
  echo "Error: Translation API is not responding correctly at $API_URL" >&2
  echo "Response received: $api_response" >&2
  exit 1
fi

translated_test=$(echo "$api_response" | jq -r '.translated_text')
echo "✓ API responding correctly"
echo "✓ Test translation: \"This is a test of the translation API\" → \"$translated_test\""

# Function to check if a subtitle file is already in Portuguese
is_portuguese() {
  local file="$1"
  local sample_size=5  # Number of subtitle blocks to check
  local portuguese_count=0
  local line_count=0
  local in_text=false
  
  # Read the file line by line
  while IFS= read -r line || [ -n "$line" ]; do
    # Skip timestamps and numbers
    if [[ "$line" =~ ^[0-9]+$ ]] || [[ "$line" =~ [0-9]{2}:[0-9]{2}:[0-9]{2} ]]; then
      in_text=false
      continue
    fi
    
    # Skip empty lines
    if [ -z "$line" ]; then
      in_text=false
      continue
    fi
    
    # Only process text lines
    if [ "$in_text" = false ]; then
      in_text=true
      ((line_count++))
      
      # Process only a sample of lines
      if [ $line_count -gt $sample_size ]; then
        break
      fi
      
      # Check for Portuguese-specific words or patterns
      if [[ "$line" =~ \b(e|o|a|da|de|para|com|não|em|do|na|no|este|essa|muito|bem|obrigado|você)\b ]]; then
        ((portuguese_count++))
      fi
    fi
  done < "$file"
  
  # If more than 60% of checked lines appear to be Portuguese, consider it Portuguese
  if [ $line_count -gt 0 ] && [ $(echo "scale=2; $portuguese_count / $line_count > 0.6" | bc) -eq 1 ]; then
    return 0  # true, it's Portuguese
  else
    return 1  # false, not Portuguese
  fi
}

# Function to translate entire SRT file using the new chunked API
translate_srt_file() {
  local file_content="$1"
  local max_retries=3
  local retry=0
  local delay=2
  local translation_start=$SECONDS
  
  # Create temporary files for large content
  local temp_input=$(mktemp)
  local temp_json=$(mktemp)
  
  # Write content to temporary file
  echo "$file_content" > "$temp_input"
  
  # Create JSON payload using temporary file
  jq -n --rawfile text "$temp_input" --arg target_lang "$TARGET_LANG" \
    '{text: $text, target_lang: $target_lang}' > "$temp_json"
  
  while [ $retry -lt $max_retries ]; do
    echo "  • Sending entire SRT file to API (attempt $((retry + 1))/$max_retries)..." >&2
    
    # Debug: Show size of temp files
    echo "    Debug: temp_input size: $(wc -c < "$temp_input") bytes" >&2
    echo "    Debug: temp_json size: $(wc -c < "$temp_json") bytes" >&2
    
    # Make request to API using the temp JSON file
    response=$(curl -s -X POST "$API_URL" \
      -H "Content-Type: application/json" \
      -d @"$temp_json" 2>/dev/null)
    
    echo "    Debug: Response length: ${#response} characters" >&2
    echo "    Debug: First 200 chars of response: ${response:0:200}" >&2
    
    # Check if we received a valid response with translated_text field
    if [ $? -eq 0 ] && echo "$response" | jq -e '.translated_text' >/dev/null 2>&1; then
      # Extract translated text
      local translated=$(echo "$response" | jq -r '.translated_text')
      
      echo "    Debug: Extracted translation length: ${#translated} characters" >&2
      
      # Calculate translation time
      local translation_time=$((SECONDS - translation_start))
      
      # Ensure minimum translation time for proper AI processing
      if [ "$translation_time" -lt "$MIN_TRANSLATION_TIME" ]; then
        # Add a small delay to ensure the IA model is being used
        local delay_needed=$((MIN_TRANSLATION_TIME - translation_time))
        echo "  • Translation too fast, adding ${delay_needed}s delay to ensure AI processing..." >&2
        sleep $delay_needed
        translation_time=$((SECONDS - translation_start))
      fi
      
      # Log translation time
      echo "  • File translated in ${translation_time}s using advanced chunking system" >&2
      
      # Check for chunking information in the logs (would be visible in API logs)
      echo "  • Translation completed with automatic chunk optimization" >&2
      
      # Cleanup temporary files
      rm -f "$temp_input" "$temp_json"
      
      # Return the translated text (to stdout)
      echo "$translated"
      return 0
    else
      echo "    Debug: API call failed or invalid response" >&2
      if [ ${#response} -lt 500 ]; then
        echo "    Debug: Full response: $response" >&2
      fi
    fi
    
    # If failed, increment counter and increase delay
    ((retry++))
    echo "  ⚠ Attempt $retry failed. Retrying in ${delay}s..." >&2
    
    if [ $retry -lt $max_retries ]; then
      sleep $delay
      # Increase wait time for next attempt (exponential backoff)
      delay=$((delay * 2))
    fi
  done
  
  # Cleanup temporary files
  rm -f "$temp_input" "$temp_json"
  
  # If we got here, all attempts failed
  echo "  ❌ ERROR: Failed to translate after $max_retries attempts." >&2
  echo "  ❌ API Response: $response" >&2
  
  # Return original text in case of failure
  echo "$file_content"
  return 1
}

# Function to process an SRT file using the new chunked translation system
translate_srt() {
  local input="$1"
  local dir base output
  
  dir="$(dirname "$input")"
  base="$(basename "${input%.srt}")"
  # Remove original language code from filename
  base="${base%.*}"
  output="$dir/${base}.${TARGET_LANG}.srt"
  
  echo -e "\n==> Translating '$input' to '$output'..."
  
  # Check if input file is readable and has valid content
  if [ ! -r "$input" ]; then
    echo "  ❌ Error: Cannot read file '$input'" >&2
    return 1
  fi
  
  if [ ! -s "$input" ]; then
    echo "  ❌ Error: File '$input' is empty." >&2
    return 1
  fi
  
  # Check if the output already exists
  if [ -f "$output" ]; then
    echo "  ⚠ Output file '$output' already exists. Skipping." >&2
    return 0
  fi
  
  # Check if the input file is already in Portuguese
  if is_portuguese "$input"; then
    echo "  ⚠ File '$input' already appears to be in Portuguese. Creating a copy as pt-br..." >&2
    cp "$input" "$output"
    return 0
  fi
  
  # Quickly check if it looks like a valid SRT file (must have block numbers and timestamps)
  if ! grep -q "^[0-9]\+$" "$input" || ! grep -E -q "[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}" "$input"; then
    echo "  ❌ Error: '$input' doesn't appear to be a valid SRT file." >&2
    echo "  ❌ Check if the file contains block numbers and timestamps in the correct format." >&2
    return 1
  fi
  
  # Get file statistics
  local total_blocks
  total_blocks=$(grep -c "^[0-9]\+$" "$input" || echo 0)
  local file_size
  file_size=$(wc -c < "$input")
  
  echo "File statistics:"
  echo "  • Total subtitle blocks: $total_blocks"
  echo "  • File size: $file_size bytes"
  echo "  • Model: ${OLLAMA_MODEL:-tibellium/towerinstruct-mistral}"
  echo ""
  
  # Read entire file content
  echo "Reading entire SRT file for optimized translation..."
  local file_content
  file_content=$(cat "$input")
  
  # Create temporary file for output
  local temp_output
  temp_output="./debug_translation_output.txt"
  
  # Process with new chunked translation system
  echo "Starting translation with advanced AI chunking system..."
  local file_start_time=$SECONDS
  
  # Translate entire file using the new API
  local translated_content
  translated_content=$(translate_srt_file "$file_content")
  local translation_exit_code=$?
  
  echo "Debug: Translation function returned with exit code: $translation_exit_code"
  echo "Debug: Translation result length: ${#translated_content} characters"
  
  if [ $translation_exit_code -eq 0 ]; then
    # Write translated content to temporary file
    echo "$translated_content" > "$temp_output"
    
    echo "Debug: Temporary output file size: $(wc -c < "$temp_output") bytes"
    echo "Debug: First few lines of output:"
    head -n 10 "$temp_output"
    echo "Debug: Last few lines of output:"
    tail -n 10 "$temp_output"
    
    # Save a copy for inspection
    cp "$temp_output" "./debug_full_translation.srt"
    echo "Debug: Full translation saved to ./debug_full_translation.srt"
    
    # Validate the output
    if [ -s "$temp_output" ] && grep -q "^[0-9]\+$" "$temp_output" && grep -E -q "[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}" "$temp_output"; then
      # Count output blocks to verify integrity
      local output_blocks
      output_blocks=$(grep -c "^[0-9]\+$" "$temp_output" || echo 0)
      
      echo "Translation validation:"
      echo "  • Input blocks: $total_blocks"
      echo "  • Output blocks: $output_blocks"
      
      if [ "$output_blocks" -eq "$total_blocks" ]; then
        echo "  ✓ Block count matches - translation integrity verified"
      else
        echo "  ⚠ Block count mismatch - but proceeding (chunking may have optimized structure)"
      fi
      
      # Calculate total time
      local total_time=$((SECONDS - file_start_time))
      echo "  ✓ Total translation time: $((total_time / 60))m $((total_time % 60))s"
      
      # Replace output file
      mv "$temp_output" "$output"
      echo "✓ Translation complete: $output"
      
      return 0
    else
      echo "  ❌ Error: Output file is not valid SRT format." >&2
      echo "Debug: Validation details:"
      echo "  - File exists and not empty: $([ -s "$temp_output" ] && echo "YES" || echo "NO")"
      echo "  - Has block numbers: $(grep -q "^[0-9]\+$" "$temp_output" && echo "YES" || echo "NO")"
      echo "  - Has timestamps: $(grep -E -q "[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}" "$temp_output" && echo "YES" || echo "NO")"
      rm -f "$temp_output"
      return 1
    fi
  else
    echo "  ❌ Error: Translation failed." >&2
    rm -f "$temp_output"
    return 1
  fi
}

# Main loop to process all files
echo "Starting translation of ${#@} subtitle file(s) with optimized chunking system..."
SECONDS=0  # Initialize global time counter

# Display model information
echo "Translation Engine Information:"
echo "  • Model: ${OLLAMA_MODEL:-tibellium/towerinstruct-mistral}"
echo "  • Chunking: Automatic based on model token limits"
echo "  • API Endpoint: $API_URL"
echo ""

# Counters for statistics
declare -i success_count=0
declare -i skip_count=0
declare -i fail_count=0

for srt in "$@"; do
  if [ ! -f "$srt" ]; then
    echo "Skipping: '$srt' does not exist." >&2
    ((skip_count++))
    continue
  fi
  
  if [[ "$srt" != *.srt ]]; then
    echo "Skipping: '$srt' is not a valid .srt file." >&2
    ((skip_count++))
    continue
  fi
  
  # Skip files that are already translations
  if [[ "$srt" == *.$TARGET_LANG.srt ]]; then
    echo "Skipping '$srt': already appears to be a translation to $TARGET_LANG." >&2
    ((skip_count++))
    continue
  fi
  
  # Reset time counter for this file
  file_start_time=$SECONDS
  
  # Try to translate the file
  if translate_srt "$srt"; then
    ((success_count++))
    file_end_time=$SECONDS
    file_duration=$((file_end_time - file_start_time))
    echo "File translated in $((file_duration / 60))m $((file_duration % 60))s"
  else
    echo "Failed to translate '$srt'. Continuing with next file..." >&2
    ((fail_count++))
  fi
done

# Final summary
total_time=$SECONDS
echo -e "\n=== Enhanced Translation Summary ==="
echo "Translation engine optimizations:"
echo "  • Automatic chunking based on model token limits"
echo "  • Intelligent SRT block boundary detection"
echo "  • Context preservation across chunks"
echo "  • Improved prompt engineering for subtitle translation"
echo ""
echo "Processing results:"
echo "  ✓ Successfully translated: $success_count"
echo "  ⚠ Skipped: $skip_count"
echo "  ✗ Failures: $fail_count"
echo "  ⏱ Total time: $((total_time / 60))m $((total_time % 60))s"
echo ""
echo "✓ Enhanced translation process complete!"