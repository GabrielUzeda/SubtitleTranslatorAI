#!/bin/bash
set -euo pipefail

# Check dependencies
for cmd in ffmpeg file; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "Error: '$cmd' not found. Install ffmpeg." >&2
    exit 1
  fi
done

usage() {
    echo "Usage: $0 <directory> <base_name>"
    echo "Converts all subtitle formats (ASS/SSA/VTT) to SRT format for easier translation."
    echo "Example: $0 ./examples example"
    exit 1
}

# Only check arguments when script is run directly, not when sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -ne 2 ]; then
        usage
    fi
    
    dir="$1"
    base="$2"
fi

convert_subtitles() {
  local dir="$1"
  local base="$2"
  local -a subtitle_files
  local conversion_count=0
  local success_count=0
  local error_count=0
  
  # Find subtitle files (ASS, SSA, VTT) to convert to SRT
  mapfile -t subtitle_files < <(find "$dir" -name "*.ass" -o -name "*.ssa" -o -name "*.vtt" | grep -F "$base" 2>/dev/null)
  
  if [ ${#subtitle_files[@]} -eq 0 ]; then
    echo "   • No subtitle files need conversion (all are already SRT or not found)"
    return 0
  fi
  
  echo -e "\n==> Converting subtitle formats to SRT..."
  echo "   • Found ${#subtitle_files[@]} subtitle file(s) to convert"
  
  for file in "${subtitle_files[@]}"; do
    local filename=$(basename "$file")
    local extension="${file##*.}"
    local base_name="${file%.*}"
    local output_file="${base_name}.srt"
    
    # Verify file exists and is readable
    if [ ! -f "$file" ] || [ ! -r "$file" ]; then
      echo "   • Skipping $filename: File not found or not readable"
      continue
    fi
    
    # Check file size
    if [ ! -s "$file" ]; then
      echo "   • Skipping $filename: File is empty"
      continue
    fi
    
    # Skip if SRT version already exists
    if [ -f "$output_file" ]; then
      echo "   • Skipping $filename: SRT version already exists"
      continue
    fi

    conversion_count=$((conversion_count + 1))
    echo "   • Converting $filename ($extension → SRT)..."
    
    # Create temporary output file
    local temp_output="${output_file}.tmp"
    
    # Convert using ffmpeg
    echo "     • Processing with ffmpeg..."
    
    # Try a simpler ffmpeg command first
    if timeout 30 ffmpeg -nostdin -y -v error -i "$file" -f srt "$temp_output" 2>&1; then
      # Verify the converted file is valid SRT
      if [ -s "$temp_output" ]; then
        # Check if it has SRT sequence numbers and timestamps (simplified validation)
        if grep -q "^[0-9]\+$" "$temp_output" && grep -E -q "[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}" "$temp_output"; then
          # Move temp file to final location
          mv "$temp_output" "$output_file"
          
          # Remove original file after successful conversion
          rm -f "$file"
          
          success_count=$((success_count + 1))
          echo "     ✓ Successfully converted to $(basename "$output_file")"
        else
          echo "     ✗ Converted file is not a valid SRT format" >&2
          rm -f "$temp_output"
          error_count=$((error_count + 1))
        fi
      else
        echo "     ✗ Converted file is empty" >&2
        rm -f "$temp_output"
        error_count=$((error_count + 1))
      fi
    else
      local exit_code=$?
      if [ $exit_code -eq 124 ]; then
        echo "     ✗ Conversion timed out after 30 seconds" >&2
      else
        echo "     ✗ Failed to convert $filename (exit code: $exit_code)" >&2
      fi
      rm -f "$temp_output"
      error_count=$((error_count + 1))
    fi
  done
  
  # Summary
  if [ $conversion_count -gt 0 ]; then
    echo "   • Conversion summary: $success_count successful, $error_count failed"
    
    if [ $success_count -gt 0 ]; then
      echo "   • All converted files are now in SRT format and ready for translation"
    fi
    
    if [ $error_count -gt 0 ]; then
      echo "   ⚠ Some conversions failed. Check the files manually."
    fi
  fi
}

# Special handling for ASS/SSA files that might have complex formatting
convert_ass_ssa_advanced() {
  local dir="$1"
  local base="$2"
  local -a ass_files
  
  # Find ASS/SSA files for fallback conversion
  mapfile -t ass_files < <(find "$dir" -name "*.ass" -o -name "*.ssa" | grep -F "$base" 2>/dev/null)
  
  if [ ${#ass_files[@]} -eq 0 ]; then
    return 0
  fi
  
  echo -e "\n==> Advanced ASS/SSA processing..."
  
  for file in "${ass_files[@]}"; do
    local filename=$(basename "$file")
    local base_name="${file%.*}"
    local output_file="${base_name}.srt"
    
    # Skip if already processed
    if [ ! -f "$file" ]; then
      continue
    fi
    
    echo "   • Processing advanced ASS/SSA: $filename"
    
    # Check if file has complex formatting that might cause issues
    local has_complex_formatting=false
    
    # Check for advanced ASS features
    if grep -q "{\\\\[^}]*}" "$file" || grep -q "Dialogue.*Effect" "$file"; then
      has_complex_formatting=true
      echo "     • Detected complex ASS formatting"
    fi
    
    # Try conversion with different approaches
    local temp_output="${output_file}.tmp"
    local conversion_success=false
    
    # Method 1: Direct ffmpeg conversion
    echo "     • Trying direct conversion..."
    if timeout 30 ffmpeg -nostdin -y -v error -i "$file" -f srt "$temp_output" </dev/null 2>/dev/null; then
      if [ -s "$temp_output" ] && grep -q "^[0-9]\+$" "$temp_output"; then
        conversion_success=true
        echo "     ✓ Converted using direct method"
      fi
    fi
    
    # Method 2: If direct method failed, try with subtitle filter to clean formatting
    if [ "$conversion_success" = false ] && [ "$has_complex_formatting" = true ]; then
      echo "     • Trying with formatting cleanup..."
      rm -f "$temp_output"
      
      if timeout 30 ffmpeg -nostdin -y -v error -i "$file" -vf "subtitles='$file'" -f srt "$temp_output" </dev/null 2>/dev/null; then
        if [ -s "$temp_output" ] && grep -q "^[0-9]\+$" "$temp_output"; then
          conversion_success=true
          echo "     ✓ Converted using cleanup method"
        fi
      fi
    fi
    
    # Finalize conversion
    if [ "$conversion_success" = true ]; then
      mv "$temp_output" "$output_file"
      rm -f "$file"
      echo "     ✓ Advanced conversion completed: $(basename "$output_file")"
    else
      echo "     ✗ Advanced conversion failed for $filename" >&2
      rm -f "$temp_output"
    fi
  done
}

# Function to clean up problematic SRT files after conversion
cleanup_converted_srt() {
  local dir="$1"
  local base="$2"
  local -a srt_files
  
  # Find newly converted SRT files using reliable pattern matching
  mapfile -t srt_files < <(find "$dir" -name "*.srt" -type f 2>/dev/null | grep -F "$base" || true)
  
  if [ ${#srt_files[@]} -eq 0 ]; then
    return 0
  fi
  
  echo -e "\n==> Cleaning up converted SRT files..."
  
  for file in "${srt_files[@]}"; do
    local filename=$(basename "$file")
    local temp_cleaned="${file}.cleaned"
    local needs_cleanup=false
    
    # Check for common conversion artifacts
    if grep -q "<font" "$file" || grep -q "{\\\\[^}]*}" "$file" || grep -q "{\\" "$file"; then
      needs_cleanup=true
      echo "   • Cleaning formatting artifacts from $filename"
      
      # Remove HTML tags and ASS formatting codes
      sed -E '
        # Remove HTML font tags
        s/<[\/]?font[^>]*>//g
        # Remove ASS formatting codes
        s/\{\\[^}]*\}//g
        # Remove other ASS codes
        s/\{[^}]*\}//g
        # Clean up extra spaces
        s/  +/ /g
        # Remove leading/trailing spaces
        s/^ +//g
        s/ +$//g
      ' "$file" > "$temp_cleaned"
      
      # Replace original if cleaning was successful
      if [ -s "$temp_cleaned" ]; then
        mv "$temp_cleaned" "$file"
        echo "     ✓ Cleaned formatting artifacts"
      else
        echo "     ⚠ Cleanup resulted in empty file, keeping original"
        rm -f "$temp_cleaned"
      fi
    fi
  done
}

# Run conversion when script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "==> Starting subtitle format conversion..."
    convert_subtitles "$dir" "$base"
    convert_ass_ssa_advanced "$dir" "$base"
    cleanup_converted_srt "$dir" "$base"
    echo "==> Conversion process complete!"
fi 