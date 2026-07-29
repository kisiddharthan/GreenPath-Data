#!/usr/bin/env bash

set -euo pipefail

BULLETIN_URL="${1:?Usage: $0 <bulletin-url> <html-file> <output-file>}"
HTML_FILE="${2:?Usage: $0 <bulletin-url> <html-file> <output-file>}"
OUTPUT_FILE="${3:?Usage: $0 <bulletin-url> <html-file> <output-file>}"

python -m parser.generate_feed \
  --url "$BULLETIN_URL" \
  --html-file "$HTML_FILE" \
  --output "$OUTPUT_FILE"

python validation/validate_feed.py "$OUTPUT_FILE"

python -m pytest
