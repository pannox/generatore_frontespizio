import os
import logging
from datetime import datetime
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, create_string_object

logger = logging.getLogger('template_utils')
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

def compila_template_pdf(template_path, dati_compilazione, output_path, text_mode='fields', font_size='auto'):
    """
    Compila un template PDF con i dati forniti usando PyMuPDF per auto-sizing o pypdf come fallback
    """
    logger.info(f"Compilazione template: {os.path.basename(template_path)}")
    
    try:
        if font_size == 'auto':
            try:
                return _compila_con_pymupdf(template_path, dati_compilazione, output_path)
            except Exception as e:
                logger.debug(f"PyMuPDF fallito, uso pypdf: {e}")
                return _compila_con_pypdf(template_path, dati_compilazione, output_path, text_mode, font_size)
        else:
            return _compila_con_pypdf(template_path, dati_compilazione, output_path, text_mode, font_size)
    except Exception as e:
        logger.error(f"Errore nella compilazione del template: {e}")
        import shutil
        shutil.copy2(template_path, output_path)
        return output_path


# Funzione _compila_con_pymupdf rimossa - non usa più PyMuPDF


def _compila_con_fillpdf(template_path, dati_compilazione, output_path):
    """
    Compila PDF usando fillpdf con auto-sizing nativo
    """
    from fillpdf import fillpdfs
    
    logger.debug(f"Uso fillpdf per auto-sizing")
    
    # fillpdf vuole un dizionario semplice
    data_dict = {}
    for key, value in dati_compilazione.items():
        if value is not None:
            data_dict[key] = str(value)
            # Fallback per compatibilità: se è numero_ordine aggiungi anche numeroOrdine
            if key == 'numero_ordine':
                data_dict['numeroOrdine'] = str(value)
            # E viceversa, se è numeroOrdine aggiungi anche numero_ordine
            elif key == 'numeroOrdine':
                data_dict['numero_ordine'] = str(value)
    
    # Compila con fillpdf
    fillpdfs.write_fillable_pdf(template_path, output_path, data_dict)
    
    return output_path


def _compila_con_pypdf(template_path, dati_compilazione, output_path, text_mode, font_size):
    try:
        reader = PdfReader(template_path)
        writer = PdfWriter(clone_from=reader)  # Mantiene i campi modulo
        
        # Verifica che ci siano campi nel template
        fields = reader.get_fields()  # Usa reader invece di writer
        if not fields:
            logger.warning(f"Nessun campo modulo trovato nel template")
            with open(output_path, 'wb') as f:
                writer.write(f)
            return output_path
        
        logger.debug(f"Campi trovati: {len(fields)}")
        
        # Prepara i dati per la compilazione
        data_to_fill = {}
        physical_fields = set()  # Campi che esistono fisicamente nel PDF
        
        # Prima raccoglie tutti i campi fisici (gestisce duplicati)
        for page_idx, page in enumerate(writer.pages):
            if "/Annots" in page:
                for annot in page["/Annots"]:
                    annot_obj = annot.get_object()
                    if "/Subtype" in annot_obj and annot_obj["/Subtype"] == "/Widget":
                        if "/T" in annot_obj:
                            field_name = annot_obj["/T"]
                            physical_fields.add(str(field_name))
        
        # Poi prepara solo i dati che hanno campi fisici corrispondenti
        for campo_nome, valore in dati_compilazione.items():
            if valore is not None and campo_nome in physical_fields:
                data_to_fill[campo_nome] = str(valore)
                # Fallback per compatibilità: se è numero_ordine aggiungi anche numeroOrdine se esiste
                if campo_nome == 'numero_ordine' and 'numeroOrdine' in physical_fields:
                    data_to_fill['numeroOrdine'] = str(valore)
                # E viceversa, se è numeroOrdine aggiungi anche numero_ordine se esiste
                elif campo_nome == 'numeroOrdine' and 'numero_ordine' in physical_fields:
                    data_to_fill['numero_ordine'] = str(valore)
            elif valore is not None and campo_nome not in physical_fields:
                logger.warning(f"Campo '{campo_nome}' non ha widget nel PDF")
        
        logger.debug(f"Campi da compilare: {len(data_to_fill)}")
        
        # Compila i campi - gestisci duplicati compilando ogni widget individuale
        if data_to_fill and fields:
            try:
                # Itera su tutte le pagine e tutti i widget
                compiled_widgets = 0
                for page_idx, page in enumerate(writer.pages):
                    if "/Annots" in page:
                        for annot in page["/Annots"]:
                            annot_obj = annot.get_object()
                            if "/Subtype" in annot_obj and annot_obj["/Subtype"] == "/Widget":
                                if "/T" in annot_obj:
                                    field_name = annot_obj["/T"]
                                    if field_name in data_to_fill:
                                        # Imposta font se necessario
                                        if font_size != 'auto':
                                            if "/DA" in annot_obj:
                                                da_value = annot_obj["/DA"]
                                                da_str = str(da_value)
                                                import re
                                                new_da = re.sub(r'(/ArialMT\s+)\d+(\s+Tf)', r'\g<1>' + str(font_size) + r'\g<2>', da_str)
                                                if new_da == da_str:
                                                    parts = da_str.split()
                                                    if len(parts) >= 3 and parts[0] == '/ArialMT' and parts[2] == 'Tf':
                                                        parts[1] = str(font_size)
                                                        new_da = ' '.join(parts)
                                                annot_obj[NameObject("/DA")] = create_string_object(new_da)
                                        
                                        # Imposta il valore direttamente nel widget
                                        annot_obj.update()
                                        compiled_widgets += 1
                
                # Imposta i valori per tutti i campi in tutte le pagine
                for page in writer.pages:
                    try:
                        writer.update_page_form_field_values(page, data_to_fill)
                    except Exception as e:
                        logger.debug(f"Errore update_page_form_field_values: {e}")
                
                logger.debug(f"Compilati {compiled_widgets} widget")
            except Exception as e:
                logger.error(f"Errore nella compilazione dei campi: {e}")
                if text_mode == 'fields':
                    with open(output_path, 'wb') as f:
                        writer.write(f)
                    return output_path
        
        # Salva il risultato
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        return output_path
        
    except Exception as e:
        print(f"ERRORE in compila_template_pdf: {e}")
        # In caso di errore, copia il template originale
        import shutil
        shutil.copy2(template_path, output_path)
        return output_path

def formatta_lista_scadenze(scadenze_ids, config):
    """
    Formatta la lista delle scadenze separata da trattini
    
    Args:
        scadenze_ids: Lista di ID delle scadenze
        config: Configurazione del sistema
    
    Returns:
        Stringa formattata delle scadenze
    """
    scadenze_nomi = []
    
    for flotta in config.get('flotte', []):
        for scadenza in flotta.get('scadenze', []):
            if scadenza['id'] in scadenze_ids:
                scadenze_nomi.append(scadenza['nome'])
    
    return " - ".join(scadenze_nomi) if scadenze_nomi else ""

def formatta_lista_documenti(scadenze_data, config, scadenze_copie=None, strumento_selezionato=''):
    """
    Formatta la lista dei documenti con informazioni copie e strumento
    Deduplica i documenti con lo stesso nome sommando le copie

    Args:
        scadenze_data: Dizionario con dati delle scadenze
        config: Configurazione del sistema
        scadenze_copie: Dizionario con numero copie per scadenza
        strumento_selezionato: Strumento selezionato (WPMS/MANUALE/CALIPRI) o vuoto

    Returns:
        Stringa formattata dei documenti
    """
    # Dizionario per deduplicare: chiave = nome documento, valore = copie totali
    documenti_dedup = {}

    print(f"DEBUG formatta_lista_documenti: strumento_selezionato = '{strumento_selezionato}' (tipo: {type(strumento_selezionato)})")
    print(f"DEBUG formatta_lista_documenti: strumento vuoto? {not strumento_selezionato or strumento_selezionato == ''}")

    for flotta in config.get('flotte', []):
        for scadenza in flotta.get('scadenze', []):
            if scadenza['id'] in scadenze_data:
                scadenza_info = scadenze_data[scadenza['id']]

                for doc in scadenza_info.get('documenti', []):
                    print(f"DEBUG: Documento '{doc.get('nome')}' - obbligatorio: {doc.get('obbligatorio', False)}, strumento: {doc.get('strumento', None)}")
                    if doc.get('obbligatorio', False):
                        # Controlla se il documento ha il campo strumento
                        doc_strumento = doc.get('strumento', None)
                        print(f"DEBUG:   doc_strumento = '{doc_strumento}' (type: {type(doc_strumento)})")
                        print(f"DEBUG:   doc_strumento is None? {doc_strumento is None}")
                        print(f"DEBUG:   doc_strumento vuoto? {not doc_strumento or doc_strumento == ''}")

                        # Documento normale = senza strumento (None o stringa vuota)
                        if not doc_strumento or doc_strumento == '':
                            # Documento normale senza campo strumento -> aggiungi sempre
                            print(f"DEBUG: ✓✓✓ Aggiunto documento normale '{doc['nome']}' (senza strumento o strumento vuoto)")
                            aggiungi_documento = True
                        elif not strumento_selezionato or strumento_selezionato == '':
                            # Nessuno strumento selezionato -> includi tutti i documenti con strumento
                            print(f"DEBUG: ✓✓✓ Aggiunto documento '{doc['nome']}' con strumento '{doc_strumento}' (nessun filtro attivo)")
                            aggiungi_documento = True
                        else:
                            # Documento con campo strumento E strumento selezionato
                            # Aggiungi solo se corrisponde allo strumento selezionato
                            print(f"DEBUG:   Confronto: doc_strumento '{doc_strumento}' == strumento_selezionato '{strumento_selezionato}' ?")
                            if doc_strumento == strumento_selezionato:
                                print(f"DEBUG: ✓✓✓ Aggiunto documento strumento '{doc['nome']}' (corrisponde a '{strumento_selezionato}')")
                                aggiungi_documento = True
                            else:
                                print(f"DEBUG: ✗✗✗ Saltato documento strumento '{doc['nome']}' (strumento '{doc_strumento}' != '{strumento_selezionato}')")
                                aggiungi_documento = False

                        if aggiungi_documento:
                            # Determina le copie per questa scadenza
                            copie = 1
                            if scadenze_copie and scadenza['id'] in scadenze_copie:
                                copie = scadenze_copie[scadenza['id']]

                            doc_nome = doc['nome']

                            # Deduplica: somma le copie se il documento esiste già
                            if doc_nome in documenti_dedup:
                                documenti_dedup[doc_nome] += copie
                                print(f"DEBUG: Documento '{doc_nome}' già presente, sommo copie: {documenti_dedup[doc_nome]}")
                            else:
                                documenti_dedup[doc_nome] = copie
                                print(f"DEBUG: Nuovo documento '{doc_nome}' con {copie} copie")

    # Formatta la lista finale deduplicata
    documenti_lista = []
    for doc_nome, copie_totali in documenti_dedup.items():
        riga = f"{doc_nome} - {copie_totali} cop{'ia' if copie_totali == 1 else 'ie'}     [ ]"
        documenti_lista.append(riga)

    print(f"DEBUG: Documenti finali deduplicati: {documenti_lista}")
    return "\n".join(documenti_lista) if documenti_lista else "Nessun documento selezionato"

def formatta_lista_operazioni(scadenze_data, config):
    """
    Formatta la lista delle operazioni con titolo, descrizione e CDL
    
    Args:
        scadenze_data: Dizionario con dati delle scadenze
        config: Configurazione del sistema
    
    Returns:
        Stringa formattata delle operazioni
    """
    operazioni_lista = []
    
    for flotta in config.get('flotte', []):
        for scadenza in flotta.get('scadenze', []):
            if scadenza['id'] in scadenze_data:
                scadenza_info = scadenze_data[scadenza['id']]
                
                for operazione in scadenza_info.get('operazioni_aggiuntive', []):
                    titolo = operazione.get('titolo', '').strip()
                    descrizione = operazione.get('descrizione', '').strip()
                    cdl = operazione.get('cdl', '').strip()

                    # Formatta la riga operazione
                    if titolo:
                        riga = f"• {titolo}"
                        if descrizione:
                            riga += f" - {descrizione}"
                        if cdl:
                            riga += f" (CDL: {cdl})"
                        operazioni_lista.append(riga)

    return "\n".join(operazioni_lista) if operazioni_lista else "Nessuna operazione aggiuntiva"

def prepara_dati_frontespizio(flotta_id, scadenze_ids, config, dati_utente, scadenze_copie=None):
    """
    Prepara i dati per la compilazione del template frontespizio
    
    Args:
        flotta_id: ID della flotta
        scadenze_ids: Lista ID scadenze selezionate
        config: Configurazione del sistema
        dati_utente: Dizionario con dati utente (sede, ordine, strumento)
        scadenze_copie: Dizionario con copie per scadenza
    
    Returns:
        Dizionario con dati pronti per il template
    """
    # Trova nome flotta
    flotta_nome = ""
    for flotta in config.get('flotte', []):
        if flotta['id'] == flotta_id:
            flotta_nome = flotta['nome']
            break
    
    # Prepara dati scadenze
    scadenze_data = {}
    for flotta in config.get('flotte', []):
        for scadenza in flotta.get('scadenze', []):
            if scadenza['id'] in scadenze_ids:
                scadenze_data[scadenza['id']] = scadenza
    
    # Calcola totali (considerando il filtro strumento)
    totale_documenti = 0
    strumento_selezionato = dati_utente.get('strumento', '')
    for scadenza_info in scadenze_data.values():
        for doc in scadenza_info.get('documenti', []):
            if doc.get('obbligatorio', False):
                # Applica lo stesso filtro strumento usato in formatta_lista_documenti
                doc_strumento = doc.get('strumento', None)
                # Documento normale = senza strumento (None o stringa vuota)
                if not doc_strumento or doc_strumento == '':
                    # Documento normale senza strumento -> conta sempre
                    totale_documenti += 1
                elif not strumento_selezionato or strumento_selezionato == '':
                    # Nessuno strumento selezionato -> conta tutti i documenti con strumento
                    totale_documenti += 1
                elif doc_strumento == strumento_selezionato:
                    # Documento con strumento corrispondente -> conta
                    totale_documenti += 1
                # Altrimenti (strumento non corrispondente) -> non contare
    
    totale_copie = 0
    if scadenze_copie:
        totale_copie = sum(scadenze_copie.values())
    else:
        totale_copie = len(scadenze_ids)
    
    # Prepara dati template
    dati_template = {
        'sede_tecnica': dati_utente.get('sede_tecnica', ''),
        'numero_ordine': dati_utente.get('numero_ordine', ''),
        'data_generazione': datetime.now().strftime("%d/%m/%Y"),
        'versione_sito': config.get('versione', {}).get('numero', ''),
        'data_versione': config.get('versione', {}).get('data', ''),
        'strumento': dati_utente.get('strumento', ''),
        'flotta_nome': flotta_nome,
        'lista_scadenze': formatta_lista_scadenze(scadenze_ids, config),
        'lista_documenti': formatta_lista_documenti(scadenze_data, config, scadenze_copie, dati_utente.get('strumento', '')),
        'lista_operazioni': formatta_lista_operazioni(scadenze_data, config),
        'totale_documenti': str(totale_documenti),
        'totale_scadenze': str(len(scadenze_ids)),
        'copie_totali': str(totale_copie)
    }
    
    return dati_template

def prepara_dati_operazioni(flotta_id, scadenze_ids, config, dati_utente):
    """
    Prepara i dati per la compilazione del template operazioni
    
    Args:
        flotta_id: ID della flotta
        scadenze_ids: Lista ID scadenze selezionate
        config: Configurazione del sistema
        dati_utente: Dizionario con dati utente
    
    Returns:
        Dizionario con dati pronti per il template
    """
    print(f"DEBUG: prepara_dati_operazioni ricevuto dati_utente: {list(dati_utente.keys())}")
    print(f"DEBUG: prepara_dati_operazioni valore numero_ordine: '{dati_utente.get('numero_ordine', 'NON TROVATO')}'")
    
    # Trova nome flotta
    flotta_nome = ""
    for flotta in config.get('flotte', []):
        if flotta['id'] == flotta_id:
            flotta_nome = flotta['nome']
            break
    
    # Prepara dati scadenze
    scadenze_data = {}
    for flotta in config.get('flotte', []):
        for scadenza in flotta.get('scadenze', []):
            if scadenza['id'] in scadenze_ids:
                scadenze_data[scadenza['id']] = scadenza
    
    # Ottieni operazioni globali filtrate per flotta
    operazioni_globali = config.get('operazioni_globali', [])
    # Filtra per flotta: mostra operazioni globali (senza flotta_id) o quelle specifiche per questa flotta
    operazioni_globali = [op for op in operazioni_globali if not op.get('flotta_id') or op.get('flotta_id') == flotta_id]

    # Raccoglie tutte le operazioni
    operazioni_completo = []
    
    # Aggiungi prima le operazioni globali
    for operazione in operazioni_globali:
        titolo = operazione.get('titolo', '').strip()
        descrizione = operazione.get('descrizione', '').strip()
        cdl = operazione.get('cdl', '').strip()
        
        if titolo:
            # Prima linea della descrizione
            testo_descrizione = ""
            if descrizione:
                testo_descrizione = descrizione.split('\n')[0].strip()
            
            # Formatta in una sola riga: titolo testo (GLOBALE) - CDL ☐
            riga = f"{titolo}"
            if testo_descrizione:
                riga += f" {testo_descrizione}"
            riga += " (GLOBALE)"
            if cdl:
                riga += f" - {cdl}"
            
            # Aggiungi casella di spunta alla fine (compatibile con ArialMT)
            riga += "     [ ]"
            
            operazioni_completo.append(riga)
    
    # Poi aggiungi le operazioni delle scadenze
    for scadenza_id in scadenze_ids:
        for flotta in config.get('flotte', []):
            for scadenza in flotta.get('scadenze', []):
                if scadenza['id'] == scadenza_id:
                    for operazione in scadenza.get('operazioni_aggiuntive', []):
                        titolo = operazione.get('titolo', '').strip()
                        descrizione = operazione.get('descrizione', '').strip()
                        cdl = operazione.get('cdl', '').strip()
                        scadenza_nome = scadenza.get('nome', '').strip()
                        
                        if titolo:
                            # Prima linea della descrizione
                            testo_descrizione = ""
                            if descrizione:
                                testo_descrizione = descrizione.split('\n')[0].strip()
                            
                            # Formatta in una sola riga: titolo testo (scadenza) - CDL ☐
                            riga = f"{titolo}"
                            if testo_descrizione:
                                riga += f" {testo_descrizione}"
                            if scadenza_nome:
                                riga += f" ({scadenza_nome})"
                            if cdl:
                                riga += f" - {cdl}"
                            
                            # Aggiungi casella di spunta alla fine (compatibile con ArialMT)
                            riga += "     [ ]"
                            
                            operazioni_completo.append(riga)
    
    # Prepara dati template
    dati_template = {
        'sede_tecnica': dati_utente.get('sede_tecnica', ''),
        'numero_ordine': dati_utente.get('numero_ordine', ''),
        'data_generazione': datetime.now().strftime("%d/%m/%Y"),
        'versione_sito': config.get('versione', {}).get('numero', ''),
        'data_versione': config.get('versione', {}).get('data', ''),
        'flotta_nome': flotta_nome,
        'lista_operazioni': "\n" + "\n\n".join(operazioni_completo).strip(),  # Usa lista_operazioni come nel template
        'operazioni_completo': "\n".join(operazioni_completo).strip(),  # Mantiene anche questo per compatibilità
        'totale_operazioni': str(len([op for scad in scadenze_data.values() for op in scad.get('operazioni_aggiuntive', [])])),
        'numero_scadenze': str(len(scadenze_ids))
    }
    
    return dati_template


def compila_template_pdf_semplice(template_path, dati_compilazione, output_path, text_mode='fields', font_size='auto', default_font_size=10, update_da=True):
    """
    Versione semplificata e cross-platform della compilazione PDF.
    Usa compile_and_flatten_pdf da pdf_utils per compilare E appiattire i campi.

    Args:
        template_path: Path del template PDF
        dati_compilazione: Dizionario con i dati da compilare
        output_path: Path dove salvare il PDF compilato
        text_mode: Modalità testo ('fields', 'coordinates', 'automatic')
        font_size: Dimensione font ('auto' o numero)
        default_font_size: Font size di default se auto (10pt)
        update_da: se True, aggiorna il /DA con il nuovo font size

    Returns:
        Path del PDF compilato (o template originale se errore)
    """
    # Forza modalità fields per semplicità
    if text_mode != 'fields':
        logger.debug(f"Modalità '{text_mode}' non supportata, uso 'fields'")
        text_mode = 'fields'

    # Converti font_size se necessario
    if font_size == 'auto':
        font_size = default_font_size
    else:
        try:
            font_size = int(font_size)
        except:
            font_size = default_font_size

    try:
        # Usa compile_and_flatten_pdf da pdf_utils per compilare E appiattire
        from pdf_utils import compile_and_flatten_pdf

        logger.debug(f"Uso compile_and_flatten_pdf per {os.path.basename(template_path)}")
        success = compile_and_flatten_pdf(template_path, output_path, dati_compilazione, font_size=font_size, text_mode=text_mode)

        if success:
            logger.debug(f"✓ Template compilato e appiattito con successo")
            return output_path
        else:
            logger.error(f"compile_and_flatten_pdf ha fallito")
            raise Exception("Compilazione fallita")

    except Exception as e:
        logger.error(f"Errore nella compilazione: {e}", exc_info=True)
        # Fallback finale: copia il template originale
        import shutil
        shutil.copy2(template_path, output_path)
        return output_path


def _compila_con_pypdf_annotazioni(template_path, dati_compilazione, output_path, font_size, update_da=True):
    """
    Compilazione usando pypdf iterando su /Annots (stessa logica di fill_pdf_fields che funziona)
    Questa è la logica collaudata usata per i PDF delle scadenze.
    
    Args:
        update_da: se True, aggiorna il /DA con il nuovo font size. Se False, lascia il /DA originale
    """
    try:
        reader = PdfReader(template_path)
        writer = PdfWriter(clone_from=reader)
        
        logger.debug(f"Apertura PDF: {os.path.basename(template_path)}")
        
        # Converte font_size a intero
        font_size_int = 10
        if isinstance(font_size, int):
            font_size_int = font_size
        elif isinstance(font_size, str) and font_size != 'auto':
            try:
                font_size_int = int(font_size)
            except ValueError:
                font_size_int = 10
        
        logger.debug(f"Font size usato: {font_size_int}")
        
        compiled_count = 0
        
        # Itera su tutte le pagine e annots (COME FUNZIONA IN fill_pdf_fields)
        for page_num, page in enumerate(writer.pages):
            if "/Annots" in page:
                for annot in page["/Annots"]:
                    annot_obj = annot.get_object()
                    if "/Subtype" in annot_obj and annot_obj["/Subtype"] == "/Widget":
                        if "/T" in annot_obj:
                            field_name = annot_obj["/T"]
                            logger.debug(f"Widget trovato: {field_name}")
                            
                            if field_name in dati_compilazione:
                                valore = str(dati_compilazione[field_name])
                                
                                # Imposta il font di default per il campo
                                if "/DA" not in annot_obj:
                                    da_string = f"/Helvetica {font_size_int} Tf 0 g"
                                    annot_obj[NameObject("/DA")] = create_string_object(da_string)
                                    logger.debug(f"Widget {field_name}: /DA creato")
                                
                                # Se update_da, aggiorna il /DA
                                if update_da:
                                    da_original = str(annot_obj.get("/DA", ""))
                                    # Estrai font name da DA string
                                    import re
                                    match = re.search(r'/(\w+)\s+\d+\s+Tf', da_original)
                                    font_name = match.group(1) if match else "Helvetica"
                                    da_string = f"/{font_name} {font_size_int} Tf 0 g"
                                    annot_obj[NameObject("/DA")] = create_string_object(da_string)
                                    logger.debug(f"Widget {field_name}: /DA aggiornato a {font_size_int}pt")
                                
                                # Rimuovi background bianco
                                if "/BG" in annot_obj:
                                    del annot_obj["/BG"]
                                    logger.debug(f"Widget {field_name}: /BG rimosso")
                                
                                # Compila il campo direttamente (COME FA fill_pdf_fields)
                                annot_obj.update({
                                    NameObject("/V"): create_string_object(valore)
                                })
                                compiled_count += 1
                                logger.debug(f"Widget compilato: {field_name} = {valore}")
        
        logger.info(f"Compilati {compiled_count} widget")
        
        # Salva il PDF
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        logger.debug(f"PDF salvato: {output_path}")
        
        # Appiattisci per renderizzare visivamente
        if compiled_count > 0:
            try:
                from pdf_optimization import flatten_pdf_fields
                logger.debug("Appiattisco i campi per renderizzare visivamente...")
                flatten_pdf_fields(output_path)
                logger.info("Campi appiattiti e testo visibile renderizzato")
            except Exception as flatten_err:
                logger.warning(f"Errore appiattimento campi: {flatten_err} - continuo comunque")
        
        return output_path
    
    except Exception as e:
        logger.error(f"Errore compilazione: {e}", exc_info=True)
        # Fallback: copia il file originale
        import shutil
        shutil.copy2(template_path, output_path)
        return output_path


def _compila_con_pypdf_semplice(template_path, dati_compilazione, output_path, font_size, update_da=True):
    """
    Compilazione semplificata usando solo pypdf - massima compatibilità cross-platform
    Usa la stessa logica robusta del codice originale ma senza PyMuPDF
    
    Args:
        update_da: se True, aggiorna il /DA con il nuovo font size. Se False, lascia il /DA originale
    """
    try:
        reader = PdfReader(template_path)
        logger.debug(f"PDF aperto: {len(reader.pages)} pagine")
        
        # Usa clone_from per preservare meglio i widget
        writer = PdfWriter(clone_from=reader)

        # Verifica che ci siano campi nel template
        fields = reader.get_fields()
        logger.debug(f"get_fields() ha trovato: {len(fields) if fields else 0} campi")
        
        # Conta widget tramite annotazioni (più affidabile di get_fields())
        widget_count = 0
        for page in reader.pages:
            if "/Annots" in page:
                for annot in page["/Annots"]:
                    annot_obj = annot.get_object()
                    if "/Subtype" in annot_obj and annot_obj["/Subtype"] == "/Widget":
                        widget_count += 1
        
        logger.debug(f"Widget trovati tramite annotazioni: {widget_count}")
        
        if widget_count == 0 and (not fields or len(fields) == 0):
            logger.warning(f"Nessun campo modulo trovato in {os.path.basename(template_path)}")
            with open(output_path, 'wb') as f:
                writer.write(f)
            return output_path

        logger.debug(f"Campi trovati: {len(fields) if fields else 0} (tramite get_fields), {widget_count} (tramite annotazioni)")
        if fields:
            logger.info(f"Campi nel template: {list(fields.keys())}")

        # Prepara dati per compilazione e identifica campi fisici
        data_to_fill = {}
        physical_fields = set()

        # Prima raccoglie tutti i campi fisici (gestisce duplicati)
        for page_idx, page in enumerate(writer.pages):
            if "/Annots" in page:
                for annot in page["/Annots"]:
                    annot_obj = annot.get_object()
                    if "/Subtype" in annot_obj and annot_obj["/Subtype"] == "/Widget":
                        if "/T" in annot_obj:
                            field_name = annot_obj["/T"]
                            physical_fields.add(str(field_name))
        
        logger.debug(f"Campi widget trovati nel PDF: {physical_fields}")

        # Poi prepara solo i dati che hanno campi fisici corrispondenti
        logger.debug(f"Dati ricevuti da compilare: {list(dati_compilazione.keys())}")
        for campo_nome, valore in dati_compilazione.items():
            # Converti None in stringa vuota
            if valore is None:
                valore = ""
            
            # Compila anche campi vuoti se il campo fisico esiste
            if campo_nome in physical_fields:
                data_to_fill[campo_nome] = str(valore)
                logger.debug(f"Campo '{campo_nome}' = '{valore}' (trovato nel PDF)")
                # Fallback per compatibilità: se è numero_ordine aggiungi anche numeroOrdine se esiste
                if campo_nome == 'numero_ordine' and 'numeroOrdine' in physical_fields:
                    data_to_fill['numeroOrdine'] = str(valore)
                # E viceversa, se è numeroOrdine aggiungi anche numero_ordine se esiste
                elif campo_nome == 'numeroOrdine' and 'numero_ordine' in physical_fields:
                    data_to_fill['numero_ordine'] = str(valore)
            elif valore is not None and valore != "":
                logger.debug(f"Campo '{campo_nome}' = '{valore}' (NON trovato nel PDF - widget mancante)")

        logger.debug(f"Campi da compilare: {len(data_to_fill)}")
        if data_to_fill:
            logger.info(f"Dati da compilare: {data_to_fill}")
        else:
            logger.warning(f"NESSUN DATO DA COMPILARE! Dati ricevuti: {dati_compilazione}")

        # Compila i campi
        if data_to_fill:
            try:
                # Converte font_size a intero se è "auto" o stringa
                font_size_int = 10
                if isinstance(font_size, int):
                    font_size_int = font_size
                elif isinstance(font_size, str) and font_size != 'auto':
                    try:
                        font_size_int = int(font_size)
                    except ValueError:
                        font_size_int = 10
                
                logger.debug(f"Font size usato: {font_size_int}")
                
                # Itera su tutte le pagine e tutti i widget per impostare i valori
                compiled_widgets = 0
                for page_idx, page in enumerate(writer.pages):
                    if "/Annots" in page:
                        for annot in page["/Annots"]:
                            annot_obj = annot.get_object()
                            if "/Subtype" in annot_obj and annot_obj["/Subtype"] == "/Widget":
                                if "/T" in annot_obj:
                                    field_name = annot_obj["/T"]
                                    if field_name in data_to_fill:
                                        # Assicura che il widget abbia un /DA (default appearance)
                                        if "/DA" not in annot_obj:
                                            da_string = f"/Helvetica {font_size_int} Tf 0 g"
                                            annot_obj[NameObject("/DA")] = create_string_object(da_string)
                                            logger.debug(f"Widget {field_name}: /DA creato mancante")
                                        
                                        # Se update_da è True, aggiorna il /DA con il nuovo font size
                                        if update_da:
                                            font_name = "Helvetica"
                                            da_original = str(annot_obj["/DA"])
                                            # Estrai il font name (es. "/Helvetica" da "/Helvetica 10 Tf 0 g")
                                            import re
                                            match = re.search(r'/(\w+)\s+\d+\s+Tf', da_original)
                                            if match:
                                                font_name = match.group(1)
                                            
                                            # Aggiorna il /DA con il nuovo font size
                                            da_string = f"/{font_name} {font_size_int} Tf 0 g"
                                            annot_obj[NameObject("/DA")] = create_string_object(da_string)
                                            logger.debug(f"Widget {field_name}: /DA aggiornato a {font_size_int}pt")
                                        
                                        # Rimuovi il background bianco del widget per renderlo trasparente
                                        if "/BG" in annot_obj:
                                            del annot_obj["/BG"]
                                            logger.debug(f"Widget {field_name}: /BG rimosso (background trasparente)")
                                        
                                        # Aggiungi il valore compilato
                                        annot_obj[NameObject("/V")] = create_string_object(data_to_fill[field_name])
                                        annot_obj[NameObject("/AS")] = NameObject(f"/{font_size_int}")
                                        annot_obj.update()
                                        compiled_widgets += 1
                                        logger.debug(f"Widget compilato: {field_name} = {data_to_fill[field_name]}")

                logger.debug(f"Compilati {compiled_widgets} widget")
                
                # Salva il PDF con i dati compilati
                with open(output_path, 'wb') as temp_file:
                    writer.write(temp_file)
                
                logger.debug(f"PDF salvato con valori compilati: {output_path}")
                
                # Appiattisci i campi per renderizzare il testo visivamente (come fa fill_pdf_fields)
                if compiled_widgets > 0:
                    try:
                        from pdf_optimization import flatten_pdf_fields
                        logger.debug("Appiattisco i campi per renderizzare visivamente...")
                        flatten_pdf_fields(output_path)
                        logger.info("Campi appiattiti e testo visibile renderizzato")
                    except Exception as flatten_err:
                        logger.warning(f"Errore appiattimento campi: {flatten_err} - continuo comunque")

            except Exception as e:
                logger.error(f"Errore nella compilazione dei campi: {e}")
                # In caso di errore, salva il PDF senza modifiche
                with open(output_path, 'wb') as f:
                    writer.write(f)
                return output_path
        else:
            # Se nessun dato da compilare, salva il PDF come è
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)

        logger.info(f"PDF compilato salvato: {os.path.basename(output_path)}")
        return output_path

    except Exception as e:
        logger.error(f"Errore compilazione PDF: {e}")
        # Fallback: copia template originale
        import shutil
        shutil.copy2(template_path, output_path)
        return output_path
