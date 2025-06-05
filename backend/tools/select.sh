#!/bin/bash
set -euo pipefail

# Order of priority for languages
declare -a PRIORITY_LANGUAGES=(
  "eng" "en"       # English
  "por" "pt" "pt-br"   # Portuguese
  "spa" "es"       # Spanish
  "fra" "fr"       # French
  "deu" "de"       # German
  "nld" "nl"       # Dutch
  "ita" "it"       # Italian
  "kor" "ko"       # Korean
  "zho" "zh" "cmn" # Chinese
  "rus" "ru"       # Russian
)

# Language names for display
declare -A LANGUAGE_NAMES=(
  ["eng"]="English"
  ["en"]="English"
  ["por"]="Portuguese"
  ["pt"]="Portuguese"
  ["pt-br"]="Portuguese (Brazil)"
  ["spa"]="Spanish"
  ["es"]="Spanish"
  ["fra"]="French"
  ["fr"]="French"
  ["deu"]="German"
  ["de"]="German"
  ["nld"]="Dutch"
  ["nl"]="Dutch"
  ["ita"]="Italian"
  ["it"]="Italian"
  ["kor"]="Korean"
  ["ko"]="Korean"
  ["zho"]="Chinese"
  ["zh"]="Chinese"
  ["cmn"]="Chinese (Mandarin)"
  ["rus"]="Russian"
  ["ru"]="Russian"
  ["und"]="Unknown"
  ["jpn"]="Japanese"
  ["ja"]="Japanese"
)

usage() {
  echo "Usage: $0 <file.mkv>"
  echo "Selects the best subtitle track from an MKV file based on language priority."
  exit 1
}

if [ $# -ne 1 ]; then
  usage
fi

MKV_FILE="$1"

if [ ! -f "$MKV_FILE" ]; then
  echo "Error: File '$MKV_FILE' not found."
  exit 1
fi

if [[ "$MKV_FILE" != *.mkv ]]; then
  echo "Error: File must be an MKV file."
  exit 1
fi

# Display translation model being used
MODEL="${OLLAMA_MODEL:-tibellium/towerinstruct-mistral}"
echo "Using translation model: $MODEL"

# Extract all subtitle tracks with detailed information
echo "Analyzing subtitle tracks in $MKV_FILE..."

# Create temporary file for JSON output
TEMP_JSON=$(mktemp)
trap 'rm -f "$TEMP_JSON"' EXIT

mkvmerge -J "$MKV_FILE" > "$TEMP_JSON"

# Extract subtitle track information: id, language, and codec
mapfile -t SUBTITLE_TRACKS < <(
  jq -r '.tracks[] | select(.type=="subtitles") | "\(.id) \(.properties.language // "und") \(.codecID // "unknown")"' "$TEMP_JSON"
)

if [ ${#SUBTITLE_TRACKS[@]} -eq 0 ]; then
  echo "No subtitle tracks found in $MKV_FILE."
  exit 1
fi

echo "Found ${#SUBTITLE_TRACKS[@]} subtitle tracks."

# Display all tracks for debugging
echo "Available subtitle tracks:"
for track_info in "${SUBTITLE_TRACKS[@]}"; do
  read -r track_id lang codec <<< "$track_info"
  lang_name="${LANGUAGE_NAMES[$lang]:-$lang}"
  echo "  • Track $track_id: $lang_name ($lang) - $codec"
done

# Select the best track based on language priority
best_track=""
best_lang=""
best_lang_name=""

# Try to find a track with text-based subtitle (not PGS/bitmap)
for priority_lang in "${PRIORITY_LANGUAGES[@]}"; do
  for track_info in "${SUBTITLE_TRACKS[@]}"; do
    read -r track_id lang codec <<< "$track_info"
    
    # Skip bitmap/graphical subtitles (PGS, VobSub, etc.)
    if [[ "$codec" == *"PGS"* ]] || [[ "$codec" == *"VobSub"* ]] || [[ "$codec" == *"HDMV"* ]]; then
      continue
    fi
    
    if [ "$lang" = "$priority_lang" ]; then
      best_track="$track_id"
      best_lang="$lang"
      best_lang_name="${LANGUAGE_NAMES[$lang]:-$lang}"
      break 2
    fi
  done
done

# If no text-based track found with priority languages, fallback to first text-based track
if [ -z "$best_track" ]; then
  for track_info in "${SUBTITLE_TRACKS[@]}"; do
    read -r track_id lang codec <<< "$track_info"
    
    # Skip bitmap/graphical subtitles
    if [[ "$codec" == *"PGS"* ]] || [[ "$codec" == *"VobSub"* ]] || [[ "$codec" == *"HDMV"* ]]; then
      continue
    fi
    
    best_track="$track_id"
    best_lang="$lang"
    best_lang_name="${LANGUAGE_NAMES[$lang]:-$lang}"
    break
  done
fi

# If still no track found, use the first available track
if [ -z "$best_track" ]; then
  read -r best_track best_lang codec <<< "${SUBTITLE_TRACKS[0]}"
  best_lang_name="${LANGUAGE_NAMES[$best_lang]:-$best_lang}"
  echo "Warning: No text-based subtitles found, using first available track (may be graphical)."
fi

echo -e "\nSelected subtitle track:"
echo "  • Track $best_track: $best_lang_name (${best_lang})"

# Extract and save the best subtitle
output_dir=$(dirname "$MKV_FILE")
base_name=$(basename "${MKV_FILE%.mkv}")
temp_output="${output_dir}/${base_name}.${best_lang}.temp"
output_file="${output_dir}/${base_name}.${best_lang}.srt"

echo "Extracting best subtitle to: $output_file"
if mkvextract tracks "$MKV_FILE" "${best_track}:${temp_output}" &>/dev/null; then
  # Check if extracted file is ASS/SSA format and convert to SRT
  if head -5 "$temp_output" | grep -q "\[Script Info\]"; then
    echo "  • Converting ASS/SSA format to SRT..."
    # Rename temp file to proper extension for convert.sh
    temp_ass="${output_dir}/${base_name}.${best_lang}.ass"
    mv "$temp_output" "$temp_ass"
    
    # Use convert.sh for professional conversion
    convert_script="$(dirname "$0")/convert.sh"
    if [ -x "$convert_script" ]; then
      # Source the convert.sh functions
      source "$convert_script"
      
      # Call conversion function directly
      convert_subtitles "$output_dir" "${base_name}"
      cleanup_converted_srt "$output_dir" "${base_name}"
      
      if [ -f "$output_file" ]; then
        echo "✓ Successfully converted and saved subtitle to $output_file"
      else
        echo "✗ Conversion failed, trying fallback method"
        # Fallback to ffmpeg direct conversion
        if ffmpeg -nostdin -y -v warning -i "$temp_ass" -c:s srt "$output_file" &>/dev/null; then
          echo "✓ Fallback conversion successful"
          rm -f "$temp_ass"
        else
          echo "✗ All conversion methods failed"
          mv "$temp_ass" "$output_file"
        fi
      fi
    else
      # Fallback to inline conversion if convert.sh not available
      if ffmpeg -nostdin -y -v warning -i "$temp_output" -c:s srt "$output_file" &>/dev/null; then
        echo "✓ Successfully converted and saved subtitle to $output_file"
        rm -f "$temp_output"
      else
        echo "✗ Failed to convert ASS/SSA to SRT, keeping original format"
        mv "$temp_output" "$output_file"
      fi
    fi
  else
    # File is already in the right format
    mv "$temp_output" "$output_file"
    echo "✓ Successfully extracted subtitle track to $output_file"
  fi
  
  # Verify the final file is valid
  if [ -s "$output_file" ]; then
    # Create symbolic link to best subtitle with standardized name
    best_subtitle="${output_dir}/${base_name}.best.srt"
    ln -sf "$(basename "$output_file")" "$best_subtitle"
    echo "✓ Created symbolic link to best subtitle: $best_subtitle"
  else
    echo "⨯ Extracted file is empty or invalid."
    exit 1
  fi
else
  echo "⨯ Failed to extract subtitle track."
  exit 1
fi

# If language is not Portuguese and we should translate
if [ "$best_lang" != "por" ] && [ "$best_lang" != "pt" ] && [ "$best_lang" != "pt-br" ]; then
  # Check if translation script exists
  translate_script="$(dirname "$0")/translate.sh"
  if [ -x "$translate_script" ]; then
    echo -e "\nTranslating best subtitle to Portuguese..."
    "$translate_script" "$output_file" || echo "Warning: Translation completed with warnings"
  else
    echo -e "\nTranslation script not found or not executable: $translate_script"
  fi
fi

echo -e "\n✓ Subtitle selection complete!" 