#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -euo pipefail

# Print usage function
usage() {
    echo "Usage: $0 <directory_path>"
    echo "Finds and opens all PDF files in the specified directory recursively."
    exit 1
}

# Check if path is provided
if [ "$#" -ne 1 ]; then
    echo "Error: Directory path is required."
    usage
fi

TARGET_DIR="$1"

# Check if the provided path is a directory
if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: '$TARGET_DIR' is not a valid directory."
    exit 1
fi

# Find all PDF files (case-insensitive) in the directory
# Using -print0 and read -r -d '' to safely handle spaces and special characters in filenames
pdf_count=0
while IFS= read -r -d '' pdf_file; do
    echo "Opening: $pdf_file"
    # xdg-open is the standard Linux command to open files with their default application
    xdg-open "$pdf_file"
    pdf_count=$((pdf_count + 1))
done < <(find "$TARGET_DIR" -type f -iname "*.pdf" -print0)

if [ "$pdf_count" -eq 0 ]; then
    echo "No PDF files found in '$TARGET_DIR'."
else
    echo "Opened $pdf_count PDF file(s)."
fi
