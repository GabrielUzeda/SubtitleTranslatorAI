#!/bin/bash
set -euo pipefail

usage() {
    echo "Usage: $0 <directory> <base_name>"
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

analyze_subtitles() {
  local dir="$1"
  local base="$2"
  local -a subtitle_files
  local -a sizes
  local total_size=0
  local count=0
  local mean=0
  local std_dev=0
  
  # Find all subtitle files for this movie
  mapfile -t subtitle_files < <(find "$dir" -name "*.srt" -o -name "*.ass" -o -name "*.vtt" | grep -F "$base" 2>/dev/null)
  
  if [ ${#subtitle_files[@]} -eq 0 ]; then
    return
  fi
  
  echo -e "\n==> Analyzing subtitle sizes..."
  
  # Calculate sizes and mean
  for file in "${subtitle_files[@]}"; do
    size=$(wc -c < "$file")
    sizes+=("$size")
    total_size=$((total_size + size))
    count=$((count + 1))
  done
  
  mean=$((total_size / count))
  
  # Calculate standard deviation
  local sum_sq_diff=0
  for size in "${sizes[@]}"; do
    local diff=$((size - mean))
    sum_sq_diff=$((sum_sq_diff + diff * diff))
  done
  std_dev=$(echo "sqrt($sum_sq_diff / $count)" | bc)
  
  # Define threshold (2 standard deviations from mean)
  local threshold=$((2 * std_dev))
  
  echo "   • Average size: $mean bytes"
  echo "   • Standard deviation: $std_dev bytes"
  echo "   • Variation limit: ±$threshold bytes"
  
  # Check each subtitle and remove outliers
  for i in "${!subtitle_files[@]}"; do
    local file="${subtitle_files[$i]}"
    local size="${sizes[$i]}"
    local diff=$((size - mean))
    diff=${diff#-} # Absolute value
    
    if [ $diff -gt $threshold ]; then
      echo "   • Removing suspicious subtitle: $(basename "$file") (size: $size bytes)"
      rm -f "$file"
    else
      echo "   • Keeping subtitle: $(basename "$file") (size: $size bytes)"
    fi
  done
}

check_duplicates() {
  local dir="$1"
  local base="$2"
  local -a subtitle_files
  
  # Find all subtitle files for this movie
  mapfile -t subtitle_files < <(find "$dir" -name "*.srt" -o -name "*.ass" -o -name "*.vtt" | grep -F "$base" 2>/dev/null)
  
  if [ ${#subtitle_files[@]} -le 1 ]; then
    return
  fi
  
  echo -e "\n==> Checking for duplicate subtitles..."
  
  # Compare each pair of files
  for ((i=0; i<${#subtitle_files[@]}-1; i++)); do
    for ((j=i+1; j<${#subtitle_files[@]}; j++)); do
      file1="${subtitle_files[$i]}"
      file2="${subtitle_files[$j]}"
      
      # Skip if either file was already removed
      [ -f "$file1" ] && [ -f "$file2" ] || continue
      
      # Compare files ignoring whitespace and line endings
      if diff -q -w -B "$file1" "$file2" >/dev/null 2>&1; then
        echo "   • Found identical subtitles:"
        echo "     - $(basename "$file1")"
        echo "     - $(basename "$file2")"
        echo "     • Keeping $(basename "$file1") and removing $(basename "$file2")"
        rm -f "$file2"
      fi
    done
  done
}

check_problematic_subtitles() {
  local dir="$1"
  local base="$2"
  local -a subtitle_files
  
  # Find all subtitle files for this movie
  mapfile -t subtitle_files < <(find "$dir" -name "*.srt" -o -name "*.ass" -o -name "*.vtt" | grep -F "$base" 2>/dev/null)
  
  if [ ${#subtitle_files[@]} -eq 0 ]; then
    return
  fi
  
  echo -e "\n==> Checking for problematic subtitles..."
  
  for file in "${subtitle_files[@]}"; do
    # Skip if file was already removed
    [ -f "$file" ] || continue
    
    # Count short duration entries (less than 100ms)
    local short_duration_count=0
    local total_entries=0
    local repeated_text_count=0
    local last_text=""
    local last_timestamp=""
    local similar_timestamp_count=0
    local consecutive_short_duration=0
    local max_consecutive_short=0
    local total_duration=0
    
    while IFS= read -r line; do
      # Skip empty lines and subtitle numbers
      [[ "$line" =~ ^[0-9]+$ ]] && continue
      [[ -z "$line" ]] && continue
      
      # Check for timestamp line
      if [[ "$line" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3} ]]; then
        total_entries=$((total_entries + 1))
        
        # Extract start and end times
        start_time=$(echo "$line" | cut -d' ' -f1)
        end_time=$(echo "$line" | cut -d' ' -f3)
        
        # Convert to milliseconds for comparison
        start_ms=$(echo "$start_time" | awk -F'[:,]' '{print ($1*3600+$2*60+$3)*1000+$4}')
        end_ms=$(echo "$end_time" | awk -F'[:,]' '{print ($1*3600+$2*60+$3)*1000+$4}')
        
        # Check for short duration
        duration=$((end_ms - start_ms))
        total_duration=$((total_duration + duration))
        
        if [ $duration -lt 100 ]; then
          short_duration_count=$((short_duration_count + 1))
          consecutive_short_duration=$((consecutive_short_duration + 1))
          if [ $consecutive_short_duration -gt $max_consecutive_short ]; then
            max_consecutive_short=$consecutive_short_duration
          fi
        else
          consecutive_short_duration=0
        fi
        
        # Check for similar timestamps
        if [ -n "$last_timestamp" ]; then
          last_ms=$(echo "$last_timestamp" | awk -F'[:,]' '{print ($1*3600+$2*60+$3)*1000+$4}')
          if [ $((start_ms - last_ms)) -lt 100 ]; then
            similar_timestamp_count=$((similar_timestamp_count + 1))
          fi
        fi
        last_timestamp="$start_time"
      else
        # Check for repeated text
        if [ "$line" = "$last_text" ]; then
          repeated_text_count=$((repeated_text_count + 1))
        fi
        last_text="$line"
      fi
    done < "$file"
    
    # Calculate percentages and averages
    if [ $total_entries -gt 0 ]; then
      local short_duration_percent=$((short_duration_count * 100 / total_entries))
      local repeated_text_percent=$((repeated_text_count * 100 / total_entries))
      local similar_timestamp_percent=$((similar_timestamp_count * 100 / total_entries))
      local avg_duration=$((total_duration / total_entries))
      
      # More precise conditions for problematic subtitles
      local is_problematic=false
      
      # Check for high percentage of short durations AND consecutive short durations
      if [ $short_duration_percent -gt 80 ] && [ $max_consecutive_short -gt 20 ]; then
        is_problematic=true
      fi
      
      # Check for high percentage of repeated text AND similar timestamps
      if [ $repeated_text_percent -gt 50 ] && [ $similar_timestamp_percent -gt 80 ]; then
        is_problematic=true
      fi
      
      # Check for very low average duration
      if [ $avg_duration -lt 100 ]; then
        is_problematic=true
      fi
      
      if [ "$is_problematic" = true ]; then
        echo "   • Removing problematic subtitle: $(basename "$file")"
        echo "     - Short duration entries: $short_duration_percent%"
        echo "     - Maximum consecutive short entries: $max_consecutive_short"
        echo "     - Repeated text: $repeated_text_percent%"
        echo "     - Similar timestamps: $similar_timestamp_percent%"
        echo "     - Average duration: ${avg_duration}ms"
        rm -f "$file"
      fi
    fi
  done
}

# Run all filters when script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    analyze_subtitles "$dir" "$base"
    check_duplicates "$dir" "$base"
    check_problematic_subtitles "$dir" "$base"
fi
