from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from datetime import datetime
import os
import logging
from pdf_utils import process_and_merge_pdfs
from pypdf import PdfReader, PdfWriter
from template_utils import compila_template_pdf, compila_template_pdf_semplice, prepara_dati_frontespizio, prepara_dati_operazioni
from historical_data import save_pdf_generation
from pdf_optimization import cleanup_old_temp_files, cleanup_merge_directories, compress_pdf, ensure_temp_dir, flatten_pdf_fields

logger = logging.getLogger('pdf_generator')
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Directory base del progetto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_path(*parts):
    """Ottiene il percorso assoluto relativo alla directory base del progetto"""
    return os.path.join(BASE_DIR, *parts)

def generate_pdf(flotta, scadenze_ids, config, sede_tecnica='', numero_ordine='', strumento='', scadenze_copie=None):
    """
    Genera un PDF frontespizio in base alla flotta e scadenze selezionate

    Args:
        flotta: ID della flotta selezionata
        scadenze_ids: Lista di ID delle scadenze selezionate
        config: Dizionario con la configurazione delle flotte
        sede_tecnica: Sede tecnica per il frontespizio
        numero_ordine: Numero ordine per il frontespizio
        strumento: Strumento di rilevazione quote (CALIPRI, WPMS, MANUALE)
        scadenze_copie: Dizionario con il numero di copie per ogni scadenza

    Returns:
        Percorso del file PDF generato
    """
    
    logger.info(f"Generazione PDF per flotta {flotta} - {len(scadenze_ids)} scadenza/e")
    
    # Pulizia automatica file temporanei vecchi (ogni 24 ore)
    ensure_temp_dir()
    cleanup_old_temp_files(max_age_hours=24)
    cleanup_merge_directories(max_age_hours=24)
    
    # Default per scadenze_copie
    if scadenze_copie is None:
        scadenze_copie = {}

    # Trova i dati della flotta
    flotta_data = None
    scadenze_data = []

    for f in config['flotte']:
        if f['id'] == flotta:
            flotta_data = f
            # Trova tutte le scadenze selezionate
            for s in f['scadenze']:
                if s['id'] in scadenze_ids:
                    scadenze_data.append(s)
            break

    if not flotta_data or not scadenze_data:
        raise ValueError("Flotta o scadenze non trovate")

    # Controlla se la flotta è multioggetto
    is_multioggetto = flotta_data.get('multioggetto', False)

    # Ottieni operazioni globali filtrate per flotta
    operazioni_globali = config.get('operazioni_globali', [])
    # Filtra per flotta: mostra operazioni globali (senza flotta_id) o quelle specifiche per questa flotta
    operazioni_globali = [op for op in operazioni_globali if not op.get('flotta_id') or op.get('flotta_id') == flotta]

    # Crea il nome del file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"frontespizio_{flotta}_{timestamp}.pdf"
    filepath = get_path('temp_pdfs', filename)

    # 1. Genera frontespizio e operazioni usando TEMPLATE UNIFICATO
    template_unified = get_path('templates', 'unified_template.pdf')
    
    try:
        if os.path.exists(template_unified):
            logger.debug(f"Uso template unificato")
            # Prepara dati per il template
            dati_utente = {
                'sede_tecnica': sede_tecnica,
                'numero_ordine': numero_ordine,
                'strumento': strumento
            }
            dati_frontespizio = prepara_dati_frontespizio(flotta, scadenze_ids, config, dati_utente, scadenze_copie)
            dati_operazioni = prepara_dati_operazioni(flotta, scadenze_ids, config, dati_utente)
            
            # Controlla se ci sono operazioni reali con contenuto
            def has_real_operations_check():
                """Controlla se ci sono operazioni reali con contenuto"""
                # Ottieni operazioni globali filtrate per flotta
                operazioni_globali_check = config.get('operazioni_globali', [])
                operazioni_globali_check = [op for op in operazioni_globali_check if not op.get('flotta_id') or op.get('flotta_id') == flotta]
                
                # Ottieni operazioni delle scadenze
                operazioni_scadenze = []
                for scadenza_id in scadenze_ids:
                    scadenza_info = None
                    for f in config['flotte']:
                        if f['id'] == flotta:
                            for s in f['scadenze']:
                                if s['id'] == scadenza_id:
                                    scadenza_info = s
                                    break
                            if scadenza_info:
                                break
                    if scadenza_info:
                        operazioni_scadenze.extend(scadenza_info.get('operazioni_aggiuntive', []))
                
                # Combina tutte le operazioni in formato uniforme (nome_scadenza, op)
                tutte_operazioni_check = [("GLOBALE", op) for op in operazioni_globali_check] + [("SCADENZA", op) for op in operazioni_scadenze]
                
                # Controlla se almeno una ha contenuto reale
                for nome_scadenza, op in tutte_operazioni_check:
                    if (op.get('titolo', '').strip() or 
                        op.get('descrizione', '').strip() or 
                        op.get('cdl', '').strip()):
                        return True
                return False
            
            has_operations = has_real_operations_check()
            logger.debug(f"Operazioni reali presenti: {has_operations}")
            
            # Unisci i dati da entrambi i template
            dati_compilazione = {**dati_frontespizio, **dati_operazioni}
            
            # Estrai la modalità testo dalla configurazione
            text_positions = config.get('text_positions', {})
            text_mode = text_positions.get('text_mode', 'automatic')
            font_size = text_positions.get('font_size', 'auto')
            
            # Compila il template temporaneo
            temp_filepath = filepath + '.temp'
            compila_template_pdf_semplice(template_unified, dati_compilazione, temp_filepath, text_mode, font_size, update_da=True)
            
            # Se non ci sono operazioni reali, estrai solo la prima pagina (frontespizio)
            if not has_operations:
                logger.debug("Nessuna operazione reale, uso solo frontespizio (pagina 1)")
                reader = PdfReader(temp_filepath)
                writer_single = PdfWriter()
                if len(reader.pages) > 0:
                    writer_single.add_page(reader.pages[0])  # Solo la prima pagina
                with open(filepath, 'wb') as f:
                    writer_single.write(f)
                # Rimuovi il file temporaneo
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
            else:
                logger.debug("Operazioni presenti, uso template completo (2 pagine)")
                # Rinomina il file temporaneo come finale
                if os.path.exists(temp_filepath):
                    os.rename(temp_filepath, filepath)
        else:
            logger.warning(f"Template frontespizio non trovato, uso generazione ReportLab")
            # Codice originale per generazione frontespizio
            c = canvas.Canvas(filepath, pagesize=A4)
            width, height = A4

            # Titolo
            c.setFont("Helvetica-Bold", 24)
            c.drawCentredString(width/2, height - 3*cm, "FRONTESPIZIO")

            # Linea separatrice
            c.line(3*cm, height - 4*cm, width - 3*cm, height - 4*cm)

            y_pos = height - 6*cm

            # Informazioni flotta
            c.setFont("Helvetica-Bold", 14)
            c.drawString(3*cm, y_pos, "FLOTTA:")
            c.setFont("Helvetica", 14)
            c.drawString(9*cm, y_pos, flotta_data['nome'])
            y_pos -= 1*cm

            # Informazioni scadenze (mostra tutte quelle selezionate)
            c.setFont("Helvetica-Bold", 14)
            if len(scadenze_data) == 1:
                c.drawString(3*cm, y_pos, "SCADENZA:")
                c.setFont("Helvetica", 14)
                c.drawString(9*cm, y_pos, scadenze_data[0]['nome'])
                y_pos -= 1*cm
            else:
                c.drawString(3*cm, y_pos, "SCADENZE:")
                y_pos -= 0.7*cm
                c.setFont("Helvetica", 12)
                for scad in scadenze_data:
                    c.drawString(4*cm, y_pos, f"• {scad['nome']}")
                    y_pos -= 0.6*cm
                y_pos -= 0.4*cm

            # Sede Tecnica
            c.setFont("Helvetica-Bold", 14)
            c.drawString(3*cm, y_pos, "SEDE TECNICA:")
            c.setFont("Helvetica", 14)
            c.drawString(9*cm, y_pos, sede_tecnica)
            y_pos -= 1*cm

            # Numero Ordine
            c.setFont("Helvetica-Bold", 14)
            c.drawString(3*cm, y_pos, "N. ORDINE:")
            c.setFont("Helvetica", 14)
            c.drawString(9*cm, y_pos, numero_ordine)
            y_pos -= 1.5*cm

            # Operazioni Globali (se presenti)
            if operazioni_globali:
                c.setFont("Helvetica-Bold", 12)
                c.drawString(3*cm, y_pos, "OPERAZIONI GLOBALI")
                y_pos -= 0.8*cm

                c.setFont("Helvetica", 9)
                for i, op in enumerate(operazioni_globali, 1):
                    c.setFont("Helvetica-Bold", 9)
                    c.drawString(3.5*cm, y_pos, f"{i}. {op['titolo']}")
                    y_pos -= 0.4*cm

                    if op.get('descrizione'):
                        c.setFont("Helvetica", 8)
                        # Word wrap per descrizione operazione
                        max_width_op = width - 7*cm
                        words_op = op['descrizione'].split()
                        line_op = ""

                        for word in words_op:
                            test_line_op = line_op + word + " "
                            if c.stringWidth(test_line_op, "Helvetica", 8) < max_width_op:
                                line_op = test_line_op
                            else:
                                c.drawString(4*cm, y_pos, line_op)
                                y_pos -= 0.35*cm
                                line_op = word + " "

                        if line_op:
                            c.drawString(4*cm, y_pos, line_op)
                        y_pos -= 0.4*cm

                    if op.get('cdl'):
                        c.setFont("Helvetica-Oblique", 8)
                        c.drawString(4*cm, y_pos, f"CDL: {op['cdl']}")
                        y_pos -= 0.4*cm

                y_pos -= 0.6*cm

            # Processa ogni scadenza selezionata
            for idx, scadenza_data_loop in enumerate(scadenze_data):
                # Se ci sono più scadenze, aggiungi separatore
                if len(scadenze_data) > 1:
                    c.setFont("Helvetica-Bold", 13)
                    c.drawString(3*cm, y_pos, f"━━ {scadenza_data_loop['nome']} ━━")
                    y_pos -= 0.8*cm

                # Descrizione (se presente)
                if 'descrizione' in scadenza_data_loop and scadenza_data_loop['descrizione']:
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(3*cm, y_pos, "Descrizione:")
                    y_pos -= 0.5*cm

                    c.setFont("Helvetica", 10)
                    # Word wrap per la descrizione
                    descrizione = scadenza_data_loop['descrizione']
                    max_width = width - 6*cm
                    words = descrizione.split()
                    line = ""

                    for word in words:
                        test_line = line + word + " "
                        if c.stringWidth(test_line, "Helvetica", 10) < max_width:
                            line = test_line
                        else:
                            c.drawString(3.5*cm, y_pos, line)
                            y_pos -= 0.4*cm
                            line = word + " "

                    if line:
                        c.drawString(3.5*cm, y_pos, line)
                    y_pos -= 0.6*cm

                # Operazioni Aggiuntive (solo per flotte standard)
                if not is_multioggetto:
                    operazioni = scadenza_data_loop.get('operazioni_aggiuntive', [])
                    if operazioni:
                        c.setFont("Helvetica-Bold", 11)
                        c.drawString(3*cm, y_pos, "Operazioni aggiuntive:")
                        y_pos -= 0.6*cm

                        c.setFont("Helvetica", 9)
                        for i, op in enumerate(operazioni, 1):
                            c.setFont("Helvetica-Bold", 9)
                            c.drawString(3.5*cm, y_pos, f"{i}. {op['titolo']}")
                            y_pos -= 0.4*cm

                            if op.get('descrizione'):
                                c.setFont("Helvetica", 8)
                                # Word wrap per descrizione operazione
                                max_width_op = width - 7*cm
                                words_op = op['descrizione'].split()
                                line_op = ""

                                for word in words_op:
                                    test_line_op = line_op + word + " "
                                    if c.stringWidth(test_line_op, "Helvetica", 8) < max_width_op:
                                        line_op = test_line_op
                                    else:
                                        c.drawString(4*cm, y_pos, line_op)
                                        y_pos -= 0.35*cm
                                        line_op = word + " "

                                if line_op:
                                    c.drawString(4*cm, y_pos, line_op)
                                y_pos -= 0.4*cm

                        y_pos -= 0.4*cm

                # Spazio tra scadenze
                if idx < len(scadenze_data) - 1:
                    y_pos -= 0.5*cm

            # Documenti (fuori dal ciclo per flotte multioggetto)
            if is_multioggetto:
                # Per flotte multioggetto, raggruppa tutti i documenti per nome considerando le copie per scadenza
                documenti_raggruppati = {}
                
                # Applica filtro strumento e considera le copie per scadenza
                for scadenza_idx, scad_data in enumerate(scadenze_data):
                    scadenza_id = scad_data['id']
                    copie_scadenza = scadenze_copie.get(scadenza_id, 1)
                    
                    for doc in scad_data.get('documenti', []):
                        # Applica filtro strumento
                        # Documenti senza campo strumento sono sempre inclusi
                        # Documenti con strumento sono inclusi solo se corrispondono
                        doc_strumento = doc.get('strumento', None)
                        if doc_strumento is not None and strumento and doc_strumento != strumento:
                            continue  # Salta documenti che non corrispondono allo strumento
                        
                        nome_doc = doc.get('nome', 'Senza nome')
                        if nome_doc not in documenti_raggruppati:
                            documenti_raggruppati[nome_doc] = {
                                'doc': doc,
                                'copie': copie_scadenza
                            }
                        else:
                            documenti_raggruppati[nome_doc]['copie'] += copie_scadenza
                
                if documenti_raggruppati:
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(3*cm, y_pos, "Documenti richiesti:")
                    y_pos -= 0.6*cm

                    c.setFont("Helvetica", 9)
                    for i, (nome_doc, info) in enumerate(documenti_raggruppati.items(), 1):
                        doc = info['doc']
                        copie = info['copie']
                        obblig = " (Obbligatorio)" if doc.get('obbligatorio', False) else ""
                        copie_text = f" ({copie} copie)" if copie > 1 else ""
                        c.drawString(3.5*cm, y_pos, f"{i}. {nome_doc}{copie_text}{obblig}")
                        y_pos -= 0.4*cm

                    y_pos -= 0.4*cm
            else:
                # Per flotte standard, i documenti sono già stati mostrati per ogni scadenza
                pass

            # Operazioni aggiuntive per flotte multioggetto (dopo i documenti)
            if is_multioggetto:
                # Mostra operazioni globali filtrate per mese e flotta
                operazioni_globali = config.get('operazioni_globali', [])
                operazioni_globali = [op for op in operazioni_globali if not op.get('flotta_id') or op.get('flotta_id') == flotta]
                operazioni_globali_filtrate = [op for op in operazioni_globali if not op.get('mesi_validi') or current_month in op.get('mesi_validi', [])]
                
                if operazioni_globali_filtrate:
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(3*cm, y_pos, "Operazioni globali:")
                    y_pos -= 0.6*cm

                    c.setFont("Helvetica", 9)
                    for i, op in enumerate(operazioni_globali_filtrate, 1):
                        c.setFont("Helvetica-Bold", 9)
                        c.drawString(3.5*cm, y_pos, f"{i}. {op['titolo']}")
                        y_pos -= 0.4*cm

                        if op.get('descrizione'):
                            c.setFont("Helvetica", 8)
                            # Word wrap per descrizione operazione
                            max_width_op = width - 7*cm
                            words_op = op['descrizione'].split()
                            line_op = ""

                            for word in words_op:
                                test_line_op = line_op + word + " "
                                if c.stringWidth(test_line_op, "Helvetica", 8) < max_width_op:
                                    line_op = test_line_op
                                else:
                                    c.drawString(4*cm, y_pos, line_op)
                                    y_pos -= 0.35*cm
                                    line_op = word + " "

                            if line_op:
                                c.drawString(4*cm, y_pos, line_op)
                            y_pos -= 0.4*cm

                        if op.get('cdl'):
                            c.setFont("Helvetica-Oblique", 8)
                            c.drawString(4*cm, y_pos, f"CDL: {op['cdl']}")
                            y_pos -= 0.4*cm

                    y_pos -= 0.4*cm

                # Mostra operazioni delle scadenze per flotte multioggetto
                for scad_data in scadenze_data:
                    operazioni = scad_data.get('operazioni_aggiuntive', [])
                    operazioni_filtrate = [op for op in operazioni if not op.get('mesi_validi') or current_month in op.get('mesi_validi', [])]
                    
                    if operazioni_filtrate:
                        c.setFont("Helvetica-Bold", 11)
                        c.drawString(3*cm, y_pos, f"Operazioni {scad_data['nome']}:")
                        y_pos -= 0.6*cm

                        c.setFont("Helvetica", 9)
                        for i, op in enumerate(operazioni_filtrate, 1):
                            c.setFont("Helvetica-Bold", 9)
                            c.drawString(3.5*cm, y_pos, f"{i}. {op['titolo']}")
                            y_pos -= 0.4*cm

                            if op.get('descrizione'):
                                c.setFont("Helvetica", 8)
                                # Word wrap per descrizione operazione
                                max_width_op = width - 7*cm
                                words_op = op['descrizione'].split()
                                line_op = ""

                                for word in words_op:
                                    test_line_op = line_op + word + " "
                                    if c.stringWidth(test_line_op, "Helvetica", 8) < max_width_op:
                                        line_op = test_line_op
                                    else:
                                        c.drawString(4*cm, y_pos, line_op)
                                        y_pos -= 0.35*cm
                                        line_op = word + " "

                                if line_op:
                                    c.drawString(4*cm, y_pos, line_op)
                                y_pos -= 0.4*cm

                            if op.get('cdl'):
                                c.setFont("Helvetica-Oblique", 8)
                                c.drawString(4*cm, y_pos, f"CDL: {op['cdl']}")
                                y_pos -= 0.4*cm

                        y_pos -= 0.4*cm

            # Data di generazione
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(3*cm, 3*cm, f"Generato il: {datetime.now().strftime('%d/%m/%Y alle ore %H:%M')}")

            # Linea footer
            c.line(3*cm, 2.5*cm, width - 3*cm, 2.5*cm)

            # Salva il PDF frontespizio
            c.save()
    except Exception as e:
        print(f"ERRORE nella generazione del frontespizio: {e}")
        import traceback
        traceback.print_exc()
        # Fallback: genera un PDF vuoto
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            c = canvas.Canvas(filepath, pagesize=A4)
            c.drawString(100, 800, "ERRORE NELLA GENERAZIONE DEL FRONTESPIZIO")
            c.drawString(100, 780, f"Errore: {str(e)}")
            c.save()
        except:
            # Se anche il fallback fallisce, copia il template se esiste
            if os.path.exists(template_frontespizio):
                import shutil
                shutil.copy2(template_frontespizio, filepath)

    # Processa e unisci i PDF caricati
    merged_pdf = process_and_merge_pdfs(flotta, scadenze_ids, config, sede_tecnica, numero_ordine, strumento, scadenze_copie)

    # 2. Unisci i PDF: frontespizio+operazioni (unificati) + documenti
    final_path = get_path('temp_pdfs', f'completo_{flotta}_{timestamp}.pdf')
    writer = PdfWriter()

    # Aggiungi il frontespizio e operazioni (già nel template unificato)
    frontespizio_reader = PdfReader(filepath)
    for page in frontespizio_reader.pages:
        writer.add_page(page)

    # Aggiungi i documenti compilati (ALLA FINE)
    if merged_pdf and os.path.exists(merged_pdf):
        docs_reader = PdfReader(merged_pdf)
        for page in docs_reader.pages:
            writer.add_page(page)

    # Salva il PDF finale
    with open(final_path, 'wb') as output_file:
        writer.write(output_file)
    

    
    # Comprimi il PDF finale per ridurre la dimensione
    # try:
    #     compress_pdf(final_path)
    #     logger.debug(f"PDF compresso con successo")
    # except Exception as e:
    #     logger.warning(f"Errore compressione PDF: {e}")

    # Salva nello storico delle generazioni
    try:
        # Ottieni dimensione file
        file_size = os.path.getsize(final_path)
        file_size_kb = round(file_size / 1024, 2)
        
        # Ottieni nomi scadenze
        scadenze_nomi = []
        for flotta_data in config.get('flotte', []):
            for scadenza in flotta_data.get('scadenze', []):
                if scadenza['id'] in scadenze_ids:
                    scadenze_nomi.append(scadenza.get('nome', ''))
        
        # Conta documenti e operazioni per lo storico
        total_documenti = 0
        total_operazioni = 0
        
        # Conta documenti dalle scadenze selezionate
        flotta_data = next((f for f in config.get('flotte', []) if f['id'] == flotta), {})
        for scadenza in flotta_data.get('scadenze', []):
            if scadenza['id'] in scadenze_ids:
                # Conta documenti
                documenti = scadenza.get('documenti', [])
                if strumento:
                    # Filtra per strumento se specificato
                    documenti_filtrati = [d for d in documenti if not d.get('strumento') or d.get('strumento') == strumento]
                    total_documenti += len(documenti_filtrati)
                else:
                    total_documenti += len(documenti)
                
                # Conta operazioni aggiuntive
                total_operazioni += len(scadenza.get('operazioni_aggiuntive', []))
        
        # Aggiungi operazioni globali se esistono
        operazioni_globali = config.get('operazioni_globali', [])
        total_operazioni += len(operazioni_globali)
        
        # Prepara dati per storico
        storico_data = {
            'flotta_id': flotta,
            'flotta_nome': next((f['nome'] for f in config.get('flotte', []) if f['id'] == flotta), 'Sconosciuta'),
            'scadenze_ids': scadenze_ids,
            'scadenze_nomi': scadenze_nomi,
            'strumento': strumento,
            'sede_tecnica': sede_tecnica,
            'numero_ordine': numero_ordine,
            'numero_documenti': total_documenti,
            'numero_operazioni': total_operazioni,
            'filename': os.path.basename(final_path),
            'file_size_kb': file_size_kb,
            'scadenze_copie': scadenze_copie or {}
        }
        
        save_pdf_generation(storico_data)
        
    except Exception as e:
        logger.error(f"Errore salvataggio storico: {e}")

    logger.info(f"PDF generato: {os.path.basename(final_path)}")
    return final_path
