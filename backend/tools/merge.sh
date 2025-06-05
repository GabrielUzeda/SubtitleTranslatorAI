#!/bin/bash
set -euo pipefail

# Check if mkvmerge is installed
command -v mkvmerge >/dev/null 2>&1 || {
    echo "Error: mkvmerge is not installed. Install mkvtoolnix." >&2
    exit 1
}

# Check if an MKV file was provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <file.mkv>"
    exit 1
fi

mkv="$1"
[ -f "$mkv" ] || {
    echo "Error: file '$mkv' not found."
    exit 1
}

base="${mkv%.*}"
dir=$(dirname "$mkv")
base_name=$(basename "$base")

echo "Processing: $mkv"

# Extract current subtitle information to avoid duplication
echo "Checking existing subtitles in MKV file..."
mapfile -t existing_tracks < <(mkvmerge -i "$mkv" | grep -i "subtitles" | sed 's/Track ID \([0-9]*\).*/\1/g')
mapfile -t existing_languages < <(mkvinfo "$mkv" | grep -A 5 "Track type: subtitles" | grep "Language" | sed 's/.*Language: \([a-z-]*\).*/\1/g')

# Create hash of existing tracks to check for duplicates
declare -A existing_track_hashes
for track_id in "${existing_tracks[@]}"; do
    # Extract sample content from track to create a hash for comparison
    track_content=$(mkvextract tracks "$mkv" "${track_id}:temp_track_${track_id}.srt" 2>/dev/null || echo "")
    if [ -f "temp_track_${track_id}.srt" ]; then
        track_hash=$(head -n 20 "temp_track_${track_id}.srt" | md5sum | cut -d' ' -f1)
        existing_track_hashes["$track_hash"]="$track_id"
        rm -f "temp_track_${track_id}.srt"
    fi
done

# Find all subtitles related to the file using a more reliable approach
mapfile -t srt_files < <(find "$dir" -name "*.srt" 2>/dev/null | grep -F "$base_name" || true)

if [ ${#srt_files[@]} -eq 0 ]; then
    echo "No subtitles found for: $mkv"
    exit 1
fi

# Prepare arguments for mkvmerge
merge_args=()
merge_args+=("$mkv")

# Array to track which subtitles we're adding to avoid duplicates
declare -A added_subtitle_hashes

# First add the main file
for srt in "${srt_files[@]}"; do
    # Calculate hash for this subtitle to detect duplicates
    srt_hash=$(head -n 20 "$srt" 2>/dev/null | md5sum | cut -d' ' -f1)
    
    # Skip if we already have this subtitle in the MKV or we've already added it
    if [[ -n "${existing_track_hashes[$srt_hash]:-}" ]]; then
        echo "  • Skipping subtitle: $srt (Already exists in MKV)"
        continue
    fi
    
    if [[ -n "${added_subtitle_hashes[$srt_hash]:-}" ]]; then
        echo "  • Skipping subtitle: $srt (Duplicate of ${added_subtitle_hashes[$srt_hash]})"
        continue
    fi
    
    # Mark this subtitle as added
    added_subtitle_hashes["$srt_hash"]="$srt"
    
    # Extract language code from filename
    lang="und"  # Default to "undefined" language
    
    # Try to extract language from filename patterns like .pt-br.srt or .eng.srt
    if [[ "$srt" =~ \.([a-z]{2}(-[a-z]{2})?)\.srt$ ]]; then
        lang="${BASH_REMATCH[1]}"
    fi
    
    # Special handling for common language codes
    if [[ "$srt" == *por* ]]; then
        lang="por"
    elif [[ "$srt" == *eng* ]]; then
        lang="eng" 
    fi
    
    # For translated files, add special name tag
    name=""
    if [[ "$lang" == "pt-br" ]]; then
        name="Português (Traduzido)"
    elif [[ "$lang" == "eng" || "$lang" == "en" ]]; then
        name="English"
    elif [[ "$lang" == "por" ]]; then
        name="Português"
    fi
    
    # Check if it's UTF-8, if not, convert
    if ! file -i "$srt" | grep -q 'charset=utf-8'; then
        echo "⚠️  Converting $srt to UTF-8..."
        iconv -f WINDOWS-1252 -t UTF-8 "$srt" -o "${srt}.utf8"
        if [ $? -ne 0 ]; then
            echo "❌  Failed to convert subtitle: $srt"
            continue
        fi
        merge_file="${srt}.utf8"
    else
        merge_file="$srt"
    fi
    
    echo "  • Adding subtitle: $srt (Language: $lang, Name: $name)"
    
    # Add language option
    merge_args+=("--language" "0:$lang")
    
    # Add track name if available
    if [ -n "$name" ]; then
        merge_args+=("--track-name" "0:$name")
    fi
    
    # Add the subtitle file
    merge_args+=("$merge_file")
done

# If no new subtitles need to be added, exit early
if [ ${#added_subtitle_hashes[@]} -eq 0 ]; then
    echo "No new subtitles to add. MKV file is already up to date."
    exit 0
fi

# Create temporary file
tmp_out="${base}_temp.mkv"

# Merge MKV with all subtitles
echo "Merging subtitles into MKV file..."
mkvmerge -o "$tmp_out" "${merge_args[@]}"
merge_status=$?

if [ $merge_status -eq 0 ] || [ $merge_status -eq 1 ]; then
    # Exit code 1 means non-fatal warnings which we can accept
    mv -f "$tmp_out" "$mkv"
    echo "✔️  File updated: $mkv"
    echo "✔️  Merge complete - subtitles embedded in MKV file"
    
    # Clean up subtitle files after successful merge
    echo "🧹 Cleaning up subtitle files (now embedded in MKV)..."
    for srt in "${srt_files[@]}"; do
        if [ -f "$srt" ]; then
            rm -f "$srt"
            echo "  • Removed: $(basename "$srt")"
        fi
        
        # Also remove any UTF-8 converted files
        if [ -f "${srt}.utf8" ]; then
            rm -f "${srt}.utf8"
            echo "  • Removed: $(basename "${srt}.utf8")"
        fi
    done
    echo "✅ Cleanup complete - only MKV file remains"
    
else
    echo "❌  Error processing $mkv"
    rm -f "$tmp_out"
    exit 1
fi 