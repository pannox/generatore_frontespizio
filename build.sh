#!/usr/bin/env bash
# Exit on error
set -o errexit

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Crea directory necessarie (NON sovrascrivere uploaded_pdfs/GLOBALE se esiste già con file dal Git)
# La directory uploaded_pdfs/GLOBALE viene già creata dal Git con i PDF
# Creiamo solo le altre directory che servono
mkdir -p thumbnails
mkdir -p data

# Verifica che i PDF GLOBALE siano presenti
echo "Verifica PDF in uploaded_pdfs/GLOBALE..."
if [ -d "uploaded_pdfs/GLOBALE" ]; then
    PDF_COUNT=$(ls -1 uploaded_pdfs/GLOBALE/*.pdf 2>/dev/null | wc -l)
    echo "Trovati $PDF_COUNT file PDF in uploaded_pdfs/GLOBALE"
else
    echo "ATTENZIONE: Directory uploaded_pdfs/GLOBALE non trovata!"
fi

# Crea file JSON se non esistono
if [ ! -f "data/scadenze_passwords.json" ]; then
    echo '{}' > data/scadenze_passwords.json
fi

if [ ! -f "data/historical_data.json" ]; then
    echo '[]' > data/historical_data.json
fi

echo "Build completato con successo!"
