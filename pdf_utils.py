from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, create_string_object
import os
from datetime import datetime
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from pdfrw import PdfReader as PdfReaderRw, PdfWriter as PdfWriterRw, PageMerge

# Directory base del progetto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_path(*parts):
    """Ottiene il percorso assoluto relativo alla directory base del progetto"""
    return os.path.join(BASE_DIR, *parts)

def add_text_to_pdf(input_pdf_path, output_pdf_path, text_data):
    """
    Aggiunge testo direttamente su qualsiasi PDF con coordinate centrali
    
    Args:
        input_pdf_path: Path del PDF originale
        output_pdf_path: Path dove salvare il PDF con testo
        text_data: Dizionario con i dati da aggiungere
    """
    # Creazione del layer di testo
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    
    # Configurazione font
    can.setFont("Helvetica-Bold", 12)
    can.setFillColorRGB(0, 0, 0)  # Nero
    
    # Posizione centrale della pagina A4
    center_x = 306  # Centro orizzontale (612/2)
    center_y = 396  # Centro verticale (792/2)
    
    # Aggiungi testo centrato
    if text_data.get('sede_tecnica'):
        text = f"Sede: {text_data['sede_tecnica']}"
        text_width = can.stringWidth(text, "Helvetica-Bold", 12)
        can.drawString(center_x - text_width/2, center_y + 20, text)
    
    if text_data.get('numero_ordine'):
        text = f"Ordine: {text_data['numero_ordine']}"
        text_width = can.stringWidth(text, "Helvetica-Bold", 12)
        can.drawString(center_x - text_width/2, center_y - 20, text)
    
    can.save()
    
    # Sovrapponi il layer di testo al PDF originale
    packet.seek(0)
    text_layer = PdfReaderRw(packet)
    original_pdf = PdfReaderRw(input_pdf_path)
    
    output = PdfWriterRw()
    
    # Aggiungi il layer di testo alla prima pagina
    if original_pdf.pages:
        PageMerge(text_layer.pages[0]).add(original_pdf.pages[0]).render()
        # Aggiungi le pagine rimanenti senza testo
        for page in original_pdf.pages[1:]:
            output.addpage(page)
    
    # Salva il risultato
    output.write(output_pdf_path)
    return output_pdf_path


def fill_pdf_fields_pdfrw(input_pdf_path, output_pdf_path, field_data):
    """
    Compila i campi di un PDF usando pdfrw (più affidabile)
    
    Args:
        input_pdf_path: Path del PDF template
        output_pdf_path: Path dove salvare il PDF compilato
        field_data: Dizionario con i dati da inserire nei campi
    """
    from pdfrw import PdfReader, PdfWriter
    
    template_pdf = PdfReader(input_pdf_path)
    
    print(f"PDF pdfrw: {input_pdf_path}")
    print(f"Campi pdfrw trovati: {list(template_pdf.Root.AcroForm.Fields.keys()) if hasattr(template_pdf.Root, 'Acro') and hasattr(template_pdf.Root.Acro, 'Fields') else 'Nessuno'}")
    
    if not hasattr(template_pdf.Root, 'Acro') or not hasattr(template_pdf.Root.Acro, 'Fields'):
        print("PDF senza campi modulo pdfrw - copia semplice")
        # Copia semplice
        writer = PdfWriter()
        writer.addpages(template_pdf.pages)
        writer.write(output_pdf_path)
        return output_pdf_path
    
    # Compila i campi
    data_to_fill = {}
    for field_name in ['sede_tecnica', 'numero_ordine']:
        if field_name in field_data:
            data_to_fill[field_name] = field_data[field_name]
            print(f"Campo pdfrw {field_name} compilato con: {field_data[field_name]}")
    
    if data_to_fill:
        # Compila i campi nel modulo
        for page in template_pdf.pages:
            if hasattr(page, 'Annots'):
                for annot in page.Annots:
                    if hasattr(annot, 'T') and hasattr(annot, 'V'):
                        field_name = annot.T
                        if field_name in data_to_fill:
                            annot.V = data_to_fill[field_name]
                            print(f"Campo {field_name} impostato a: {data_to_fill[field_name]}")
        
        print("Campi pdfrw compilati con successo")
    
    # Salva il PDF
    writer = PdfWriter()
    writer.addpages(template_pdf.pages)
    writer.write(output_pdf_path)
    
    return output_pdf_path


def compile_and_flatten_pdf(input_pdf_path, output_pdf_path, field_data, font_size=None, text_mode='fields'):
    """
    Compila i campi e poi disegna il testo sopra usando SOLO pypdf e reportlab

    Args:
        input_pdf_path: Path del PDF template
        output_pdf_path: Path dove salvare il PDF appiattito
        field_data: Dizionario con i dati da inserire nei campi
        font_size: Dimensione font (se None, calcola dall'altezza del campo)
        text_mode: Modalità testo ('fields', 'coordinates', 'automatic')

    Returns:
        True se ha successo, False altrimenti
    """
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import NameObject, create_string_object
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import io
        import tempfile
        import os
        import json

        # Se font_size non è specificato, prova a leggerlo dalla configurazione
        if font_size is None:
            try:
                config_path = get_path('data', 'flotte.json')
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    font_size = config.get('text_positions', {}).get('font_size', 10)
                    if font_size == 'auto':
                        font_size = None  # Usa calcolo automatico
                    else:
                        font_size = int(font_size)
            except:
                font_size = 10  # Default

        print(f"DEBUG: Compilazione con pypdf")
        print(f"DEBUG: Input: {input_pdf_path}")
        print(f"DEBUG: Field data: {field_data}")
        print(f"DEBUG: Font size: {font_size if font_size else 'AUTO'}")

        # FASE 1: Leggi il PDF e trova le posizioni dei campi DIRETTAMENTE dalle annotazioni
        # (pypdf.get_fields() non funziona se i campi non sono nell'AcroForm/Fields)
        reader = PdfReader(input_pdf_path)

        # Raccogli informazioni sui campi (posizione e valore) dalle annotazioni
        field_positions = {}
        has_widgets = False

        for page_num, page in enumerate(reader.pages):
            if '/Annots' in page:
                for annot_ref in page['/Annots']:
                    try:
                        annot = annot_ref.get_object()
                        if annot.get('/Subtype') == '/Widget' and '/T' in annot:
                            has_widgets = True
                            field_name = annot['/T']

                            if field_name in field_data:
                                # Ottieni coordinate del campo
                                rect = annot.get('/Rect')
                                if rect:
                                    field_positions[field_name] = {
                                        'value': str(field_data[field_name]),
                                        'rect': rect,
                                        'page': page_num,
                                        'annot': annot
                                    }
                                    print(f"DEBUG: Campo '{field_name}' trovato a pagina {page_num}")
                    except Exception as e:
                        print(f"WARN Errore lettura annotazione: {e}")
                        continue

        if not has_widgets:
            print("WARN Nessun campo widget trovato nel PDF")
            if text_mode == 'fields':
                # Modalità "solo campi": NON scrivere nulla se non ci sono campi
                print("Modalità 'fields': nessun campo trovato, copio PDF senza modifiche")
                import shutil
                shutil.copy2(input_pdf_path, output_pdf_path)
                return True
            elif text_mode == 'coordinates':
                # Modalità "solo coordinate": usa sempre coordinate
                print("Modalità 'coordinates': uso coordinate predefinite")
                add_text_to_pdf_direct(input_pdf_path, output_pdf_path, field_data)
                return True
            else:  # automatic
                # Modalità "automatica": fallback su coordinate se non ci sono campi
                print("Modalità 'automatic': nessun campo trovato, uso coordinate predefinite")
                add_text_to_pdf_direct(input_pdf_path, output_pdf_path, field_data)
                return True

        print(f"DEBUG: Trovati {len(field_positions)} campi da compilare")

        # FASE 2: Crea overlay con il testo usando reportlab
        for page_num, page in enumerate(reader.pages):
            # Ottieni dimensioni pagina
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            # Crea un layer con il testo
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(page_width, page_height))
            can.setFillColorRGB(0, 0, 0)

            # Disegna il testo per ogni campo in questa pagina
            if '/Annots' in page:
                for annot_ref in page['/Annots']:
                    try:
                        annot = annot_ref.get_object()
                        if annot.get('/Subtype') == '/Widget' and '/T' in annot:
                            field_name = annot['/T']

                            if field_name in field_positions:
                                value = field_positions[field_name]['value']

                                # Ottieni coordinate del campo
                                rect = annot['/Rect']
                                x0, y0, x1, y1 = [float(r) for r in rect]
                                field_width = x1 - x0
                                field_height = y1 - y0

                                # Calcola font size se auto
                                field_font_size = font_size
                                if field_font_size is None:
                                    # Calcola basandosi sull'altezza del campo
                                    field_font_size = max(8, min(field_height * 0.6, 20))

                                # Imposta font per questo campo
                                can.setFont("Helvetica", field_font_size)

                                # Leggi alignment dal campo (/Q: 0=left, 1=center, 2=right)
                                alignment = 0  # default left
                                if '/Q' in annot:
                                    alignment = int(annot['/Q'])

                                # Verifica se è multilinea (/Ff flag bit 12 o se contiene \n)
                                is_multiline = False
                                if '/Ff' in annot:
                                    flags = int(annot['/Ff'])
                                    is_multiline = (flags & (1 << 12)) != 0  # bit 12 = multiline

                                # Se il valore contiene \n, consideralo multilinea
                                if '\n' in value:
                                    is_multiline = True

                                # Funzione helper per wrapping del testo
                                def wrap_text(text, max_width, font_name, font_size):
                                    """Spezza il testo in righe che stanno nella larghezza massima"""
                                    words = text.split(' ')
                                    lines = []
                                    current_line = ''

                                    for word in words:
                                        test_line = current_line + (' ' if current_line else '') + word
                                        test_width = can.stringWidth(test_line, font_name, font_size)

                                        if test_width <= max_width:
                                            current_line = test_line
                                        else:
                                            if current_line:
                                                lines.append(current_line)
                                            current_line = word

                                    if current_line:
                                        lines.append(current_line)

                                    return lines if lines else ['']

                                # Disegna il testo con allineamento e multilinea
                                if is_multiline:
                                    # Campo multilinea - disegna righe multiple con wrapping
                                    raw_lines = value.split('\n')
                                    wrapped_lines = []

                                    # Applica wrapping a ogni riga
                                    for raw_line in raw_lines:
                                        wrapped = wrap_text(raw_line, field_width - 4, "Helvetica", field_font_size)
                                        wrapped_lines.extend(wrapped)

                                    line_height = field_font_size * 1.2
                                    y_start = y1 - field_font_size - 2  # Inizia dall'alto del campo

                                    for i, line in enumerate(wrapped_lines):
                                        y_pos = y_start - (i * line_height)
                                        if y_pos < y0:  # Non disegnare fuori dal campo
                                            break

                                        if alignment == 1:  # Center
                                            text_width = can.stringWidth(line, "Helvetica", field_font_size)
                                            x_pos = x0 + (field_width - text_width) / 2
                                            can.drawString(x_pos, y_pos, line)
                                        elif alignment == 2:  # Right
                                            text_width = can.stringWidth(line, "Helvetica", field_font_size)
                                            x_pos = x1 - text_width - 2
                                            can.drawString(x_pos, y_pos, line)
                                        else:  # Left
                                            can.drawString(x0 + 2, y_pos, line)
                                else:
                                    # Campo singola linea
                                    text_width = can.stringWidth(value, "Helvetica", field_font_size)

                                    # Se il testo è troppo lungo, tronca o riduci il font
                                    if text_width > field_width - 4:
                                        # Opzione 1: Tronca con "..."
                                        # truncated = value
                                        # while can.stringWidth(truncated + '...', "Helvetica", field_font_size) > field_width - 4 and len(truncated) > 0:
                                        #     truncated = truncated[:-1]
                                        # value = truncated + '...'

                                        # Opzione 2: Riduci il font size per farlo entrare
                                        reduced_font_size = field_font_size
                                        while text_width > field_width - 4 and reduced_font_size > 6:
                                            reduced_font_size -= 0.5
                                            can.setFont("Helvetica", reduced_font_size)
                                            text_width = can.stringWidth(value, "Helvetica", reduced_font_size)

                                        field_font_size = reduced_font_size

                                    # Centra verticalmente nel campo
                                    y_pos = y0 + (field_height - field_font_size) / 2

                                    if alignment == 1:  # Center
                                        text_width = can.stringWidth(value, "Helvetica", field_font_size)
                                        x_pos = x0 + (field_width - text_width) / 2
                                        can.drawString(x_pos, y_pos, value)
                                    elif alignment == 2:  # Right
                                        text_width = can.stringWidth(value, "Helvetica", field_font_size)
                                        x_pos = x1 - text_width - 2
                                        can.drawString(x_pos, y_pos, value)
                                    else:  # Left
                                        can.drawString(x0 + 2, y_pos, value)

                                align_text = ['left', 'center', 'right'][alignment]
                                multi_text = 'multiline' if is_multiline else 'singleline'
                                print(f"OK Testo '{value[:20]}...' disegnato ({align_text}, {multi_text}) con font {field_font_size}")
                    except Exception as e:
                        print(f"WARN Errore campo: {e}")
                        continue

            can.save()

            # Sovrapponi il layer di testo alla pagina
            packet.seek(0)
            overlay_pdf = PdfReader(packet)
            if overlay_pdf.pages:
                page.merge_page(overlay_pdf.pages[0])

        # FASE 3: Rimuovi i campi modulo
        from pypdf.generic import ArrayObject

        writer = PdfWriter()
        for page in reader.pages:
            # Rimuovi le annotazioni dei campi
            if '/Annots' in page:
                new_annots = ArrayObject()
                for annot_ref in page['/Annots']:
                    try:
                        annot = annot_ref.get_object()
                        # Mantieni solo annotazioni NON di tipo Widget
                        if annot.get('/Subtype') != '/Widget':
                            new_annots.append(annot_ref)
                    except:
                        new_annots.append(annot_ref)

                if len(new_annots) > 0:
                    page[NameObject('/Annots')] = new_annots
                else:
                    # Rimuovi completamente Annots se vuoto
                    del page['/Annots']

            writer.add_page(page)

        # Rimuovi AcroForm
        if '/AcroForm' in writer._root_object:
            del writer._root_object['/AcroForm']

        # Salva
        with open(output_pdf_path, 'wb') as output_file:
            writer.write(output_file)

        print(f"OK PDF salvato in: {output_pdf_path}")
        return True

    except Exception as e:
        print(f"ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return False


def fill_pdf_fields(input_pdf_path, output_pdf_path, field_data, text_mode='automatic', field_names=None):
    """
    Compila i campi di un PDF con i dati forniti - versione con gestione modalità testo

    Args:
        input_pdf_path: Path del PDF template
        output_pdf_path: Path dove salvare il PDF compilato
        field_data: Dizionario con i dati da inserire nei campi
        text_mode: Modalità di inserimento ('automatic', 'fields', 'coordinates')
        field_names: Dizionario con i nomi personalizzati dei campi PDF
    """
    if field_names is None:
        field_names = {}

    print(f"DEBUG: Inizio fill_pdf_fields con text_mode={text_mode}")
    print(f"DEBUG: field_data ricevuto: {field_data}")

    # PRIORITÀ: Usa SOLO pypdf e reportlab per compilare e appiattire
    if text_mode in ['fields', 'automatic']:
        try:
            # Verifica se il PDF ha campi usando pypdf
            reader = PdfReader(input_pdf_path)
            fields = reader.get_fields()
            has_fields = fields is not None and len(fields) > 0

            if has_fields or text_mode == 'fields':
                print("DEBUG: Uso pypdf + reportlab per compilare e appiattire i campi")

                # Prepara i dati con i nomi dei campi corretti
                pdf_data = {}

                # Aggiungi i dati base
                if 'sede_tecnica' in field_data:
                    pdf_data['sede_tecnica'] = field_data['sede_tecnica']
                    pdf_data[field_names.get('sede_fieldname', 'sede_tecnica')] = field_data['sede_tecnica']

                if 'numero_ordine' in field_data:
                    pdf_data['numero_ordine'] = field_data['numero_ordine']
                    pdf_data[field_names.get('ordine_fieldname', 'numero_ordine')] = field_data['numero_ordine']

                # Aggiungi tutti gli altri campi dal field_data
                for key, value in field_data.items():
                    if key not in pdf_data:
                        pdf_data[key] = value

                print(f"DEBUG: Dati preparati per pypdf: {pdf_data}")

                # Usa la funzione che compila e appiattisce con pypdf + reportlab
                success = compile_and_flatten_pdf(input_pdf_path, output_pdf_path, pdf_data, font_size=None, text_mode=text_mode)

                if success:
                    print("✓ PDF compilato e appiattito con successo usando pypdf + reportlab")
                    return output_pdf_path
                else:
                    print("⚠ pypdf ha fallito, provo con pypdf fallback...")
            elif text_mode == 'automatic':
                # Nessun campo trovato in modalità automatica, usa coordinate
                print("DEBUG: Nessun campo trovato, uso coordinate")
                return add_text_to_pdf_direct(input_pdf_path, output_pdf_path, field_data)

        except Exception as e:
            print(f"ERRORE nell'uso di pypdf: {e}")
            import traceback
            traceback.print_exc()
            print("Provo fallback con pypdf standard...")

    # Fallback: usa pypdf (metodo originale)
    try:
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()

        # Copia tutte le pagine
        for page in reader.pages:
            writer.add_page(page)

        # Verifica se il PDF ha campi modulo
        original_fields = reader.get_fields()
        print(f"DEBUG: Campi trovati con pypdf: {list(original_fields.keys()) if original_fields else 'Nessuno'}")

        # Usa sempre i campi originali dal reader
        fields = original_fields

        # Logica basata sulla modalità testo
        should_use_fields = False
        should_use_coordinates = False

        if text_mode == 'automatic':
            should_use_fields = fields is not None and len(fields) > 0
            should_use_coordinates = not should_use_fields
            print(f"Modalità automatica: campi={should_use_fields}, coordinate={should_use_coordinates}")
        elif text_mode == 'fields':
            should_use_fields = True
            should_use_coordinates = False
            print("Modalità campi PDF: uso solo campi compilabili")
        elif text_mode == 'coordinates':
            should_use_fields = False
            should_use_coordinates = True
            print("Modalità coordinate: uso solo coordinate assolute")
        else:
            print(f"ATTENZIONE: Modalità sconosciuta '{text_mode}', uso automatic")
            text_mode = 'automatic'
            should_use_fields = fields is not None and len(fields) > 0
            should_use_coordinates = not should_use_fields

        print(f"DEBUG: Decisione finale pypdf - should_use_fields={should_use_fields}, should_use_coordinates={should_use_coordinates}")

        # Se ci sono campi modulo e la modalità lo permette, prova a usarli
        if should_use_fields and fields:
            data_to_fill = {}
            
            # Mappa i campi usando i nomi personalizzati
            field_mapping = {
                'sede_tecnica': field_names.get('sede_fieldname', 'sede_tecnica'),
                'numero_ordine': field_names.get('ordine_fieldname', 'numero_ordine')
            }
            
            print(f"DEBUG: Tentativo di compilazione campi con mapping: {field_mapping}")
            
            for data_key, pdf_field_name in field_mapping.items():
                if pdf_field_name in fields and data_key in field_data:
                    data_to_fill[pdf_field_name] = field_data[data_key]
                    print(f"Campo mappato: {data_key} -> {pdf_field_name} = {field_data[data_key]}")

            if data_to_fill:
                print(f"DEBUG: Tentativo di compilare {len(data_to_fill)} campi: {list(data_to_fill.keys())}")
                try:
                    # Imposta NeedAppearances su True per forzare la visualizzazione dei campi
                    if "/AcroForm" in writer._root_object:
                        acro_form = writer._root_object["/AcroForm"]
                        if acro_form:
                            acro_form[NameObject("/NeedAppearances")] = True
                            print("DEBUG: Impostato NeedAppearances=True per AcroForm")

                    # Metodo più robusto per compilare i campi
                    for page_num, page in enumerate(writer.pages):
                        if "/Annots" in page:
                            for annot in page["/Annots"]:
                                annot_obj = annot.get_object()
                                if "/Subtype" in annot_obj and annot_obj["/Subtype"] == "/Widget":
                                    if "/T" in annot_obj:
                                        field_name = annot_obj["/T"]
                                        if field_name in data_to_fill:
                                            # Imposta il font di default per il campo
                                            if "/DA" not in annot_obj:
                                                annot_obj[NameObject("/DA")] = create_string_object("/Helvetica 10 Tf 0 g")
                                                print(f"DEBUG: Imposto font Helvetica per il campo {field_name}")

                                            # Rimuovi il background bianco del widget per renderlo trasparente
                                            if "/BG" in annot_obj:
                                                del annot_obj["/BG"]
                                                print(f"DEBUG: /BG rimosso dal campo {field_name} (background trasparente)")

                                            # Compila il campo direttamente
                                            annot_obj.update({
                                                NameObject("/V"): create_string_object(data_to_fill[field_name])
                                            })

                                            # Rimuovi l'appearance esistente per forzare la rigenerazione
                                            if "/AP" in annot_obj:
                                                del annot_obj["/AP"]
                                                print(f"DEBUG: /AP rimosso dal campo {field_name} per forzare rigenerazione")

                                            print(f"DEBUG: Campo {field_name} compilato con: {data_to_fill[field_name]}")
                    
                    print(f"Campi compilati con successo: {list(data_to_fill.keys())}")
                except Exception as e:
                    print(f"ERRORE nella compilazione dei campi: {e}")
                    # In modalità fields, se fallisce la compilazione, non usare coordinate
                    if text_mode == 'fields':
                        print("Modalità fields: compilazione fallita, nessun testo inserito")
                        with open(output_pdf_path, 'wb') as output_file:
                            writer.write(output_file)
                        return output_pdf_path
                    else:
                        print("Modalità automatic/coordinates: provo fallback su coordinate")
                        should_use_coordinates = True
            elif text_mode == 'automatic':
                # Solo in modalità automatica, fallback su coordinate se non trova campi
                print("Nessun campo corrispondente trovato, fallback su coordinate")
                should_use_coordinates = True
            elif text_mode == 'fields':
                # In modalità fields, non fare fallback se non trova campi
                print("Modalità campi PDF: nessun campo trovato, nessun testo inserito")
                print("DEBUG: Sto per salvare il PDF senza modifiche in modalità fields")
                # Salva il PDF senza modifiche
                with open(output_pdf_path, 'wb') as output_file:
                    writer.write(output_file)
                print("DEBUG: PDF salvato senza modifiche, esco dalla funzione")
                return output_path
        
        # Se necessario, usa le coordinate (fallback o modalità coordinate)
        if should_use_coordinates:
            print("Uso coordinate per inserire testo")
            return add_text_to_pdf_direct(input_pdf_path, output_pdf_path, field_data)
        
        # Se non dovrebbe usare né campi né coordinate, salva il PDF compilato
        print("DEBUG: Salvo PDF con campi compilati (SENZA appiattimento - già fatto da compile_and_flatten_pdf)")
        with open(output_pdf_path, 'wb') as output_file:
            writer.write(output_file)

        return output_pdf_path
                
    except Exception as e:
        print(f"Errore in fill_pdf_fields: {e}")
        # In caso di errore, rispetta la modalità testo
        if text_mode == 'fields':
            print("Modalità campi PDF: errore nella compilazione, nessun testo inserito")
            # Copia il file originale senza modifiche
            import shutil
            shutil.copy2(input_pdf_path, output_pdf_path)
            return output_pdf_path
        elif text_mode == 'coordinates':
            print("Modalità coordinate: errore, uso testo diretto come fallback")
            # Prova con il testo diretto
            try:
                return add_text_to_pdf_direct(input_pdf_path, output_pdf_path, field_data)
            except:
                # Se anche questo fallisce, copia il file originale
                import shutil
                shutil.copy2(input_pdf_path, output_pdf_path)
                return output_pdf_path
        else:  # automatic
            print("Modalità automatica: errore, provo con testo diretto come fallback")
            # Prova con il testo diretto
            try:
                return add_text_to_pdf_direct(input_pdf_path, output_pdf_path, field_data)
            except:
                # Se anche questo fallisce, copia il file originale
                import shutil
                shutil.copy2(input_pdf_path, output_pdf_path)
                return output_pdf_path
    
    # Salva il risultato se abbiamo usato i campi
    with open(output_pdf_path, 'wb') as output_file:
        writer.write(output_file)
    
    return output_pdf_path


def add_text_to_pdf_test(input_pdf_path, output_pdf_path, field_data, custom_positions):
    """
    Aggiunge testo direttamente su un PDF usando posizioni personalizzate per i test
    
    Args:
        input_pdf_path: Path del PDF originale
        output_pdf_path: Path dove salvare il PDF con testo
        field_data: Dizionario con i dati da aggiungere
        custom_positions: Dizionario con le posizioni personalizzate
    """
    from reportlab.pdfgen import canvas
    import io
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import A4
    
    # Leggi il PDF originale
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    
    # Se non ci sono dati da aggiungere, copia semplicemente il PDF
    if not field_data:
        for page in reader.pages:
            writer.add_page(page)
        
        with open(output_pdf_path, 'wb') as output_file:
            writer.write(output_file)
        return output_pdf_path
    
    # Ottieni le dimensioni della prima pagina
    first_page = reader.pages[0]
    page_width = float(first_page.mediabox.width)
    page_height = float(first_page.mediabox.height)
    
    # Se le coordinate sono state configurate per A4 (default), adattale alle dimensioni reali
    # A4 standard: 595.28 x 841.89 punti
    a4_width, a4_height = 595.28, 841.89
    
    # Calcola fattori di scala
    scale_x = page_width / a4_width if page_width != a4_width else 1.0
    scale_y = page_height / a4_height if page_height != a4_height else 1.0
    
    # Crea il layer di testo solo per la prima pagina con le dimensioni reali
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))
    
    # Configurazione font con dimensione personalizzata
    font_size = custom_positions.get('font_size', 10)
    if font_size == 'auto':
        # Usa dimensione automatica del campo PDF (non impostare font qui)
        pass
    else:
        font_size = int(font_size)
        can.setFont("Helvetica-Bold", font_size)
    can.setFillColorRGB(0, 0, 0)  # Nero
    
    # Aggiungi testo per sede tecnica con posizione personalizzata adattata
    if field_data.get('sede_tecnica'):
        x = custom_positions.get('sede_x', 50) * scale_x
        y = custom_positions.get('sede_y', 750) * scale_y
        can.drawString(x, y, field_data['sede_tecnica'])
    
    # Aggiungi testo per numero ordine con posizione personalizzata adattata
    if field_data.get('numero_ordine'):
        x = custom_positions.get('ordine_x', 50) * scale_x
        y = custom_positions.get('ordine_y', 735) * scale_y
        can.drawString(x, y, field_data['numero_ordine'])
    
    # Aggiungi testo per campi personalizzati con posizioni adattate
    custom_fields = custom_positions.get('custom_fields', [])
    for field in custom_fields:
        field_key = field['name'].lower().replace(' ', '_')
        if field_data.get(field_key):
            x = field['x'] * scale_x
            y = field['y'] * scale_y
            can.drawString(x, y, field_data[field_key])
    
    can.save()
    
    # Sovrapponi il layer di testo alla prima pagina
    packet.seek(0)
    text_layer = PdfReader(packet)
    
    # Processa tutte le pagine
    for i, page in enumerate(reader.pages):
        if i == 0 and text_layer.pages:
            # Prima pagina: unisci testo + contenuto originale
            text_page = text_layer.pages[0]
            
            # Unisci la pagina originale con il layer di testo
            page.merge_page(text_page)
            writer.add_page(page)
        else:
            # Pagine rimanenti: aggiungi senza modifiche
            writer.add_page(page)
    
    # Salva il risultato
    with open(output_pdf_path, 'wb') as output_file:
        writer.write(output_file)
    
    return output_pdf_path


def add_text_to_pdf_direct(input_pdf_path, output_pdf_path, field_data):
    """
    Aggiunge testo direttamente su un PDF in posizioni specifiche
    
    Args:
        input_pdf_path: Path del PDF originale
        output_pdf_path: Path dove salvare il PDF con testo
        field_data: Dizionario con i dati da aggiungere
    """
    from reportlab.pdfgen import canvas
    import io
    import json
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import A4
    
    print(f"DEBUG: add_text_to_pdf_direct - input={input_pdf_path}")
    print(f"DEBUG: add_text_to_pdf_direct - field_data={field_data}")
    
    # Carica le posizioni dalla configurazione
    try:
        config_path = get_path('data', 'flotte.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            positions = config.get('text_positions', {
                'sede_x': 50,
                'sede_y': 750,
                'ordine_x': 50,
                'ordine_y': 735,
                'font_size': 10
            })
    except:
        # Posizioni di default in caso di errore
        positions = {
            'sede_x': 50,
            'sede_y': 750,
            'ordine_x': 50,
            'ordine_y': 735,
            'font_size': 10
        }
    
    print(f"DEBUG: add_text_to_pdf_direct - positions={positions}")
    
    # Leggi il PDF originale
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    
    # Se non ci sono dati da aggiungere, copia semplicemente il PDF
    if not field_data.get('sede_tecnica') and not field_data.get('numero_ordine'):
        print("DEBUG: Nessun dato da inserire, copio PDF così com'è")
        for page in reader.pages:
            writer.add_page(page)
        
        with open(output_pdf_path, 'wb') as output_file:
            writer.write(output_file)
        return output_pdf_path
    
    # Ottieni le dimensioni della prima pagina
    first_page = reader.pages[0]
    page_width = float(first_page.mediabox.width)
    page_height = float(first_page.mediabox.height)
    
    print(f"Dimensioni pagina: {page_width} x {page_height}")
    print(f"Coordinate originali - Sede: ({positions['sede_x']}, {positions['sede_y']}), Ordine: ({positions['ordine_x']}, {positions['ordine_y']})")
    
    # Se le coordinate sono state configurate per A4 (default), adattale alle dimensioni reali
    # A4 standard: 595.28 x 841.89 punti
    a4_width, a4_height = 595.28, 841.89
    
    # Calcola fattori di scala
    scale_x = page_width / a4_width if page_width != a4_width else 1.0
    scale_y = page_height / a4_height if page_height != a4_height else 1.0
    
    # Adatta le coordinate al formato reale
    adapted_sede_x = positions['sede_x'] * scale_x
    adapted_sede_y = positions['sede_y'] * scale_y
    adapted_ordine_x = positions['ordine_x'] * scale_x  
    adapted_ordine_y = positions['ordine_y'] * scale_y
    
    print(f"Coordinate adattate - Sede: ({adapted_sede_x}, {adapted_sede_y}), Ordine: ({adapted_ordine_x}, {adapted_ordine_y})")
    
    # Crea il layer di testo solo per la prima pagina con le dimensioni reali
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))
    
    # Configurazione font con dimensione configurata
    if positions['font_size'] == 'auto':
        # Usa dimensione automatica del campo PDF (non impostare font qui)
        pass
    else:
        font_size = int(positions['font_size'])
        can.setFont("Helvetica-Bold", font_size)
    can.setFillColorRGB(0, 0, 0)  # Nero
    
    # Aggiungi testo per sede tecnica con posizioni adattate
    if field_data.get('sede_tecnica'):
        can.drawString(adapted_sede_x, adapted_sede_y, field_data['sede_tecnica'])
    
    # Aggiungi testo per numero ordine con posizioni adattate
    if field_data.get('numero_ordine'):
        can.drawString(adapted_ordine_x, adapted_ordine_y, field_data['numero_ordine'])
    
    can.save()
    
    # Sovrapponi il layer di testo alla prima pagina
    packet.seek(0)
    text_layer = PdfReader(packet)
    
    # Processa tutte le pagine
    for i, page in enumerate(reader.pages):
        if i == 0 and text_layer.pages:
            # Prima pagina: aggiungi il testo
            from pypdf import PageObject
            text_page = text_layer.pages[0]
            
            # Unisci la pagina originale con il layer di testo
            page.merge_page(text_page)
            writer.add_page(page)
        else:
            # Pagine rimanenti: aggiungi senza modifiche
            writer.add_page(page)
    
    # Salva il risultato
    with open(output_pdf_path, 'wb') as output_file:
        writer.write(output_file)
    
    return output_pdf_path


def merge_pdfs(pdf_paths, output_path):
    """
    Unisce più PDF in un unico file

    Args:
        pdf_paths: Lista di path dei PDF da unire
        output_path: Path dove salvare il PDF finale
    """
    writer = PdfWriter()

    for pdf_path in pdf_paths:
        if os.path.exists(pdf_path):
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                writer.add_page(page)

    # Salva il PDF unito
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)

    return output_path


def fill_operazioni_pdf(template_path, output_path, flotta_nome, operazioni_tutte_scadenze, text_mode='automatic', field_names=None):
    """
    Compila il template PDF delle operazioni aggiuntive con TUTTE le operazioni di TUTTE le scadenze

    Args:
        template_path: Path del PDF template
        output_path: Path dove salvare il PDF compilato
        flotta_nome: Nome della flotta per il campo sede_tecnica
        operazioni_tutte_scadenze: Lista di tuple (scadenza_nome, operazione) per max 5 operazioni totali
        text_mode: Modalità di inserimento testo
        field_names: Nomi personalizzati dei campi PDF
    """
    if field_names is None:
        field_names = {}
    field_data = {
        'sede_tecnica': flotta_nome
    }

    # Compila fino a 5 righe di operazioni (da TUTTE le scadenze)
    for i in range(5):
        if i < len(operazioni_tutte_scadenze):
            scadenza_nome, op = operazioni_tutte_scadenze[i]
            # Campi: scadenza1-5, testoscadenza1-5, CDL1-5
            field_data[f'scadenza{i+1}'] = scadenza_nome
            field_data[f'testoscadenza{i+1}'] = f"{op['titolo']}\n{op.get('descrizione', '')}"
            field_data[f'CDL{i+1}'] = op.get('cdl', '')
        else:
            # Campi vuoti se ci sono meno di 5 operazioni
            field_data[f'scadenza{i+1}'] = ''
            field_data[f'testoscadenza{i+1}'] = ''
            field_data[f'CDL{i+1}'] = ''

    fill_pdf_fields(template_path, output_path, field_data, text_mode, field_names)
    return output_path


def process_and_merge_pdfs(flotta_id, scadenze_data, config, sede_tecnica, numero_ordine, strumento='', scadenze_copie=None):
    """
    Processa tutti i PDF delle scadenze selezionate, compila i campi e li unisce

    Args:
        flotta_id: ID della flotta
        scadenze_data: Lista delle scadenze selezionate
        config: Configurazione completa
        sede_tecnica: Valore per il campo sede tecnica
        numero_ordine: Valore per il campo numero ordine
        strumento: Strumento di rilevazione quote (CALIPRI, WPMS, MANUALE)
        scadenze_copie: Dizionario con il numero di copie per ogni scadenza

    Returns:
        Path del PDF finale unito
    """
    print(f"DEBUG: process_and_merge_pdfs INIZIATO")
    print(f"DEBUG: flotta_id={flotta_id}, scadenze_data={scadenze_data}")
    print(f"DEBUG: sede_tecnica={sede_tecnica}, numero_ordine={numero_ordine}, strumento={strumento}")
    print(f"DEBUG: scadenze_copie={scadenze_copie}")
    
    # Default per scadenze_copie
    if scadenze_copie is None:
        scadenze_copie = {}
    
    # Estrai le configurazioni delle posizioni testo
    text_positions = config.get('text_positions', {})
    text_mode = text_positions.get('text_mode', 'automatic')
    field_names = {
        'sede_fieldname': text_positions.get('sede_fieldname', 'sede_tecnica'),
        'ordine_fieldname': text_positions.get('ordine_fieldname', 'numero_ordine')
    }
    
    print(f"DEBUG: process_and_merge_pdfs - config completa={config}")
    print(f"DEBUG: process_and_merge_pdfs - text_positions={text_positions}")
    print(f"Processamento con modalità testo: {text_mode}")
    print(f"Nomi campi PDF: {field_names}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = get_path('temp_pdfs', f'merge_{timestamp}')
    os.makedirs(temp_dir, exist_ok=True)

    compiled_pdfs = []

    # Prepara i dati per i campi documenti
    field_data = {
        'sede_tecnica': sede_tecnica,
        'numero_ordine': numero_ordine
    }

    # Trova il nome della flotta e determina se è multioggetto
    flotta_nome = ''
    is_multioggetto = False
    template_operazioni = None
    for f in config['flotte']:
        if f['id'] == flotta_id:
            flotta_nome = f['nome']
            is_multioggetto = f.get('multioggetto', False)
            template_operazioni = f.get('operazioni_pdf_template')
            break

    print(f"DEBUG: Flotta '{flotta_nome}' - is_multioggetto: {is_multioggetto}")

    # Ottieni operazioni globali filtrate per flotta
    operazioni_globali = config.get('operazioni_globali', [])
    # Filtra per flotta: mostra operazioni globali (senza flotta_id) o quelle specifiche per questa flotta
    operazioni_globali = [op for op in operazioni_globali if not op.get('flotta_id') or op.get('flotta_id') == flotta_id]

    # Raccoglie TUTTE le operazioni da TUTTE le scadenze selezionate
    tutte_operazioni = []

    # Aggiungi prima le operazioni globali
    for op_globale in operazioni_globali:
        tutte_operazioni.append(("GLOBALE", op_globale))

    # Raccogli TUTTI i documenti con le loro informazioni di copie per deduplicazione
    documenti_unici = {}  # chiave: pdf_path, valore: {'doc': doc, 'copie_finali': copie, 'scadenze': [scadenza_id]}
    
    # Processa ogni scadenza per raccogliere i documenti
    for scadenza_id in scadenze_data:
        # Trova i dati della scadenza
        scadenza_info = None
        for f in config['flotte']:
            if f['id'] == flotta_id:
                for s in f['scadenze']:
                    if s['id'] == scadenza_id:
                        scadenza_info = s
                        break
                if scadenza_info:
                    break
        
        if not scadenza_info:
            continue
            
        # Ottieni il numero di copie per questa scadenza
        copie_scadenza = scadenze_copie.get(scadenza_id, 1)
        
        # Processa i documenti della scadenza
        documenti = scadenza_info.get('documenti', [])
        print(f"DEBUG: Scadenza '{scadenza_info.get('nome', 'N/D')}' ha {len(documenti)} documenti")

        for doc in documenti:
            # Salta i documenti senza PDF (solo voci elenco)
            if not doc.get('pdf_path'):
                print(f" Voce senza PDF saltata: {doc.get('nome', 'N/D')}")
                continue
                
            # Filtra documenti per strumento se specificato
            doc_strumento = doc.get('strumento', '')

            # Includi il documento se:
            # - Non ha uno strumento specificato (documento standard) OPPURE
            # - Lo strumento corrisponde a quello selezionato
            if not doc_strumento or doc_strumento == strumento:
                doc_path = doc.get('pdf_path')
                print(f"DEBUG: Documento '{doc.get('nome', 'N/D')}' - pdf_path originale: '{doc_path}'")

                # Normalizza il percorso
                if doc_path:
                    # Se il percorso non è assoluto, costruiscilo usando get_path
                    if not os.path.isabs(doc_path):
                        doc_path = get_path('uploaded_pdfs', doc_path)
                    doc_path = os.path.normpath(doc_path)
                    print(f"DEBUG: Percorso finale calcolato: '{doc_path}'")
                    print(f"DEBUG: File esiste? {os.path.exists(doc_path)}")
                else:
                    print(f"DEBUG: pdf_path è vuoto/None per documento '{doc.get('nome', 'N/D')}'")

                if doc_path and os.path.exists(doc_path):
                    print(f"✓ Trovato documento: {doc.get('nome', 'N/D')} al percorso {doc_path}")
                    # Gestisci la deduplicazione
                    if doc_path in documenti_unici:
                        # Documento già presente, aggiorna le informazioni
                        if is_multioggetto:
                            # Per flotte multioggetto: SOMMA delle copie
                            documenti_unici[doc_path]['copie_finali'] += copie_scadenza
                        else:
                            # Per flotte standard: MASSIMO delle copie
                            documenti_unici[doc_path]['copie_finali'] = max(documenti_unici[doc_path]['copie_finali'], copie_scadenza)
                        documenti_unici[doc_path]['scadenze'].append(scadenza_id)
                    else:
                        # Nuovo documento
                        documenti_unici[doc_path] = {
                            'doc': doc,
                            'copie_finali': copie_scadenza,
                            'scadenze': [scadenza_id]
                        }

    # Ora processa i documenti unici deduplicati
    for doc_path, info in documenti_unici.items():
        doc = info['doc']
        copie_finali = info['copie_finali']
        
        metodo = "SOMMA" if is_multioggetto else "MASSIMO"
        print(f"Documento deduplicato: {doc.get('nome', 'N/D')} - copie: {copie_finali} ({metodo} da scadenze: {info['scadenze']})")
        
        # Compila il documento per ogni copia richiesta
        for copia_num in range(copie_finali):
            output_filename = f"compiled_{doc['id']}_copia{copia_num + 1}.pdf"
            output_path = os.path.join(temp_dir, output_filename)
            
            fill_pdf_fields(doc_path, output_path, field_data, text_mode, field_names)
            compiled_pdfs.append(output_path)

    # 2. Raccogli TUTTE le operazioni da TUTTE le scadenze selezionate
    for scadenza_id in scadenze_data:
        # Trova i dati della scadenza
        scadenza_info = None
        for f in config['flotte']:
            if f['id'] == flotta_id:
                for s in f['scadenze']:
                    if s['id'] == scadenza_id:
                        scadenza_info = s
                        break
                if scadenza_info:
                    break
        
        if not scadenza_info:
            continue

        # Raccogli le operazioni di questa scadenza
        operazioni = scadenza_info.get('operazioni_aggiuntive', [])
        for op in operazioni:
            tutte_operazioni.append((scadenza_info['nome'], op))
    for scadenza_id in scadenze_data:
        # Trova i dati della scadenza
        scadenza_info = None
        for f in config['flotte']:
            if f['id'] == flotta_id:
                for s in f['scadenze']:
                    if s['id'] == scadenza_id:
                        scadenza_info = s
                        break
                if scadenza_info:
                    break
        
        if not scadenza_info:
            continue

        # Raccogli le operazioni di questa scadenza
        operazioni = scadenza_info.get('operazioni_aggiuntive', [])
        for op in operazioni:
            tutte_operazioni.append((scadenza_info['nome'], op))

    # Funzione helper per controllare se ci sono operazioni reali (non vuote)
    def has_real_operations(operations_list):
        """Controlla se ci sono operazioni con contenuto reale (nome, descrizione o cdl non vuoti)"""
        for scadenza_nome, op in operations_list:
            if (op.get('nome', '').strip() or 
                op.get('descrizione', '').strip() or 
                op.get('cdl', '').strip()):
                return True
        return False

    # 3. Genera UN UNICO PDF con TUTTE le operazioni (max 5 totali)
    if template_operazioni and os.path.exists(template_operazioni) and has_real_operations(tutte_operazioni):
        output_filename = f"operazioni_tutte_{timestamp}.pdf"
        output_path = os.path.join(temp_dir, output_filename)

        try:
            fill_operazioni_pdf(
                template_operazioni,
                output_path,
                flotta_nome,
                tutte_operazioni[:5],  # Max 5 operazioni TOTALI
                text_mode,
                field_names
            )
            compiled_pdfs.append(output_path)
            
            # Se siamo in una flotta multioggetto, duplica il template per la SOMMA delle copie di tutte le scadenze
            # Altrimenti usa il MASSIMO come per le flotte standard
            if is_multioggetto:
                # Per flotte multioggetto: SOMMA delle copie
                total_copie = 0
                for scadenza_id_loop in scadenze_data:
                    copie = scadenze_copie.get(scadenza_id_loop, 1)
                    total_copie += copie
            else:
                # Per flotte standard: MASSIMO delle copie
                total_copie = 1
                for scadenza_id_loop in scadenze_data:
                    copie = scadenze_copie.get(scadenza_id_loop, 1)
                    if copie > total_copie:
                        total_copie = copie
            
            # Aggiungi copie aggiuntivi del template operazioni se necessario
            for copia_num in range(1, total_copie):
                output_filename_copia = f"operazioni_tutte_copia{copia_num + 1}_{timestamp}.pdf"
                output_path_copia = os.path.join(temp_dir, output_filename_copia)
                
                # Copia il template operazioni già compilato
                import shutil
                shutil.copy2(output_path, output_path_copia)
                compiled_pdfs.append(output_path_copia)
                
        except Exception as e:
            print(f"Errore nella compilazione del template operazioni {template_operazioni}: {e}")

    # 4. Genera il PDF con il TEMPLATE_OPERAZIONE_AGGIUNTIVE compilato
    modello_aggiuntive_path = "TEMPLATE_OPERAZIONE_AGGIUNTIVE.pdf"
    if has_real_operations(tutte_operazioni) and os.path.exists(modello_aggiuntive_path):
        output_filename = f"modello_operazioni_aggiuntive_{timestamp}.pdf"
        output_path = os.path.join(temp_dir, output_filename)
        
        try:
            # Prepara i dati per i campi del modello
            field_data_aggiuntive = {}
            
            # Compila i campi per ogni operazione (max 10 operazioni)
            for i, (scadenza_nome, operazione) in enumerate(tutte_operazioni[:10]):
                # Campi nome, descrizione e Cdl per ogni operazione
                field_data_aggiuntive[f'nome_{i+1}'] = operazione.get('nome', '')
                field_data_aggiuntive[f'descrizione_{i+1}'] = operazione.get('descrizione', '')
                field_data_aggiuntive[f'cdl_{i+1}'] = operazione.get('cdl', '')
            
            # Compila i campi vuoti per le operazioni rimanenti
            for i in range(len(tutte_operazioni[:10]), 10):
                field_data_aggiuntive[f'nome_{i+1}'] = ''
                field_data_aggiuntive[f'descrizione_{i+1}'] = ''
                field_data_aggiuntive[f'cdl_{i+1}'] = ''
            
            fill_pdf_fields(modello_aggiuntive_path, output_path, field_data_aggiuntive, text_mode, field_names)
            compiled_pdfs.append(output_path)
            
        except Exception as e:
            print(f"Errore nella compilazione del modello operazioni aggiuntive: {e}")

    # Se non ci sono PDF, ritorna None
    if not compiled_pdfs:
        return None

    # Unisci tutti i PDF compilati
    final_output = get_path('temp_pdfs', f'documenti_{flotta_id}_{timestamp}.pdf')
    merge_pdfs(compiled_pdfs, final_output)

    return final_output
