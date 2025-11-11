import os
import logging
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

LOG_LEVEL = logging.INFO
logger = logging.getLogger('pdf_optimization')
logger.setLevel(LOG_LEVEL)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_path(*parts):
    return os.path.join(BASE_DIR, *parts)

def cleanup_old_temp_files(max_age_hours=24):
    """
    Pulisce i file temporanei più vecchi di max_age_hours
    
    Args:
        max_age_hours: Età massima in ore prima di eliminare (default: 24)
    """
    temp_dir = get_path('temp_pdfs')
    if not os.path.exists(temp_dir):
        return
    
    cutoff_time = time.time() - (max_age_hours * 3600)
    deleted_count = 0
    freed_space_mb = 0
    
    try:
        for root, dirs, files in os.walk(temp_dir, topdown=False):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    if os.path.getmtime(filepath) < cutoff_time:
                        size_kb = os.path.getsize(filepath) / 1024
                        os.remove(filepath)
                        deleted_count += 1
                        freed_space_mb += size_kb / 1024
                        logger.debug(f"Eliminato: {filepath} ({size_kb:.2f} KB)")
                except Exception as e:
                    logger.warning(f"Errore eliminazione {filepath}: {e}")
            
            for dir_name in dirs:
                dirpath = os.path.join(root, dir_name)
                try:
                    if os.path.isdir(dirpath) and not os.listdir(dirpath):
                        os.rmdir(dirpath)
                        logger.debug(f"Cartella vuota rimossa: {dirpath}")
                except Exception as e:
                    logger.warning(f"Errore rimozione cartella {dirpath}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Pulizia completata: {deleted_count} file eliminati ({freed_space_mb:.2f} MB liberati)")
    
    except Exception as e:
        logger.error(f"Errore durante pulizia temp: {e}")

def cleanup_single_file(filepath):
    """
    Elimina un singolo file temporaneo
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.debug(f"File eliminato: {filepath}")
            return True
    except Exception as e:
        logger.warning(f"Errore eliminazione {filepath}: {e}")
    return False

def cleanup_merge_directories(max_age_hours=24):
    """
    Pulisce le cartelle di merge non utilizzate
    """
    temp_dir = get_path('temp_pdfs')
    if not os.path.exists(temp_dir):
        return
    
    cutoff_time = time.time() - (max_age_hours * 3600)
    deleted_count = 0
    
    try:
        for item in os.listdir(temp_dir):
            if item.startswith('merge_'):
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path):
                    try:
                        if os.path.getmtime(item_path) < cutoff_time:
                            shutil.rmtree(item_path)
                            deleted_count += 1
                            logger.debug(f"Cartella merge eliminata: {item_path}")
                    except Exception as e:
                        logger.warning(f"Errore rimozione {item_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cartelle merge pulite: {deleted_count} cartelle eliminate")
    
    except Exception as e:
        logger.error(f"Errore durante pulizia merge: {e}")

def compress_pdf(input_path, output_path=None):
    """
    Comprime un PDF usando PyMuPDF
    
    Args:
        input_path: Percorso del PDF da comprimere
        output_path: Percorso output (default: sovrascrivi input)
    
    Returns:
        True se compressione riuscita, False altrimenti
    """
    if output_path is None:
        output_path = input_path
    
    try:
        import fitz
        
        doc = fitz.open(input_path)
        original_size = os.path.getsize(input_path) / 1024
        
        doc.save(output_path, garbage=4, deflate=True, clean=True)
        doc.close()
        
        new_size = os.path.getsize(output_path) / 1024
        reduction = (1 - new_size / original_size) * 100
        
        if reduction > 0:
            logger.debug(f"PDF compresso: {original_size:.2f} KB -> {new_size:.2f} KB ({reduction:.1f}% ridotto)")
        
        return True
    
    except Exception as e:
        logger.warning(f"Errore compressione PDF: {e}")
        return False

def is_pdf_identical(pdf_path, data_hash):
    """
    Verifica se un PDF è identico a uno generato con gli stessi dati
    (Usa hash del contenuto)
    """
    try:
        with open(pdf_path, 'rb') as f:
            file_hash = hash(f.read())
        return file_hash == data_hash
    except:
        return False

def get_temp_dir_size_mb():
    """
    Calcola la dimensione totale della cartella temp_pdfs
    """
    temp_dir = get_path('temp_pdfs')
    if not os.path.exists(temp_dir):
        return 0
    
    total_size = 0
    try:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(filepath)
                except:
                    pass
    except:
        pass
    
    return total_size / (1024 * 1024)

def ensure_temp_dir():
    """
    Assicura che la cartella temp_pdfs esista
    """
    temp_dir = get_path('temp_pdfs')
    os.makedirs(temp_dir, exist_ok=True)

def flatten_pdf_fields(input_path, output_path=None):
    """
    Appiattisce i campi modulo di un PDF, trasformandoli in testo statico
    Renderizza i valori compilati come testo permanente prima di rimuovere i widget
    
    Args:
        input_path: Percorso del PDF con campi compilati
        output_path: Percorso output (default: sovrascrivi input)
    
    Returns:
        True se appiattimento riuscito, False altrimenti
    """
    if output_path is None:
        output_path = input_path
    
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(input_path)
        total_widgets = 0
        total_rendered = 0
        
        for page_num, page in enumerate(doc):
            annots = page.annots()
            if annots:
                widgets_data = []
                for annot in annots:
                    try:
                        if annot.type[0] == 10:  # Type 10 = Widget
                            total_widgets += 1
                            annot_obj = annot.this_dict
                            value_text = None
                            
                            logger.debug(f"Widget trovato: {annot_obj}")
                            
                            if "/V" in annot_obj:
                                value_text = str(annot_obj["/V"]).strip("()")
                                logger.debug(f"Valore trovato: {value_text}")
                            
                            rect = annot.rect
                            
                            if value_text and rect:
                                widgets_data.append((annot, value_text, rect))
                            else:
                                widgets_data.append((annot, None, None))
                    except Exception as annot_err:
                        logger.debug(f"Errore elaborazione widget: {annot_err}")
                
                # Rimuovi i widget PRIMA di renderizzare il testo
                for widget, _, _ in widgets_data:
                    try:
                        page.delete_annot(widget)
                    except:
                        pass
                
                # Renderizza il testo DOPO aver rimosso i widget
                for widget, value_text, rect in widgets_data:
                    if value_text and rect:
                        try:
                            x0, y0, x1, y1 = rect
                            font_size = 15
                            text_height = font_size * 0.75
                            y_pos = y0 + (y1 - y0 - text_height) / 2 + text_height
                            
                            page.insert_text(
                                (x0 + 2, y_pos),
                                value_text,
                                fontsize=font_size,
                                color=(0, 0, 0),
                                fontname="helv"
                            )
                            total_rendered += 1
                            logger.debug(f"Widget renderizzato: {value_text} a rect={rect}")
                        except Exception as text_err:
                            logger.debug(f"Errore renderizzazione testo: {text_err}")
        
        logger.info(f"Widget trovati: {total_widgets}, Renderizzati: {total_rendered}")
        
        # Salva il PDF appiattito senza AcroForm
        doc.save(output_path, garbage=4, deflate=True, clean=True)
        doc.close()
        
        # Pulizia aggiuntiva con pypdf per rimuovere completamente AcroForm
        try:
            from pypdf import PdfReader, PdfWriter
            
            reader = PdfReader(output_path)
            writer = PdfWriter(clone_from=reader)
            
            if hasattr(writer, 'Root') and hasattr(writer.Root, 'AcroForm'):
                try:
                    writer.Root.AcroForm = None
                except:
                    pass
            
            with open(output_path, 'wb') as f:
                writer.write(f)
        except Exception as e:
            logger.debug(f"Pulizia AcroForm fallita: {e}")
        
        logger.info(f"PDF appiattito - valori renderizzati e campi rimossi")
        return True
        
    except Exception as e:
        logger.warning(f"Errore appiattimento PDF con PyMuPDF: {e}")
        
        # Fallback: semplicemente disabilita i campi mantenendo AcroForm
        try:
            from pypdf import PdfReader, PdfWriter
            
            reader = PdfReader(input_path)
            writer = PdfWriter(clone_from=reader)
            
            try:
                if reader.Root.AcroForm and reader.Root.AcroForm["/Fields"]:
                    for field in reader.Root.AcroForm["/Fields"]:
                        field_obj = field.get_object()
                        if "/Ff" not in field_obj:
                            from pypdf.generic import NumberObject
                            field_obj["/Ff"] = NumberObject(1)
            except:
                pass
            
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            logger.info(f"PDF salvato con campi disabilitati (fallback)")
            return True
            
        except Exception as e2:
            logger.error(f"Errore appiattimento PDF: {e2}")
            return False
