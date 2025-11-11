import warnings
# Sopprimi tutti i warning di cryptography
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*ARC4.*")
warnings.filterwarnings("ignore", module=".*cryptography.*")
warnings.filterwarnings("ignore", module=".*pypdf.*")

from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for, session, flash
from datetime import datetime
import os
import json
import hashlib
from werkzeug.utils import secure_filename
from pdf_generator import generate_pdf
import uuid
import re
from functools import wraps
from historical_data import get_filtered_history, get_statistics, export_to_csv, get_scadenze_counts_with_names, save_pdf_generation
from thumbnail_service import get_pdf_thumbnail, generate_pdf_thumbnail

app = Flask(__name__)
app.secret_key = 'chiave_segreta_frontespizio_20225'  # Chiave segreta per le sessioni

# Directory base del progetto (assoluta, indipendente da dove viene eseguito)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Password per l'amministrazione (in un progetto reale dovrebbe essere in un file di configurazione sicuro)
ADMIN_PASSWORD = 'treno'
MASTER_PASSWORD = '368769'  # Masterpassword per accesso sempre consentito

# ========== HELPER PER PERCORSI ==========

def get_path(*parts):
    """Ottiene il percorso assoluto relativo alla directory base del progetto"""
    return os.path.join(BASE_DIR, *parts)

# ========== FUNZIONI DI SUPPORTO PDF ==========

def calculate_file_hash(file_content):
    """Calcola hash SHA256 del contenuto file per deduplicazione"""
    return hashlib.sha256(file_content).hexdigest()

def find_existing_pdf(file_content, filename):
    """Cerca se esiste già un PDF con lo stesso contenuto in uploaded_pdfs"""
    file_hash = calculate_file_hash(file_content)

    # Scansiona tutti i file in uploaded_pdfs e sottocartelle
    uploaded_dir = get_path('uploaded_pdfs')
    if not os.path.exists(uploaded_dir):
        return None
    
    for root, dirs, files in os.walk(uploaded_dir):
        for file in files:
            if file.endswith('.pdf'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'rb') as existing_file:
                        existing_content = existing_file.read()
                        existing_hash = calculate_file_hash(existing_content)
                        
                        if existing_hash == file_hash:
                            # Trovato duplicato! Restituisci il path relativo
                            return os.path.relpath(filepath, uploaded_dir)
                except Exception as e:
                    print(f"Errore lettura file {filepath}: {e}")
                    continue
    
    return None

def scan_global_pdfs():
    r"""Scansiona specificamente la cartella uploaded_pdfs\GLOBALE"""
    pdfs = []
    global_dir = get_path('uploaded_pdfs', 'GLOBALE')
    uploaded_pdfs_dir = get_path('uploaded_pdfs')

    if not os.path.exists(global_dir):
        return pdfs

    for file in os.listdir(global_dir):
        if file.endswith('.pdf'):
            filepath = os.path.join(global_dir, file)
            file_size = os.path.getsize(filepath)

            pdfs.append({
                'filename': file,
                'path': os.path.relpath(filepath, uploaded_pdfs_dir),
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2)
            })
    
    # Ordina per nome file
    pdfs.sort(key=lambda x: x['filename'])
    return pdfs

def save_pdf_centralized(file_content, filename):
    """Salva PDF nella cartella centralizzata uploaded_pdfs"""
    uploaded_dir = get_path('uploaded_pdfs')
    os.makedirs(uploaded_dir, exist_ok=True)

    # Usa nome sanitizzato ma mantieni leggibilità
    safe_filename = secure_filename(filename)
    if not safe_filename.lower().endswith('.pdf'):
        safe_filename += '.pdf'

    filepath = os.path.join(uploaded_dir, safe_filename)

    # Se esiste già, aggiungi suffisso numerico
    counter = 1
    original_filepath = filepath
    while os.path.exists(filepath):
        name, ext = os.path.splitext(original_filepath)
        filepath = f"{name}_{counter}{ext}"
        counter += 1

    with open(filepath, 'wb') as f:
        f.write(file_content)

    return os.path.relpath(filepath, uploaded_dir)

# ========== FUNZIONI DI AUTENTICAZIONE ==========

def admin_required(f):
    """Decorator per richiedere l'autenticazione da amministratore"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Path del file di configurazione (assoluto)
CONFIG_FILE = get_path('data', 'flotte.json')

def load_config():
    """Carica la configurazione dal file JSON"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    """Salva la configurazione nel file JSON"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def sanitize_folder_name(name):
    """Sanitizza un nome per usarlo come nome cartella"""
    # Rimuovi caratteri non validi per i nomi di cartella Windows
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Sostituisci spazi con underscore
    name = name.replace(' ', '_')
    # Rimuovi punti multipli
    name = re.sub(r'\.+', '.', name)
    return name.strip()

def sanitize_filename(filename):
    """Sanitizza un nome file per renderlo valido ma mantenibile"""
    # Rimuovi caratteri non validi per i nomi di file Windows
    name = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Rimuovi punti multipli eccetto quello dell'estensione
    if '.' in name:
        base_name, extension = name.rsplit('.', 1)
        base_name = re.sub(r'\.+', '.', base_name)
        name = base_name + '.' + extension
    else:
        name = re.sub(r'\.+', '.', name)
    return name.strip()

def filter_operazioni_by_month(operazioni):
    """Filtra le operazioni in base al mese corrente"""
    current_month = datetime.now().month
    operazioni_filtrate = []

    for op in operazioni:
        mesi_validi = op.get('mesi_validi', [])
        # Se mesi_validi è vuoto o None, l'operazione è sempre visibile
        if not mesi_validi or len(mesi_validi) == 0:
            operazioni_filtrate.append(op)
        # Altrimenti controlla se il mese corrente è nella lista
        elif current_month in mesi_validi:
            operazioni_filtrate.append(op)

    return operazioni_filtrate

# ========== ROUTES PUBBLICHE ==========

@app.route('/')
def index():
    """Homepage con form di selezione"""
    config = load_config()
    return render_template('index.html', flotte=config['flotte'], config=config, is_admin_authenticated=session.get('admin_authenticated', False))

@app.route('/generate', methods=['POST'])
def generate():
    """Genera il PDF in base alle selezioni"""
    print("DEBUG generate: === RICEVUTA RICHIESTA GENERATE ===")
    print(f"DEBUG generate: request.form keys: {list(request.form.keys())}")
    print(f"DEBUG generate: request.form values: {dict(request.form)}")
    print(f"DEBUG generate: request.method: {request.method}")
    
    flotta = request.form.get('flotta')
    scadenze_ids = request.form.getlist('scadenze')
    sede_tecnica = request.form.get('sede_tecnica', '')
    numero_ordine = request.form.get('numero_ordine', '')
    strumento = request.form.get('strumento', '')  # Strumento selezionato (CALIPRI, WPMS, MANUALE)
    
    print(f"DEBUG generate: Estratti valori - flotta: '{flotta}', scadenze: {scadenze_ids}")
    print(f"DEBUG generate: sede_tecnica estratto: '{sede_tecnica}' (tipo: {type(sede_tecnica)})")
    print(f"DEBUG generate: numero_ordine estratto: '{numero_ordine}' (tipo: {type(numero_ordine)})")
    print(f"DEBUG generate: strumento estratto: '{strumento}' (tipo: {type(strumento)})")

    if not flotta or not scadenze_ids:
        print("DEBUG generate: ERRORE - flotta o scadenze mancanti")
        return "Errore: seleziona flotta e almeno una scadenza", 400

    config = load_config()
    print(f"DEBUG: generate - config caricata: {len(config.get('flotte', []))} flotte trovate")
    print(f"DEBUG: generate - text_positions: {config.get('text_positions', 'NON TROVATO')}")

    # Raccogli il numero di copie per ogni scadenza
    scadenze_copie = {}
    print(f"DEBUG generate: Raccolta copie per {len(scadenze_ids)} scadenze")
    for scadenza_id in scadenze_ids:
        copie_key = f'copie_{scadenza_id}'
        copie = request.form.get(copie_key, '1')
        print(f"DEBUG generate: Scadenza {scadenza_id} - chiave {copie_key} - valore raw '{copie}'")
        try:
            copie_num = int(copie)
            if copie_num < 1:
                copie_num = 1
            elif copie_num > 50:
                copie_num = 50
        except (ValueError, TypeError) as e:
            print(f"DEBUG generate: Errore conversione copie per {scadenza_id}: {e}")
            copie_num = 1
        scadenze_copie[scadenza_id] = copie_num
        print(f"DEBUG generate: Scadenza {scadenza_id} - copie finali: {copie_num}")

    print(f"DEBUG generate: Dizionario copie finale: {scadenze_copie}")

    # Genera il PDF con tutte le scadenze selezionate e le copie
    print("DEBUG generate: Chiamo generate_pdf...")
    try:
        pdf_path = generate_pdf(flotta, scadenze_ids, config, sede_tecnica, numero_ordine, strumento, scadenze_copie)
        print(f"DEBUG generate: generate_pdf completato, path: {pdf_path}")
    except Exception as e:
        print(f"DEBUG generate: ERRORE in generate_pdf: {e}")
        import traceback
        traceback.print_exc()
        return f"Errore nella generazione del PDF: {str(e)}", 500

    # Apri il file con l'app predefinita del sistema
    # DISATTIVATO: il PDF viene solo scaricato senza aprirsi automaticamente
    # try:
    #     import subprocess
    #     import platform
    #     if platform.system() == 'Windows':
    #         os.startfile(pdf_path)
    #     elif platform.system() == 'Darwin':
    #         subprocess.Popen(['open', pdf_path])
    #     else:
    #         subprocess.Popen(['xdg-open', pdf_path])
    # except Exception as e:
    #     logger.error(f"Errore apertura PDF: {e}")

    # Invia il file PDF per visualizzazione nel browser
    return send_file(
        pdf_path,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f'completo_{flotta}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )

@app.route('/api/scadenze/<flotta>')
def get_scadenze(flotta):
    """API per ottenere le scadenze disponibili per una flotta"""
    config = load_config()
    for f in config['flotte']:
        if f['id'] == flotta:
            return jsonify({
                'scadenze': f['scadenze'],
                'multioggetto': f.get('multioggetto', False)
            })
    return jsonify({'scadenze': [], 'multioggetto': False}), 404

@app.route('/api/preview_documenti/<flotta_id>')
def get_preview_documenti(flotta_id):
    """API per ottenere l'anteprima dei documenti e operazioni per le scadenze selezionate"""
    scadenze_ids = request.args.get('scadenze', '').split(',')

    if not scadenze_ids or scadenze_ids == ['']:
        return jsonify({'scadenze': []}), 400

    config = load_config()
    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)

    if not flotta:
        return jsonify({'scadenze': []}), 404

    # Filtra solo le scadenze selezionate
    scadenze_filtrate = []
    for scadenza in flotta['scadenze']:
        if scadenza['id'] in scadenze_ids:
            # Filtra le operazioni aggiuntive in base al mese corrente
            operazioni = scadenza.get('operazioni_aggiuntive', [])
            operazioni_filtrate = filter_operazioni_by_month(operazioni)

            scadenze_filtrate.append({
                'id': scadenza['id'],
                'nome': scadenza['nome'],
                'rilevazione_quote': scadenza.get('rilevazione_quote', False),
                'documenti': scadenza.get('documenti', []),
                'operazioni_aggiuntive': operazioni_filtrate
            })

    # Aggiungi operazioni globali filtrate per mese e flotta
    operazioni_globali = config.get('operazioni_globali', [])
    # Filtra per flotta: mostra operazioni globali (senza flotta_id) o quelle specifiche per questa flotta
    operazioni_globali = [op for op in operazioni_globali if not op.get('flotta_id') or op.get('flotta_id') == flotta_id]
    operazioni_globali_filtrate = filter_operazioni_by_month(operazioni_globali)

    return jsonify({
        'scadenze': scadenze_filtrate,
        'operazioni_globali': operazioni_globali_filtrate
    })

@app.route('/api/documenti_flotta/<flotta_id>')
def get_documenti_flotta(flotta_id):
    """API per ottenere tutti i documenti di una flotta (per stampa singola)"""
    config = load_config()
    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)

    if not flotta:
        return jsonify({'documenti': []}), 404

    # Controlla se la flotta è multioggetto
    is_multioggetto = flotta.get('multioggetto', False)

    # Raccoglie tutti i documenti da tutte le scadenze
    tutti_documenti = []
    for scadenza in flotta['scadenze']:
        for doc in scadenza.get('documenti', []):
            # Aggiungi info scadenza al documento
            doc_con_scadenza = doc.copy()
            doc_con_scadenza['scadenza_nome'] = scadenza['nome']
            doc_con_scadenza['scadenza_id'] = scadenza['id']
            tutti_documenti.append(doc_con_scadenza)

    # Se la flotta è multioggetto, raggruppa documenti per nome e somma le copie
    if is_multioggetto:
        documenti_raggruppati = {}
        for doc in tutti_documenti:
            nome_doc = doc.get('nome', 'Senza nome')
            if nome_doc not in documenti_raggruppati:
                # Primo documento con questo nome
                doc_raggruppato = doc.copy()
                doc_raggruppato['copie_totali'] = 1
                documenti_raggruppati[nome_doc] = doc_raggruppato
            else:
                # Documento già esistente, incrementa il contatore
                documenti_raggruppati[nome_doc]['copie_totali'] += 1

        # Converti il dizionario in lista
        documenti_finali = list(documenti_raggruppati.values())
    else:
        # Per flotte standard, mostra tutti i documenti individualmente
        documenti_finali = tutti_documenti

    return jsonify({'documenti': documenti_finali, 'flotta_nome': flotta['nome']})

@app.route('/merge-pdf', methods=['POST'])
def merge_pdf():
    """Unisce più PDF in un unico file"""
    from pdf_utils import merge_pdfs
    import tempfile
    import uuid
    
    try:
        data = request.get_json()
        pdf_paths = data.get('pdf_paths', [])
        
        if not pdf_paths:
            return jsonify({'error': 'Nessun PDF specificato'}), 400
        
        # Verifica che tutti i file esistano
        existing_paths = []
        for path in pdf_paths:
            full_path = os.path.join(os.getcwd(), path.replace('/', os.sep))
            if os.path.exists(full_path):
                existing_paths.append(full_path)
        
        if not existing_paths:
            return jsonify({'error': 'Nessun PDF trovato'}), 404
        
        # Crea un file temporaneo per il PDF unito
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f'documenti_uniti_{timestamp}.pdf'
        output_path = os.path.join('temp_pdfs', output_filename)
        
        # Assicurati che la cartella temp_pdfs esista
        os.makedirs('temp_pdfs', exist_ok=True)
        
        # Unisci i PDF
        merge_pdfs(existing_paths, output_path)
        
        # Ritorna il path del file unito
        return jsonify({
            'success': True,
            'merged_pdf_path': f'temp_pdfs/{output_filename}',
            'filename': output_filename
        })
        
    except Exception as e:
        print(f"Errore nell'unione PDF: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/generate-grid-pdf', methods=['POST'])
def generate_grid_pdf():
    """Genera un PDF con griglia di riferimento per le coordinate"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import black, gray, lightgrey
        import io
        import os
        from datetime import datetime
        
        # Crea il PDF della griglia
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        
        # Titolo
        can.setFont("Helvetica-Bold", 16)
        can.drawCentredString(width/2, height - 30, "GRIGLIA RIFERIMENTO COORDINATE")
        
        can.setFont("Helvetica", 10)
        can.drawCentredString(width/2, height - 50, "Dimensioni A4: 595×842 punti | Origine (0,0) in basso a sinistra")
        
        # Disegna griglia ogni 50 punti
        can.setStrokeColor(lightgrey)
        can.setLineWidth(0.5)
        
        # Linee verticali ogni 50 punti
        for x in range(0, int(width) + 1, 50):
            can.line(x, 0, x, height)
            
        # Linee orizzontali ogni 50 punti  
        for y in range(0, int(height) + 1, 50):
            can.line(0, y, width, y)
        
        # Disegna griglia principale ogni 100 punti (più spessa)
        can.setStrokeColor(gray)
        can.setLineWidth(1)
        
        for x in range(0, int(width) + 1, 100):
            can.line(x, 0, x, height)
            
        for y in range(0, int(height) + 1, 100):
            can.line(0, y, width, y)
        
        # Numerazione coordinate principali
        can.setFont("Helvetica", 8)
        can.setFillColor(black)
        
        # Coordinate X (in basso)
        for x in range(0, int(width) + 1, 100):
            can.drawString(x - 10, 10, str(x))
            
        # Coordinate Y (a sinistra)
        for y in range(0, int(height) + 1, 100):
            can.drawString(10, y - 5, str(y))
        
        # Esempi di posizioni comuni
        can.setFont("Helvetica-Bold", 10)
        can.drawString(50, 750, "Esempio Top-Left (50, 750)")
        can.drawString(50, 700, "Esempio Top-Middle (50, 700)")
        can.drawString(50, 100, "Esempio Bottom-Left (50, 100)")
        can.drawString(400, 750, "Esempio Top-Right (400, 750)")
        can.drawString(400, 100, "Esempio Bottom-Right (400, 100)")
        
        # Note
        can.setFont("Helvetica-Oblique", 9)
        can.drawString(50, height - 80, "✓ Usa questa griglia per identificare le coordinate esatte")
        can.drawString(50, height - 95, "✓ Le coordinate sono in punti (1 punto ≈ 0.35mm)")
        can.drawString(50, height - 110, "✓ L'origine (0,0) è in basso a sinistra")
        
        can.save()
        
        # Salva il file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"griglia_coordinate_{timestamp}.pdf"
        filepath = os.path.join('temp_pdfs', filename)
        
        os.makedirs('temp_pdfs', exist_ok=True)
        
        packet.seek(0)
        with open(filepath, 'wb') as f:
            f.write(packet.getvalue())
        
        return jsonify({
            'success': True,
            'pdf_path': f'temp_pdfs/{filename}'
        })
        
    except Exception as e:
        print(f"Errore nella generazione griglia PDF: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/generate-test-pdf', methods=['POST'])
def generate_test_pdf():
    """Genera un PDF di test con tutte le posizioni attuali su foglio bianco con griglia"""
    try:
        from pdf_utils import add_text_to_pdf_test
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import lightgrey, gray
        import io
        import os
        from datetime import datetime
        
        data = request.get_json()
        
        # Crea un PDF di base con griglia di riferimento
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        
        # Disegna griglia ogni 50 punti (linee sottili)
        can.setStrokeColor(lightgrey)
        can.setLineWidth(0.5)
        
        # Linee verticali ogni 50 punti
        for x in range(0, int(width) + 1, 50):
            can.line(x, 0, x, height)
            
        # Linee orizzontali ogni 50 punti  
        for y in range(0, int(height) + 1, 50):
            can.line(0, y, width, y)
        
        # Disegna griglia principale ogni 100 punti (più spessa)
        can.setStrokeColor(gray)
        can.setLineWidth(1)
        
        for x in range(0, int(width) + 1, 100):
            can.line(x, 0, x, height)
            
        for y in range(0, int(height) + 1, 100):
            can.line(0, y, width, y)
        
        # Numerazione coordinate principali
        can.setFont("Helvetica", 8)
        can.setFillColorRGB(0, 0, 0)
        
        # Coordinate X (in basso)
        for x in range(0, int(width) + 1, 100):
            can.drawString(x - 10, 10, str(x))
            
        # Coordinate Y (a sinistra)
        for y in range(0, int(height) + 1, 100):
            can.drawString(10, y - 5, str(y))
        
        # Titolo del PDF di test
        can.setFont("Helvetica-Bold", 14)
        can.drawCentredString(width/2, height - 30, "PDF TEST - POSIZIONAMENTO CAMPI")
        
        can.setFont("Helvetica", 10)
        can.drawCentredString(width/2, height - 50, f"Font size: {data.get('font_size', 10)} punti")
        
        # Disegna un bordo per riferimento
        can.rect(20, 20, width - 40, height - 40)
        
        # Disegna alcune aree di riferimento
        can.setStrokeColor(lightgrey)
        can.setLineWidth(0.5)
        can.line(0, height/2, width, height/2)  # Linea orizzontale centrale
        can.line(width/2, 0, width/2, height)  # Linea verticale centrale
        
        can.save()
        
        # Salva il PDF temporaneo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_filename = f"temp_test_{timestamp}.pdf"
        temp_filepath = os.path.join('temp_pdfs', temp_filename)
        
        os.makedirs('temp_pdfs', exist_ok=True)
        
        packet.seek(0)
        with open(temp_filepath, 'wb') as f:
            f.write(packet.getvalue())
        
        # Prepara i dati di test per tutti i campi
        test_data = {
            'sede_tecnica': 'SEDE TECNICA',
            'numero_ordine': 'NUMERO ORDINE'
        }
        
        # Aggiungi i campi personalizzati
        custom_fields = data.get('custom_fields', [])
        for field in custom_fields:
            field_key = field['name'].lower().replace(' ', '_')
            test_data[field_key] = field['name'].upper()
        
        # Applica il testo con le coordinate specificate usando la funzione modificata
        final_filename = f"test_coordinate_{timestamp}.pdf"
        final_filepath = os.path.join('temp_pdfs', final_filename)
        
        # Usa una funzione speciale per il test che accetta posizioni personalizzate
        result_path = add_text_to_pdf_test(temp_filepath, final_filepath, test_data, data)
        
        return jsonify({
            'success': True,
            'pdf_path': f'temp_pdfs/{final_filename}'
        })
        
    except Exception as e:
        print(f"Errore nella generazione PDF test: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/upload-template', methods=['POST'])
def upload_template():
    """Carica un template PDF personalizzato"""
    try:
        import os
        from datetime import datetime
        from werkzeug.utils import secure_filename
        
        if 'template' not in request.files:
            return jsonify({'success': False, 'error': 'Nessun file caricato'}), 400
        
        file = request.files['template']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nessun file selezionato'}), 400
        
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'error': 'Il file deve essere un PDF'}), 400
        
        # Crea la cartella templates se non esiste
        os.makedirs('templates', exist_ok=True)
        
        # Salva il file con un nome sicuro
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = secure_filename(f"template_{timestamp}_{file.filename}")
        filepath = os.path.join('templates', filename)
        
        file.save(filepath)
        
        return jsonify({
            'success': True,
            'template_path': f'templates/{filename}',
            'message': 'Template caricato con successo'
        })
        
    except Exception as e:
        print(f"Errore nel caricamento template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/generate-template-test-pdf', methods=['POST'])
def generate_template_test_pdf():
    """Genera un PDF di test usando il template caricato con griglia e testo"""
    try:
        from pdf_utils import add_text_to_pdf_test
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import lightgrey, gray
        import io
        import os
        from datetime import datetime
        
        data = request.get_json()
        template_path = data.get('template_path')
        
        if not template_path or not os.path.exists(template_path):
            return jsonify({'success': False, 'error': 'Template non trovato'}), 400
        
        # Copia il template come base
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_filename = f"temp_template_test_{timestamp}.pdf"
        temp_filepath = os.path.join('temp_pdfs', temp_filename)
        
        os.makedirs('temp_pdfs', exist_ok=True)
        
        # Copia il template caricato
        import shutil
        shutil.copy2(template_path, temp_filepath)
        
        # Aggiungi la griglia di riferimento sopra il template
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        
        # Disegna griglia ogni 50 punti (linee sottili)
        can.setStrokeColor(lightgrey)
        can.setLineWidth(0.5)
        
        # Linee verticali ogni 50 punti
        for x in range(0, int(width) + 1, 50):
            can.line(x, 0, x, height)
            
        # Linee orizzontali ogni 50 punti  
        for y in range(0, int(height) + 1, 50):
            can.line(0, y, width, y)
        
        # Disegna griglia principale ogni 100 punti (più spessa)
        can.setStrokeColor(gray)
        can.setLineWidth(1)
        
        for x in range(0, int(width) + 1, 100):
            can.line(x, 0, x, height)
            
        for y in range(0, int(height) + 1, 100):
            can.line(0, y, width, y)
        
        # Numerazione coordinate principali
        can.setFont("Helvetica", 8)
        can.setFillColorRGB(0, 0, 0)
        
        # Coordinate X (in basso)
        for x in range(0, int(width) + 1, 100):
            can.drawString(x - 10, 10, str(x))
            
        # Coordinate Y (a sinistra)
        for y in range(0, int(height) + 1, 100):
            can.drawString(10, y - 5, str(y))
        
        # Titolo del PDF di test
        can.setFont("Helvetica-Bold", 14)
        can.drawCentredString(width/2, height - 30, "PDF TEST - TEMPLATE PERSONALIZZATO")
        
        can.setFont("Helvetica", 10)
        can.drawCentredString(width/2, height - 50, f"Font size: {data.get('font_size', 10)} punti")
        
        can.save()
        
        # Prepara i dati di test per tutti i campi
        test_data = {
            'sede_tecnica': 'SEDE TECNICA',
            'numero_ordine': 'NUMERO ORDINE'
        }
        
        # Aggiungi i campi personalizzati
        custom_fields = data.get('custom_fields', [])
        for field in custom_fields:
            field_key = field['name'].lower().replace(' ', '_')
            test_data[field_key] = field['name'].upper()
        
        # Applica il testo con le coordinate specificate
        final_filename = f"test_template_coordinate_{timestamp}.pdf"
        final_filepath = os.path.join('temp_pdfs', final_filename)
        
        # Usa la funzione speciale per il test che accetta posizioni personalizzate
        result_path = add_text_to_pdf_test(temp_filepath, final_filepath, test_data, data)
        
        return jsonify({
            'success': True,
            'pdf_path': f'temp_pdfs/{final_filename}'
        })
        
    except Exception as e:
        print(f"Errore nella generazione PDF test template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/custom-fields', methods=['GET'])
def get_custom_fields():
    """Ottiene i campi personalizzati salvati"""
    try:
        config = load_config()
        custom_fields = config.get('custom_fields', [])
        
        return jsonify({
            'success': True,
            'fields': custom_fields
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/custom-fields', methods=['POST'])
def save_custom_fields():
    """Salva i campi personalizzati"""
    try:
        data = request.get_json()
        
        if not data or 'custom_fields' not in data:
            return jsonify({'success': False, 'error': 'Dati campi personalizzati mancanti'}), 400
        
        # Carica la configurazione esistente
        config = load_config()
        
        # Salva solo i campi personalizzati
        config['custom_fields'] = data['custom_fields']
        
        # Salva la configurazione
        save_config(config)
        
        return jsonify({
            'success': True,
            'message': f'Salvati {len(data["custom_fields"])} campi personalizzati'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/text-positions', methods=['GET'])
def get_text_positions():
    """Ottiene le posizioni del testo per i PDF"""
    try:
        config = load_config()
        positions = config.get('text_positions', {
            'sede_x': 50,
            'sede_y': 750,
            'ordine_x': 50,
            'ordine_y': 735,
            'sede_fieldname': '',
            'ordine_fieldname': '',
            'font_size': 'auto',
            'text_mode': 'automatic'
        })
        
        return jsonify({
            'success': True,
            'positions': positions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/text-positions', methods=['POST'])
def save_text_positions():
    """Salva le posizioni del testo per i PDF"""
    try:
        data = request.get_json()
        
        # Validazione dei dati base
        required_fields = ['sede_x', 'sede_y', 'ordine_x', 'ordine_y', 'font_size']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Campo mancante: {field}'}), 400
        
        # Validazione campi personalizzati
        custom_fields = data.get('custom_fields', [])
        for field in custom_fields:
            if not all(key in field for key in ['name', 'x', 'y']):
                return jsonify({'success': False, 'error': 'Campo personalizzato incompleto'}), 400
        
        # Carica la configurazione
        config = load_config()
        
        # Aggiorna le posizioni base
        config['text_positions'] = {
            'sede_x': int(data['sede_x']),
            'sede_y': int(data['sede_y']),
            'ordine_x': int(data['ordine_x']),
            'ordine_y': int(data['ordine_y']),
            'sede_fieldname': data.get('sede_fieldname', ''),
            'ordine_fieldname': data.get('ordine_fieldname', ''),
            'font_size': data['font_size'] if data['font_size'] == 'auto' else int(data['font_size']),
            'text_mode': data.get('text_mode', 'automatic')
        }
        
        # Salva i campi personalizzati
        config['custom_fields'] = custom_fields
        
        # Salva la configurazione
        save_config(config)
        
        return jsonify({
            'success': True,
            'message': 'Posizioni testo salvate con successo'
        })
        
    except Exception as e:
        print(f"Errore nel salvataggio posizioni testo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/clear-cache', methods=['POST'])
@admin_required
def admin_clear_cache():
    """Svuota le cartelle temporanee e la cache del sistema"""
    import shutil
    import glob
    
    try:
        cleared_folders = []
        cleared_files = 0
        
        # Cartelle da svuotare
        temp_folders = ['temp_pdfs', 'temp']
        
        for folder in temp_folders:
            folder_path = os.path.join(os.getcwd(), folder)
            if os.path.exists(folder_path):
                # Conta i file prima di cancellare
                file_count = len(glob.glob(os.path.join(folder_path, '**/*'), recursive=True))
                
                # Rimuovi e ricrea la cartella
                shutil.rmtree(folder_path)
                os.makedirs(folder_path, exist_ok=True)
                
                cleared_folders.append(f"{folder} ({file_count} file)")
                cleared_files += file_count
        
        # Pulisci anche eventuali file PDF temporanei nella root
        temp_files = glob.glob(os.path.join(os.getcwd(), '*_temp.pdf'))
        temp_files.extend(glob.glob(os.path.join(os.getcwd(), 'documenti_*.pdf')))
        
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
                cleared_files += 1
            except:
                pass
        
        message = f"Cartelle svuotate: {', '.join(cleared_folders)}\nFile totali cancellati: {cleared_files}"
        
        return jsonify({
            'success': True,
            'message': message,
            'cleared_files': cleared_files,
            'cleared_folders': cleared_folders
        })
        
    except Exception as e:
        print(f"Errore nella pulizia cache: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/stampa-documenti')
def stampa_documenti():
    """Pagina per stampa documenti singoli"""
    config = load_config()
    return render_template('stampa_documenti.html', flotte=config['flotte'], is_admin_authenticated=session.get('admin_authenticated', False))

@app.route('/temp_pdfs/<path:filename>')
def serve_temp_pdf(filename):
    """Serve i file PDF dalla cartella temp_pdfs"""
    from flask import send_from_directory
    return send_from_directory(get_path('temp_pdfs'), filename)

@app.route('/uploaded_pdfs/<path:filename>')
def serve_pdf(filename):
    """Serve i file PDF dalla cartella uploaded_pdfs"""
    from flask import send_from_directory
    return send_from_directory(get_path('uploaded_pdfs'), filename)

@app.route('/favicon.ico')
def favicon():
    """Serve la favicon"""
    from flask import send_from_directory
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/serve_pdf/<path:filename>')
def serve_pdf_route(filename):
    """Route universale per servire i file PDF da qualsiasi sottocartella di uploaded_pdfs"""
    from flask import send_from_directory
    import os

    uploaded_pdfs_dir = get_path('uploaded_pdfs')

    # Prima prova a trovare il file direttamente nel percorso specificato
    direct_path = os.path.join(uploaded_pdfs_dir, filename)
    if os.path.exists(direct_path):
        return send_from_directory(uploaded_pdfs_dir, filename)

    # Se non trovato, cerca in tutte le sottocartelle
    search_name = os.path.basename(filename)
    for root, dirs, files in os.walk(uploaded_pdfs_dir):
        for file in files:
            if file == search_name:
                # Trovato! Restituisci il percorso relativo
                relative_path = os.path.relpath(os.path.join(root, file), uploaded_pdfs_dir)
                return send_from_directory(uploaded_pdfs_dir, relative_path)

    # Se non trovato, restituisci 404
    return "File non trovato", 404

@app.route('/admin/login', methods=['POST'])
def admin_login():
    """Pagina di login per l'amministrazione"""
    password = request.form.get('password')
    
    if password == ADMIN_PASSWORD or password == MASTER_PASSWORD:
        session['admin_authenticated'] = True
        session.permanent = True  # Rendi la sessione permanente
        
        # Messaggio diverso per masterpassword
        if password == MASTER_PASSWORD:
            flash('Accesso effettuato con masterpassword!', 'success')
        else:
            flash('Accesso effettuato con successo!', 'success')
            
        return redirect(url_for('admin'))
    else:
        flash('Password errata. Riprova.', 'error')
        # Torna alla pagina admin con errore nel modale
        config = load_config()
        return render_template('admin.html', flotte=config['flotte'], config=config, show_login=True, login_error='Password errata. Riprova.')

@app.route('/admin/logout')
def admin_logout():
    """Logout dall'amministrazione"""
    session.clear()
    flash('Disconnessione effettuata.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/change-password', methods=['GET', 'POST'])
@admin_required
def admin_change_password():
    """Cambia password admin"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if current_password != ADMIN_PASSWORD and current_password != MASTER_PASSWORD:
            flash('Password attuale errata.', 'error')
            return render_template('admin_change_password.html')
        
        if new_password != confirm_password:
            flash('Le nuove password non coincidono.', 'error')
            return render_template('admin_change_password.html')
        
        if len(new_password) < 4:
            flash('La nuova password deve essere di almeno 4 caratteri.', 'error')
            return render_template('admin_change_password.html')
        
        # In un progetto reale, qui salveresti la nuova password nel database
        # Per ora, mostriamo solo un messaggio di successo
        flash('Password cambiata con successo! (In un progetto reale verrebbe salvata nel database)', 'success')
        return redirect(url_for('admin'))
    
    return render_template('admin_change_password.html')

# ========== ROUTES AMMINISTRAZIONE ==========

@app.route('/admin')
def admin():
    """Pagina principale amministrazione"""
    config = load_config()
    # Se non autenticato, mostra la pagina admin con il modale di login
    return render_template('admin.html', flotte=config['flotte'], config=config, show_login=not session.get('admin_authenticated'))

@app.route('/admin/flotte')
@admin_required
def admin_flotte():
    """Gestione flotte"""
    config = load_config()
    return render_template('admin_flotte.html', flotte=config['flotte'])

@app.route('/admin/scadenze/<flotta_id>')
@admin_required
def admin_scadenze(flotta_id):
    """Gestione scadenze di una flotta"""
    config = load_config()
    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return "Flotta non trovata", 404
    return render_template('admin_scadenze.html', flotta=flotta)

@app.route('/admin/documenti/<flotta_id>/<scadenza_id>')
@admin_required
def admin_documenti(flotta_id, scadenza_id):
    """Gestione documenti di una scadenza"""
    config = load_config()
    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return "Flotta non trovata", 404
    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return "Scadenza non trovata", 404
    return render_template('admin_documenti.html', flotta=flotta, scadenza=scadenza)

@app.route('/admin/operazioni/<flotta_id>/<scadenza_id>')
@admin_required
def admin_operazioni(flotta_id, scadenza_id):
    """Gestione operazioni di una scadenza"""
    config = load_config()
    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return "Flotta non trovata", 404
    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return "Scadenza non trovata", 404
    return render_template('admin_operazioni.html', flotta=flotta, scadenza=scadenza)

@app.route('/admin/operazioni-globali')
@admin_required
def admin_operazioni_globali():
    """Gestione operazioni globali"""
    config = load_config()
    operazioni_globali = config.get('operazioni_globali', [])
    flotte = config.get('flotte', [])

    # Aggiungi nome flotta a ogni operazione
    for op in operazioni_globali:
        if op.get('flotta_id'):
            flotta = next((f for f in flotte if f['id'] == op['flotta_id']), None)
            if flotta:
                op['flotta_nome'] = flotta['nome']

    return render_template('admin_operazioni_globali.html', operazioni_globali=operazioni_globali, flotte=flotte)

@app.route('/admin/reports')
@admin_required
def admin_reports():
    """Pagina report e statistiche"""
    config = load_config()
    flotte = config.get('flotte', [])
    operazioni_globali = config.get('operazioni_globali', [])

    # Prepara dati per il report
    report_data = {
        'totale_flotte': len(flotte),
        'totale_scadenze': 0,
        'totale_documenti': 0,
        'totale_operazioni': 0,
        'flotte': [],
        'operazioni_globali': []
    }

    # Arricchisci operazioni globali con nome flotta
    for op in operazioni_globali:
        op_copy = op.copy()
        if op.get('flotta_id'):
            flotta = next((f for f in flotte if f['id'] == op['flotta_id']), None)
            if flotta:
                op_copy['flotta_nome'] = flotta['nome']
        report_data['operazioni_globali'].append(op_copy)

    # Processa ogni flotta
    for flotta in flotte:
        flotta_report = {
            'nome': flotta['nome'],
            'id': flotta['id'],
            'scadenze': []
        }

        for scadenza in flotta.get('scadenze', []):
            report_data['totale_scadenze'] += 1

            documenti = scadenza.get('documenti', [])
            operazioni = scadenza.get('operazioni_aggiuntive', [])

            report_data['totale_documenti'] += len(documenti)
            report_data['totale_operazioni'] += len(operazioni)

            scadenza_report = {
                'nome': scadenza['nome'],
                'id': scadenza['id'],
                'documenti': documenti,
                'operazioni': operazioni
            }
            flotta_report['scadenze'].append(scadenza_report)

        report_data['flotte'].append(flotta_report)

    # Aggiungi operazioni globali al totale
    report_data['totale_operazioni'] += len(operazioni_globali)

    # Prepara dati delle scadenze per JavaScript (JSON safe)
    scadenze_per_flotta = {}
    for flotta in report_data['flotte']:
        scadenze_per_flotta[flotta['id']] = [
            {'id': s['id'], 'nome': s['nome']} 
            for s in flotta.get('scadenze', [])
        ]
    report_data['scadenze_per_flotta'] = scadenze_per_flotta

    return render_template('admin_reports.html', report_data=report_data)

@app.route('/admin/reports/export')
@admin_required
def export_reports_csv():
    """Esporta storico generazioni in CSV con filtri"""
    # Ottieni filtri dalla richiesta
    filters = {}
    if request.args.get('flotta'):
        filters['flotta'] = request.args.get('flotta')
    if request.args.get('strumento'):
        filters['strumento'] = request.args.get('strumento')
    if request.args.get('data_da'):
        filters['data_da'] = request.args.get('data_da')
    if request.args.get('data_a'):
        filters['data_a'] = request.args.get('data_a')
    
    # Genera CSV
    csv_content = export_to_csv(filters)
    
    if not csv_content:
        flash('Nessun dato da esportare', 'warning')
        return redirect(url_for('admin_reports'))
    
    # Crea risposta CSV
    from flask import Response
    response = Response(csv_content, mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=storico_pdf_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

@app.route('/api/thumbnail/<path:filename>')
def get_thumbnail_api(filename):
    """
    API endpoint per ottenere thumbnail PDF in base64
    Cerca il file in temp_pdfs e uploaded_pdfs (anche ricorsivamente)
    """
    try:
        # Prova prima in temp_pdfs
        pdf_path = os.path.join('temp_pdfs', filename)

        # Se non esiste, cerca ricorsivamente in uploaded_pdfs
        if not os.path.exists(pdf_path):
            # Cerca ricorsivamente il file in uploaded_pdfs
            for root, dirs, files in os.walk('uploaded_pdfs'):
                if filename in files:
                    pdf_path = os.path.join(root, filename)
                    break

        # Verifica che il file esista
        if not os.path.exists(pdf_path):
            return jsonify({'error': 'File non trovato'}), 404

        # Genera thumbnail
        thumbnail_base64 = get_pdf_thumbnail(pdf_path)

        if thumbnail_base64:
            return jsonify({
                'success': True,
                'thumbnail': f"data:image/png;base64,{thumbnail_base64}",
                'filename': filename
            })
        else:
            return jsonify({'error': 'Impossibile generare thumbnail'}), 500

    except Exception as e:
        print(f"Errore thumbnail API: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500

@app.route('/admin/reports/storico-data')
@admin_required
def get_storico_data():
    """API endpoint per ottenere dati storico per il frontend"""
    try:
        # Ottieni storico e statistiche
        storico = get_filtered_history({})  # Nessun filtro = tutti
        statistiche = get_statistics()
        
        return jsonify({
            'success': True,
            'storico': storico[:50],  # Limita a 50 record per performance
            'statistiche': statistiche
        })
        
    except Exception as e:
        print(f"❌ Errore API storico: {e}")
        return jsonify({'success': False, 'error': 'Errore caricamento dati'}), 500

@app.route('/admin/reports/conteggio-scadenze')
@admin_required
def get_conteggio_scadenze():
    """API endpoint per ottenere conteggio per flotta"""
    try:
        config = load_config()
        conteggi = get_scadenze_counts_with_names(config)
        
        return jsonify({
            'success': True,
            'conteggi': conteggi,
            'totali': len(conteggi)
        })
        
    except Exception as e:
        print(f"❌ Errore API conteggio: {e}")
        return jsonify({'success': False, 'error': 'Errore caricamento conteggi'}), 500

@app.route('/admin/reports/log-dettagliato')
@admin_required
def get_log_dettagliato():
    """API endpoint per ottenere log dettagliato di tutte le stampe"""
    try:
        from historical_data import load_pdf_history
        config = load_config()
        
        # Carica tutto lo storico
        history = load_pdf_history()
        
        # Arricchisci con nomi flotte
        flotte_dict = {f['id']: f['nome'] for f in config.get('flotte', [])}
        
        log_entries = []
        for entry in history:
            # Trova nomi scadenze
            scadenze_nomi = []
            flotta_nome = flotte_dict.get(entry.get('flotta_id', ''), 'Flotta sconosciuta')
            
            if entry.get('scadenze_ids'):
                for flotta in config.get('flotte', []):
                    if flotta['id'] == entry.get('flotta_id'):
                        for scadenza in flotta.get('scadenze', []):
                            if scadenza['id'] in entry['scadenze_ids']:
                                scadenze_nomi.append(scadenza['nome'])
            
            # Calcola documenti e operazioni se mancano nei dati storici
            numero_documenti = entry.get('numero_documenti', 0)
            numero_operazioni = entry.get('numero_operazioni', 0)
            
            # Se i conteggi sono 0, prova a calcolarli dai dati attuali
            if numero_documenti == 0 or numero_operazioni == 0:
                flotta_id = entry.get('flotta_id', '')
                scadenze_ids = entry.get('scadenze_ids', [])
                strumento = entry.get('strumento', '')
                
                for flotta in config.get('flotte', []):
                    if flotta['id'] == flotta_id:
                        for scadenza in flotta.get('scadenze', []):
                            if scadenza['id'] in scadenze_ids:
                                # Conta documenti
                                if numero_documenti == 0:
                                    documenti = scadenza.get('documenti', [])
                                    if strumento and strumento != 'Standard':
                                        # Filtra per strumento
                                        documenti_filtrati = [d for d in documenti if not d.get('strumento') or d.get('strumento') == strumento]
                                        numero_documenti += len(documenti_filtrati)
                                    else:
                                        numero_documenti += len(documenti)
                                
                                # Conta operazioni
                                if numero_operazioni == 0:
                                    numero_operazioni += len(scadenza.get('operazioni_aggiuntive', []))
                
                # Aggiungi operazioni globali
                if numero_operazioni == 0 or entry.get('numero_operazioni', 0) == 0:
                    operazioni_globali = config.get('operazioni_globali', [])
                    if operazioni_globali:
                        numero_operazioni += len(operazioni_globali)
            
            log_entries.append({
                'id': entry.get('id', ''),
                'data': entry.get('date', ''),
                'timestamp': entry.get('timestamp', ''),
                'flotta_nome': flotta_nome,
                'flotta_id': entry.get('flotta_id', ''),
                'scadenze_nomi': scadenze_nomi,
                'numero_scadenze': len(entry.get('scadenze_ids', [])),
                'strumento': entry.get('strumento', 'Standard'),
                'sede_tecnica': entry.get('sede_tecnica', ''),
                'numero_ordine': entry.get('numero_ordine', ''),
                'numero_documenti': numero_documenti,
                'numero_operazioni': numero_operazioni
            })
        
        # Ordina per data decrescente (più recenti prima)
        log_entries.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            'success': True,
            'log': log_entries,
            'totale': len(log_entries)
        })
        
    except Exception as e:
        print(f"❌ Errore API log dettagliato: {e}")
        return jsonify({'success': False, 'error': 'Errore caricamento log'}), 500

@app.route('/admin/reports/azzera-cronologia', methods=['POST'])
@admin_required
def azzera_cronologia():
    """API endpoint per azzerare completamente la cronologia delle stampe"""
    try:
        import os
        
        # Percorsi dei file da azzerare
        history_file = 'data/pdf_history.json'
        counter_file = 'data/scadenze_counter.json'
        
        # Azzera il file storico
        if os.path.exists(history_file):
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        
        # Azzera il file contatori
        if os.path.exists(counter_file):
            with open(counter_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'Cronologia azzerata con successo'
        })
        
    except Exception as e:
        print(f"❌ Errore azzeramento cronologia: {e}")
        return jsonify({'success': False, 'error': 'Errore durante l\'azzeramento'}), 500

# Altre route admin...
@app.route('/admin/reports/export-pdf')
def export_report_pdf():
    """Esporta report in PDF con filtri opzionali"""
    from report_pdf_generator import generate_report_pdf

    # Ottieni filtri da query parameters
    flotta_id_filter = request.args.get('flotta_id', '')
    scadenza_id_filter = request.args.get('scadenza_id', '')

    config = load_config()
    flotte = config.get('flotte', [])
    operazioni_globali = config.get('operazioni_globali', [])

    # Applica filtro flotta se specificato
    if flotta_id_filter:
        flotte = [f for f in flotte if f['id'] == flotta_id_filter]

    # Prepara dati per il report
    report_data = {
        'totale_flotte': len(flotte),
        'totale_scadenze': 0,
        'totale_documenti': 0,
        'totale_operazioni': 0,
        'flotte': [],
        'operazioni_globali': []
    }

    # Arricchisci operazioni globali con nome flotta
    for op in operazioni_globali:
        op_copy = op.copy()
        if op.get('flotta_id'):
            flotta = next((f for f in config.get('flotte', []) if f['id'] == op['flotta_id']), None)
            if flotta:
                op_copy['flotta_nome'] = flotta['nome']
        report_data['operazioni_globali'].append(op_copy)

    # Processa ogni flotta
    for flotta in flotte:
        flotta_report = {
            'nome': flotta['nome'],
            'id': flotta['id'],
            'scadenze': []
        }

        scadenze = flotta.get('scadenze', [])

        # Applica filtro scadenza se specificato
        if scadenza_id_filter:
            scadenze = [s for s in scadenze if s['id'] == scadenza_id_filter]

        for scadenza in scadenze:
            report_data['totale_scadenze'] += 1

            documenti = scadenza.get('documenti', [])
            operazioni = scadenza.get('operazioni_aggiuntive', [])

            report_data['totale_documenti'] += len(documenti)
            report_data['totale_operazioni'] += len(operazioni)

            scadenza_report = {
                'nome': scadenza['nome'],
                'id': scadenza['id'],
                'documenti': documenti,
                'operazioni': operazioni
            }

            flotta_report['scadenze'].append(scadenza_report)

        # Aggiungi la flotta solo se ha scadenze
        if flotta_report['scadenze']:
            report_data['flotte'].append(flotta_report)

    # Aggiungi operazioni globali al totale
    report_data['totale_operazioni'] += len(operazioni_globali)

    # Genera il PDF
    pdf_path = generate_report_pdf(report_data)

    # Invia il file PDF
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=f'report_frontespizio_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )

@app.route('/api/admin/versione', methods=['PUT'])
def api_update_versione():
    """Aggiorna versione del sistema"""
    data = request.json
    config = load_config()

    config['versione'] = {
        'numero': data['numero'],
        'data': data['data']
    }
    
    save_config(config)
    return jsonify({'success': True, 'versione': config['versione']})

# ========== API AMMINISTRAZIONE - FLOTTE ==========

@app.route('/api/admin/flotte', methods=['POST'])
def api_add_flotta():
    """Aggiungi nuova flotta"""
    data = request.json
    config = load_config()

    new_flotta = {
        'id': str(uuid.uuid4())[:8],
        'nome': data['nome'],
        'multioggetto': data.get('multioggetto', False),
        'scadenze': []
    }

    config['flotte'].append(new_flotta)
    save_config(config)

    return jsonify({'success': True, 'flotta': new_flotta})

@app.route('/api/admin/flotte/<flotta_id>', methods=['PUT'])
def api_update_flotta(flotta_id):
    """Modifica flotta"""
    data = request.json
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    flotta['nome'] = data['nome']
    flotta['multioggetto'] = data.get('multioggetto', False)
    save_config(config)

    return jsonify({'success': True, 'flotta': flotta})

@app.route('/api/admin/flotte/<flotta_id>', methods=['DELETE'])
def api_delete_flotta(flotta_id):
    """Elimina flotta"""
    config = load_config()
    config['flotte'] = [f for f in config['flotte'] if f['id'] != flotta_id]
    save_config(config)

    return jsonify({'success': True})

@app.route('/api/admin/flotte/reorder', methods=['POST'])
def api_reorder_flotte():
    """Riordina flotte tramite drag and drop"""
    data = request.json
    from_id = data.get('fromId')
    to_id = data.get('toId')
    config = load_config()

    flotte = config['flotte']
    from_index = next((i for i, f in enumerate(flotte) if f['id'] == from_id), None)
    to_index = next((i for i, f in enumerate(flotte) if f['id'] == to_id), None)

    if from_index is None or to_index is None:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    # Sposta l'elemento dalla posizione from_index a to_index
    flotta_moved = flotte.pop(from_index)
    flotte.insert(to_index, flotta_moved)

    save_config(config)
    return jsonify({'success': True})

@app.route('/api/admin/flotte/<flotta_id>/upload-template', methods=['POST'])
def api_upload_template_flotta(flotta_id):
    """Upload del PDF template per le operazioni aggiuntive della flotta"""
    if 'template' not in request.files:
        return jsonify({'success': False, 'error': 'Nessun file caricato'}), 400

    file = request.files['template']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nessun file selezionato'}), 400

    if not file.filename.endswith('.pdf'):
        return jsonify({'success': False, 'error': 'Solo file PDF sono permessi'}), 400

    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    # Crea cartella per i template con nome leggibile
    flotta_folder = sanitize_folder_name(flotta['nome'])
    template_dir = os.path.join('operazioni_templates', flotta_folder)
    os.makedirs(template_dir, exist_ok=True)

    # Salva il file con il nome originale sanitizzato
    filename = sanitize_filename(file.filename)
    filepath = os.path.join(template_dir, filename)
    file.save(filepath)

    # Aggiorna il path nel config
    flotta['operazioni_pdf_template'] = filepath
    save_config(config)

    return jsonify({'success': True, 'path': filepath})

# ========== API AMMINISTRAZIONE - SCADENZE ==========

@app.route('/api/admin/scadenze/<flotta_id>', methods=['POST'])
def api_add_scadenza(flotta_id):
    """Aggiungi nuova scadenza"""
    data = request.json
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    new_scadenza = {
        'id': str(uuid.uuid4())[:8],
        'nome': data['nome'],
        'descrizione': data.get('descrizione', ''),
        'rilevazione_quote': data.get('rilevazione_quote', False),
        'documenti': [],
        'operazioni_aggiuntive': []
    }

    flotta['scadenze'].append(new_scadenza)
    save_config(config)

    return jsonify({'success': True, 'scadenza': new_scadenza})

@app.route('/api/admin/scadenze/<flotta_id>/<scadenza_id>', methods=['PUT'])
def api_update_scadenza(flotta_id, scadenza_id):
    """Modifica scadenza"""
    data = request.json
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    scadenza['nome'] = data['nome']
    scadenza['descrizione'] = data.get('descrizione', '')
    scadenza['rilevazione_quote'] = data.get('rilevazione_quote', False)
    save_config(config)

    return jsonify({'success': True, 'scadenza': scadenza})

@app.route('/api/admin/scadenze/<flotta_id>/<scadenza_id>', methods=['DELETE'])
def api_delete_scadenza(flotta_id, scadenza_id):
    """Elimina scadenza"""
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    flotta['scadenze'] = [s for s in flotta['scadenze'] if s['id'] != scadenza_id]
    save_config(config)

    return jsonify({'success': True})

@app.route('/api/admin/scadenze/<flotta_id>/reorder', methods=['POST'])
def api_reorder_scadenze(flotta_id):
    """Riordina scadenze tramite drag and drop"""
    data = request.json
    from_id = data.get('fromId')
    to_id = data.get('toId')
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenze = flotta['scadenze']
    from_index = next((i for i, s in enumerate(scadenze) if s['id'] == from_id), None)
    to_index = next((i for i, s in enumerate(scadenze) if s['id'] == to_id), None)

    if from_index is None or to_index is None:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    # Sposta l'elemento dalla posizione from_index a to_index
    scadenza_moved = scadenze.pop(from_index)
    scadenze.insert(to_index, scadenza_moved)

    save_config(config)
    return jsonify({'success': True})

@app.route('/api/admin/scadenze/<flotta_id>/<scadenza_id>/upload-template', methods=['POST'])
def api_upload_template_operazioni(flotta_id, scadenza_id):
    """Upload del PDF template per le operazioni aggiuntive"""
    if 'template' not in request.files:
        return jsonify({'success': False, 'error': 'Nessun file caricato'}), 400

    file = request.files['template']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nessun file selezionato'}), 400

    if not file.filename.endswith('.pdf'):
        return jsonify({'success': False, 'error': 'Solo file PDF sono permessi'}), 400

    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    # Crea cartella per i template con nomi leggibili
    flotta_folder = sanitize_folder_name(flotta['nome'])
    scadenza_folder = sanitize_folder_name(scadenza['nome'])
    template_dir = os.path.join('operazioni_templates', flotta_folder)
    os.makedirs(template_dir, exist_ok=True)

    # Salva il file con il nome originale sanitizzato
    filename = sanitize_filename(file.filename)
    filepath = os.path.join(template_dir, filename)
    file.save(filepath)

    # Aggiorna il path nel config
    scadenza['operazioni_pdf_template'] = filepath
    save_config(config)

    return jsonify({'success': True, 'path': filepath})

# ========== API AMMINISTRAZIONE - DOCUMENTI ==========

@app.route('/api/admin/documenti/<flotta_id>/<scadenza_id>', methods=['POST'])
def api_add_documento(flotta_id, scadenza_id):
    """Aggiungi nuovo documento con upload PDF o solo voce"""
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    # Ottieni dati dal form
    nome = request.form.get('nome')
    obbligatorio = request.form.get('obbligatorio') == 'true'
    strumento = request.form.get('strumento', '')  # CALIPRI, WPMS, MANUALE o vuoto
    pdf_path = request.form.get('pdf_path')  # Path PDF esistente

    new_documento = {
        'id': str(uuid.uuid4())[:8],
        'nome': nome,
        'obbligatorio': obbligatorio,
        'strumento': strumento
    }

    # Gestione PDF: upload nuovo OR usa esistente (opzionale)
    if pdf_path:
        # Usa PDF esistente
        new_documento['pdf_path'] = pdf_path
    elif 'pdf' in request.files:
        # Upload nuovo PDF con deduplicazione
        file = request.files['pdf']
        if file and file.filename.endswith('.pdf'):
            # Leggi il contenuto del file per calcolare hash
            file_content = file.read()
            file.seek(0)  # Reset cursor
            
            # Controlla se esiste già un PDF con lo stesso contenuto
            existing_pdf_path = find_existing_pdf(file_content, file.filename)
            
            if existing_pdf_path:
                # Usa il PDF esistente
                new_documento['pdf_path'] = existing_pdf_path
            else:
                # Salva nuovo PDF nella cartella centralizzata
                saved_path = save_pdf_centralized(file_content, file.filename)
                new_documento['pdf_path'] = saved_path
    # Se non c'è PDF, crea comunque il documento (solo voce)

    scadenza['documenti'].append(new_documento)
    save_config(config)

    return jsonify({'success': True, 'documento': new_documento})

@app.route('/api/admin/documenti/<flotta_id>/<scadenza_id>/<documento_id>', methods=['PUT'])
def api_update_documento(flotta_id, scadenza_id, documento_id):
    """Modifica documento"""
    data = request.json
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    documento = next((d for d in scadenza['documenti'] if d['id'] == documento_id), None)
    if not documento:
        return jsonify({'success': False, 'error': 'Documento non trovato'}), 404

    documento['nome'] = data['nome']
    documento['obbligatorio'] = data.get('obbligatorio', False)
    save_config(config)

    return jsonify({'success': True, 'documento': documento})

@app.route('/api/admin/documenti/<flotta_id>/<scadenza_id>/<documento_id>', methods=['DELETE'])
def api_delete_documento(flotta_id, scadenza_id, documento_id):
    """Elimina documento"""
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    scadenza['documenti'] = [d for d in scadenza['documenti'] if d['id'] != documento_id]
    save_config(config)

    return jsonify({'success': True})

@app.route('/api/admin/documenti/<flotta_id>/<scadenza_id>/reorder', methods=['POST'])
def api_reorder_documenti(flotta_id, scadenza_id):
    """Riordina documenti tramite drag and drop"""
    data = request.json
    new_order = data.get('order', [])
    
    config = load_config()
    
    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404
    
    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404
    
    # Riordina i documenti secondo il nuovo ordine
    documenti_dict = {d['id']: d for d in scadenza['documenti']}
    scadenza['documenti'] = [documenti_dict[doc_id] for doc_id in new_order if doc_id in documenti_dict]
    
    save_config(config)
    
    return jsonify({'success': True})

@app.route('/api/upload_pdf/<flotta_id>/<scadenza_id>/<documento_id>', methods=['POST'])
def api_upload_pdf(flotta_id, scadenza_id, documento_id):
    """Upload PDF per documento con deduplicazione intelligente"""
    if 'pdf' not in request.files:
        return jsonify({'success': False, 'error': 'Nessun file caricato'}), 400

    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nessun file selezionato'}), 400

    if not file.filename.endswith('.pdf'):
        return jsonify({'success': False, 'error': 'Solo file PDF sono permessi'}), 400

    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    documento = next((d for d in scadenza['documenti'] if d['id'] == documento_id), None)
    if not documento:
        return jsonify({'success': False, 'error': 'Documento non trovato'}), 404

    # Leggi il contenuto del file per calcolare hash
    file_content = file.read()
    file.seek(0)  # Reset cursor per eventuali riutilizzi

    # Controlla se esiste già un PDF con lo stesso contenuto
    existing_pdf_path = find_existing_pdf(file_content, file.filename)
    
    if existing_pdf_path:
        # Usa il PDF esistente
        pdf_path = existing_pdf_path
        status = "linked"
        message = f"PDF collegato a file esistente: {existing_pdf_path}"
    else:
        # Salva nuovo PDF nella cartella centralizzata
        pdf_path = save_pdf_centralized(file_content, file.filename)
        status = "uploaded"
        message = f"PDF caricato come nuovo: {pdf_path}"

    # Aggiorna il path nel config (mantieni nome leggibile per frontend)
    documento['pdf_path'] = pdf_path
    save_config(config)

    return jsonify({
        'success': True, 
        'path': pdf_path,
        'status': status,
        'message': message,
        'filename': os.path.basename(pdf_path)
    })

@app.route('/api/available_pdfs', methods=['GET'])
def api_available_pdfs():
    r"""Restituisce la lista di tutti i PDF disponibili in uploaded_pdfs\GLOBALE"""
    # Prima scansiona la cartella GLOBALE
    pdfs = scan_global_pdfs()
    
    # Poi scansiona altre cartelle per completezza
    uploaded_dir = 'uploaded_pdfs'
    if os.path.exists(uploaded_dir):
        for root, dirs, files in os.walk(uploaded_dir):
            # Salta la cartella GLOBALE perché già scansionata
            if 'GLOBALE' in root:
                continue
                
            for file in files:
                if file.endswith('.pdf'):
                    filepath = os.path.join(root, file)
                    relative_path = os.path.relpath(filepath, uploaded_dir)
                    file_size = os.path.getsize(filepath)
                    
                    pdfs.append({
                        'filename': file,
                        'path': relative_path,
                        'size': file_size,
                        'size_mb': round(file_size / (1024 * 1024), 2)
                    })
    
    # Ordina per nome file
    pdfs.sort(key=lambda x: x['filename'])
    
    return jsonify({'success': True, 'pdfs': pdfs})

@app.route('/api/refresh_pdfs', methods=['POST'])
def api_refresh_pdfs():
    """Forza il refresh della scansione PDF (utile per nuovi file aggiunti manualmente)"""
    try:
        # Forza una nuova scansione completa
        pdfs = scan_global_pdfs()
        
        # Aggiungi altre cartelle se presenti
        uploaded_dir = 'uploaded_pdfs'
        if os.path.exists(uploaded_dir):
            for root, dirs, files in os.walk(uploaded_dir):
                if 'GLOBALE' in root:
                    continue
                    
                for file in files:
                    if file.endswith('.pdf'):
                        filepath = os.path.join(root, file)
                        relative_path = os.path.relpath(filepath, uploaded_dir)
                        file_size = os.path.getsize(filepath)
                        
                        pdfs.append({
                            'filename': file,
                            'path': relative_path,
                            'size': file_size,
                            'size_mb': round(file_size / (1024 * 1024), 2)
                        })
        
        pdfs.sort(key=lambda x: x['filename'])
        
        return jsonify({
            'success': True, 
            'pdfs': pdfs,
            'message': f'Trovati {len(pdfs)} PDF disponibili'
        })
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': f'Errore durante il refresh: {str(e)}'
        }), 500

@app.route('/api/check_responsabili_pdf', methods=['GET'])
def api_check_responsabili_pdf():
    """Verifica se il PDF responsabili esiste"""
    try:
        filepath = os.path.join('uploaded_pdfs', 'GLOBALE', 'RESP_MAN elenco responsabili manutenzione.pdf')
        exists = os.path.exists(filepath)
        
        return jsonify({
            'success': True, 
            'exists': exists,
            'path': 'GLOBALE/RESP_MAN elenco responsabili manutenzione.pdf' if exists else None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Errore durante la verifica: {str(e)}'}), 500

@app.route('/api/delete_responsabili_pdf', methods=['POST'])
def api_delete_responsabili_pdf():
    """Cancella il PDF responsabili manutenzione"""
    try:
        # Percorso del file
        filepath = os.path.join('uploaded_pdfs', 'GLOBALE', 'RESP_MAN elenco responsabili manutenzione.pdf')
        
        # Rimuovi il file se esiste
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Aggiorna il config
        config = load_config()
        config['responsabili_pdf_exists'] = False
        save_config(config)
        
        return jsonify({
            'success': True, 
            'message': 'PDF responsabili cancellato con successo'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Errore durante la cancellazione: {str(e)}'}), 500

@app.route('/api/upload_responsabili_pdf', methods=['POST'])
def api_upload_responsabili_pdf():
    """Carica il PDF responsabili manutenzione"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Nessun file ricevuto'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nessun file selezionato'}), 400
        
        if not file.filename.endswith('.pdf'):
            return jsonify({'success': False, 'error': 'Il file deve essere un PDF'}), 400
        
        # Crea la cartella GLOBALE se non esiste
        global_dir = os.path.join('uploaded_pdfs', 'GLOBALE')
        os.makedirs(global_dir, exist_ok=True)
        
        # Salva con nome fisso
        filename = 'RESP_MAN elenco responsabili manutenzione.pdf'
        filepath = os.path.join(global_dir, filename)
        
        # Rimuovi il file esistente se presente
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Salva il nuovo file
        file.save(filepath)
        
        # Aggiorna il config per indicare che il PDF esiste
        config = load_config()
        config['responsabili_pdf_exists'] = True
        save_config(config)
        
        return jsonify({
            'success': True, 
            'message': 'PDF responsabili caricato con successo',
            'filename': filename,
            'path': os.path.relpath(filepath, 'uploaded_pdfs')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Errore durante il caricamento: {str(e)}'}), 500

@app.route('/api/portali', methods=['GET'])
def api_get_portali():
    """Ottieni le informazioni sui portali"""
    config = load_config()
    portali = config.get('portali', {
        'wpms': {'id': '136042', 'scadenza': '05/12/2025'},
        'tornio': {'id': '135138', 'scadenza': '02/12/2025'}
    })
    return jsonify({'success': True, 'portali': portali})

@app.route('/api/portali', methods=['PUT'])
def api_update_portali():
    """Aggiorna le informazioni sui portali"""
    data = request.json
    config = load_config()
    
    # Valida i dati
    required_fields = ['wpms', 'tornio']
    for field in required_fields:
        if field not in data or 'id' not in data[field] or 'scadenza' not in data[field]:
            return jsonify({'success': False, 'error': f'Dati mancanti per {field}'}), 400
    
    # Aggiorna il config
    config['portali'] = data
    save_config(config)
    
    return jsonify({'success': True, 'portali': data})

@app.route('/api/link_pdf/<flotta_id>/<scadenza_id>/<documento_id>', methods=['POST'])
def api_link_pdf(flotta_id, scadenza_id, documento_id):
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    documento = next((d for d in scadenza['documenti'] if d['id'] == documento_id), None)
    if not documento:
        return jsonify({'success': False, 'error': 'Documento non trovato'}), 404

    # Verifica che il PDF esista
    full_path = os.path.join('uploaded_pdfs', pdf_path)
    if not os.path.exists(full_path):
        return jsonify({'success': False, 'error': 'PDF non trovato'}), 404

    # Collega il PDF al documento
    documento['pdf_path'] = pdf_path
    save_config(config)

    return jsonify({
        'success': True,
        'path': pdf_path,
        'filename': os.path.basename(pdf_path),
        'message': f'PDF "{os.path.basename(pdf_path)}" collegato con successo'
    })

# ========== API AMMINISTRAZIONE - OPERAZIONI ==========

@app.route('/api/admin/operazioni/<flotta_id>/<scadenza_id>', methods=['POST'])
def api_add_operazione(flotta_id, scadenza_id):
    """Aggiungi nuova operazione"""
    data = request.json
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    new_operazione = {
        'id': str(uuid.uuid4())[:8],
        'titolo': data['titolo'],
        'descrizione': data.get('descrizione', ''),
        'cdl': data.get('cdl', ''),
        'mesi_validi': data.get('mesi_validi', [])
    }

    scadenza['operazioni_aggiuntive'].append(new_operazione)
    save_config(config)

    return jsonify({'success': True, 'operazione': new_operazione})

@app.route('/api/admin/operazioni/<flotta_id>/<scadenza_id>/<operazione_id>', methods=['PUT'])
def api_update_operazione(flotta_id, scadenza_id, operazione_id):
    """Modifica operazione"""
    data = request.json
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    operazione = next((o for o in scadenza['operazioni_aggiuntive'] if o['id'] == operazione_id), None)
    if not operazione:
        return jsonify({'success': False, 'error': 'Operazione non trovata'}), 404

    operazione['titolo'] = data['titolo']
    operazione['descrizione'] = data.get('descrizione', '')
    operazione['cdl'] = data.get('cdl', '')
    operazione['mesi_validi'] = data.get('mesi_validi', [])
    save_config(config)

    return jsonify({'success': True, 'operazione': operazione})

@app.route('/api/admin/operazioni/<flotta_id>/<scadenza_id>/<operazione_id>', methods=['DELETE'])
def api_delete_operazione(flotta_id, scadenza_id, operazione_id):
    """Elimina operazione"""
    config = load_config()

    flotta = next((f for f in config['flotte'] if f['id'] == flotta_id), None)
    if not flotta:
        return jsonify({'success': False, 'error': 'Flotta non trovata'}), 404

    scadenza = next((s for s in flotta['scadenze'] if s['id'] == scadenza_id), None)
    if not scadenza:
        return jsonify({'success': False, 'error': 'Scadenza non trovata'}), 404

    scadenza['operazioni_aggiuntive'] = [o for o in scadenza['operazioni_aggiuntive'] if o['id'] != operazione_id]
    save_config(config)

    return jsonify({'success': True})

# ========== API AMMINISTRAZIONE - OPERAZIONI GLOBALI ==========

@app.route('/api/admin/operazioni-globali', methods=['POST'])
def api_add_operazione_globale():
    """Aggiungi nuova operazione globale"""
    data = request.json
    config = load_config()

    if 'operazioni_globali' not in config:
        config['operazioni_globali'] = []

    new_operazione = {
        'id': str(uuid.uuid4())[:8],
        'titolo': data['titolo'],
        'descrizione': data.get('descrizione', ''),
        'cdl': data.get('cdl', ''),
        'flotta_id': data.get('flotta_id', ''),
        'mesi_validi': data.get('mesi_validi', [])
    }

    config['operazioni_globali'].append(new_operazione)
    save_config(config)

    return jsonify({'success': True, 'operazione': new_operazione})

@app.route('/api/admin/operazioni-globali/<operazione_id>', methods=['PUT'])
def api_update_operazione_globale(operazione_id):
    """Aggiorna operazione globale"""
    data = request.json
    config = load_config()

    if 'operazioni_globali' not in config:
        config['operazioni_globali'] = []

    operazione = next((o for o in config['operazioni_globali'] if o['id'] == operazione_id), None)
    if not operazione:
        return jsonify({'success': False, 'error': 'Operazione non trovata'}), 404

    operazione['titolo'] = data['titolo']
    operazione['descrizione'] = data.get('descrizione', '')
    operazione['cdl'] = data.get('cdl', '')
    operazione['flotta_id'] = data.get('flotta_id', '')
    operazione['mesi_validi'] = data.get('mesi_validi', [])
    save_config(config)

    return jsonify({'success': True, 'operazione': operazione})

@app.route('/api/admin/operazioni-globali/<operazione_id>', methods=['DELETE'])
def api_delete_operazione_globale(operazione_id):
    """Elimina operazione globale"""
    config = load_config()

    if 'operazioni_globali' not in config:
        config['operazioni_globali'] = []

    config['operazioni_globali'] = [o for o in config['operazioni_globali'] if o['id'] != operazione_id]
    save_config(config)

    return jsonify({'success': True})

@app.route('/debug/files')
def debug_files():
    """Route di debug per verificare file system"""
    import glob

    debug_info = {
        'cwd': os.getcwd(),
        'base_dir': BASE_DIR,
        'directories': {},
        'globale_pdfs': [],
        'environment': {
            'PORT': os.environ.get('PORT'),
            'FLASK_ENV': os.environ.get('FLASK_ENV')
        }
    }

    # Controlla directory
    dirs_to_check = ['uploaded_pdfs', 'uploaded_pdfs/GLOBALE', 'templates', 'static', 'thumbnails', 'data']
    for d in dirs_to_check:
        full_path = get_path(d)
        debug_info['directories'][d] = {
            'exists': os.path.exists(full_path),
            'path': full_path,
            'items': len(os.listdir(full_path)) if os.path.exists(full_path) else 0
        }

    # Lista PDF in GLOBALE
    globale_dir = get_path('uploaded_pdfs', 'GLOBALE')
    if os.path.exists(globale_dir):
        pdf_files = [f for f in os.listdir(globale_dir) if f.endswith('.pdf')]
        debug_info['globale_pdfs'] = pdf_files[:20]  # Prime 20
        debug_info['total_globale_pdfs'] = len(pdf_files)

    return jsonify(debug_info)

if __name__ == '__main__':
    # Crea cartelle necessarie
    os.makedirs('temp_pdfs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
