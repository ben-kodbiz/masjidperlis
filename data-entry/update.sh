#!/usr/bin/env bash
# Masjid Events Perlis — daily data entry driver (local CSV).
# Usage (from anywhere in the repo):
#     ./data-entry/update.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# 1) Import the CSVs into data/ (validated first; nothing written if broken).
python3 tools/import_google_sheet.py --config data-entry/config.json

# 2) Double-check the merged data.
python3 tools/validate_data.py

echo
echo "Imported and validated. Now commit + push to publish the site:"
echo "  git add data/ && git commit -m 'data: update from CSV' && git push"
