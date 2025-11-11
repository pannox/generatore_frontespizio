#!/usr/bin/env bash
# Exit on error
set -o errexit

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install poppler (necessario per pdf2image)
apt-get update
apt-get install -y poppler-utils

# Crea directory necessarie
mkdir -p uploaded_pdfs/GLOBALE
mkdir -p thumbnails
mkdir -p templates
mkdir -p data

# Crea file JSON se non esistono
if [ ! -f "data/scadenze_passwords.json" ]; then
    echo '{}' > data/scadenze_passwords.json
fi

if [ ! -f "data/historical_data.json" ]; then
    echo '[]' > data/historical_data.json
fi

echo "Build completato con successo!"
