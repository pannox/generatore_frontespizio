"""Script di debug per verificare percorsi e file su Render"""
import os
import sys

print("=" * 80)
print("DEBUG: Verifica percorsi e file")
print("=" * 80)

# Directory corrente
print(f"\n1. CURRENT DIRECTORY: {os.getcwd()}")
print(f"2. __file__ location: {os.path.abspath(__file__)}")
print(f"3. BASE_DIR: {os.path.dirname(os.path.abspath(__file__))}")

# Controlla esistenza directory
dirs_to_check = [
    'uploaded_pdfs',
    'uploaded_pdfs/GLOBALE',
    'templates',
    'static',
    'thumbnails',
    'data'
]

print("\n4. DIRECTORY EXISTENCE:")
for d in dirs_to_check:
    exists = os.path.exists(d)
    print(f"   {d}: {'✓ EXISTS' if exists else '✗ NOT FOUND'}")
    if exists and os.path.isdir(d):
        count = len(os.listdir(d))
        print(f"      → {count} items inside")

# Lista file in uploaded_pdfs/GLOBALE
globale_dir = 'uploaded_pdfs/GLOBALE'
if os.path.exists(globale_dir):
    print(f"\n5. FILES IN {globale_dir}:")
    files = [f for f in os.listdir(globale_dir) if f.endswith('.pdf')]
    print(f"   Total PDF files: {len(files)}")
    if files:
        print("   First 10 files:")
        for f in files[:10]:
            print(f"      - {f}")
else:
    print(f"\n5. {globale_dir} NOT FOUND!")

# Environment variables
print("\n6. ENVIRONMENT:")
print(f"   PORT: {os.environ.get('PORT', 'NOT SET')}")
print(f"   PYTHON_VERSION: {os.environ.get('PYTHON_VERSION', 'NOT SET')}")
print(f"   FLASK_ENV: {os.environ.get('FLASK_ENV', 'NOT SET')}")

print("\n" + "=" * 80)
