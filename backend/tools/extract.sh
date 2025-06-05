#!/bin/bash
set -euo pipefail

# Check dependencies
for cmd in mkvmerge mkvextract jq ffprobe ffmpeg; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "Error: '$cmd' not found. Install mkvtoolnix, jq and ffmpeg." >&2
    exit 1
  fi
done

usage() {
  echo "Usage: $0 <file.mkv>"
  echo "Example: $0 ./examples/example.mkv"
  exit 1
}

[ $# -eq 1 ] || usage

mkv="$1"
if [ ! -f "$mkv" ] || [[ "$mkv" != *.mkv ]]; then
  echo "Error: '$mkv' is not a valid .mkv file." >&2
  exit 1
fi

extract_with_mkvtoolnix() {
  local mkv="$1" 
  local base
  base="$(basename "${mkv%.mkv}")"
  local dir
  dir="$(dirname "$mkv")"
  
  # Fix jq and quotes issue in command
  mkvmerge -J "$mkv" > "/tmp/mkv_info_$$.json"
  
  # Capture only text subtitle tracks
  mapfile -t tracks < <(
    jq -r '.tracks[] | select(.type=="subtitles") | select(.codecID? != null) | select(.codecID | test("S_TEXT/UTF8|S_TEXT/ASCII|S_TEXT/SSA|S_TEXT/ASS|S_TEXT/WEBVTT")) | "\(.id) \(.properties.language // "und") \(.codecID)"' "/tmp/mkv_info_$$.json"
  )
  
  rm -f "/tmp/mkv_info_$$.json"
  
  if [ "${#tracks[@]}" -eq 0 ]; then
    return 1  # no text tracks
  fi
  
  declare -A count idx
  # Initialize counters
  for entry in "${tracks[@]}"; do
    lang=$(echo "$entry" | awk '{print $2}')
    count[$lang]=${count[$lang]:-0}
    count[$lang]=$((count[$lang]+1))
    idx[$lang]=0
  done

  echo "↳ [mkvtoolnix] Extracting ${#tracks[@]} text subtitle track(s) from '$mkv'..."
  
  for entry in "${tracks[@]}"; do
    read -r id lang codec <<< "$entry"
    
    # Determine extension based on codec
    case "$codec" in
      S_TEXT/UTF8|S_TEXT/ASCII) ext="srt" ;;
      S_TEXT/SSA|S_TEXT/ASS)    ext="ass" ;;
      S_TEXT/WEBVTT)            ext="vtt" ;;
      *)                        ext="txt" ;;
    esac
    
    # Numeric suffix if there are duplicates
    if [ "${count[$lang]}" -gt 1 ]; then
      idx[$lang]=$((idx[$lang]+1))
      suf="${idx[$lang]}"
    else
      suf=""
    fi
    
    # Create full path for output file
    out="$dir/${base}.${lang}${suf}.${ext}"
    echo "   • track $id ($lang / $codec) → $out"
    
    # Extract subtitle
    if mkvextract tracks "$mkv" "$id:$out"; then
      echo "     ✓ OK"
    else
      echo "     ✗ Failed on track $id" >&2
    fi
  done
  
  return 0
}

extract_with_ffmpeg() {
  local mkv="$1"
  local base
  base="$(basename "${mkv%.mkv}")"
  local dir
  dir="$(dirname "$mkv")"
  
  echo "↳ [ffmpeg] Fallback: trying to extract with ffprobe + ffmpeg..."

  # Create temporary file to store ffprobe information
  local temp_file="/tmp/ffprobe_info_$$.txt"
  
  # Use JSON format for better parsing
  ffprobe -v error -select_streams s \
    -show_entries stream=index:stream_tags=language \
    -of json "$mkv" > "$temp_file"
    
  if [ ! -s "$temp_file" ]; then
    echo "   • No subtitle tracks found by ffprobe." >&2
    rm -f "$temp_file"
    return 1
  fi
  
  echo "   • Extracting subtitles one by one to avoid issues..."
  
  # Process each subtitle using jq for JSON parsing
  while IFS= read -r line; do
    idx=$(echo "$line" | jq -r '.index')
    lang=$(echo "$line" | jq -r '.tags.language // "und"')
    
    out_file="$dir/${base}.${lang}.srt"
    
    # If a file with this name already exists, add a numeric suffix
    counter=1
    original_out="$out_file"
    while [ -f "$out_file" ]; do
      out_file="${original_out%.srt}${counter}.srt"
      ((counter++))
    done
    
    echo "   • Extracting track $idx ($lang) → $out_file"
    
    # Use -map to select specific track and -c:s to force srt encoding
    if ffmpeg -nostdin -y -v warning -i "$mkv" -map "0:$idx" -c:s srt "$out_file" 2>/dev/null; then
      # Verify if generated file is valid
      if [ -s "$out_file" ] && grep -q "^[0-9]\+$" "$out_file" && grep -q "[0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\},[0-9]\{3\}" "$out_file"; then
        echo "     ✓ OK"
      else
        echo "     ✗ Generated file doesn't appear to be a valid SRT" >&2
        rm -f "$out_file"
      fi
    else
      echo "     ✗ Failed to extract subtitle from index $idx" >&2
      rm -f "$out_file"
    fi
  done < <(jq -c '.streams[]' "$temp_file")
  
  rm -f "$temp_file"
  echo "     ✓ ffmpeg processing complete"
  return 0
}

# Main loop
echo -e "\n==> Processing '$mkv'"

base="$(basename "${mkv%.mkv}")"
dir="$(dirname "$mkv")"

if extract_with_mkvtoolnix "$mkv"; then
  echo "$dir:$base"  # Output directory and base name for filtering
  exit 0
fi

# if mkvtoolnix didn't find text, fallback
if extract_with_ffmpeg "$mkv"; then
  echo "$dir:$base"  # Output directory and base name for filtering
  exit 0
else
  echo "No subtitles extracted from '$mkv'." >&2
  exit 1
fi