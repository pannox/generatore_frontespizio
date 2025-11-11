import os
from io import BytesIO
from PIL import Image
import base64
import hashlib
import fitz  # PyMuPDF
from datetime import datetime

class ThumbnailService:
    def __init__(self, cache_dir='thumbnails'):
        self.cache_dir = cache_dir
        self.ensure_cache_dir()
    
    def ensure_cache_dir(self):
        """Crea la directory cache se non esiste"""
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_cache_path(self, pdf_path):
        """Genera percorso cache basato su hash del file"""
        # Usa hash del contenuto file per cache univoco
        try:
            with open(pdf_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:12]
        except:
            # Fallback: usa nome file + timestamp
            file_hash = hashlib.md5(pdf_path.encode()).hexdigest()[:12]
        
        cache_filename = f"thumb_{file_hash}.png"
        return os.path.join(self.cache_dir, cache_filename)
    
    def generate_thumbnail(self, pdf_path, page_num=0, size=(200, 150)):
        """
        Genera thumbnail per una pagina PDF
        
        Args:
            pdf_path: Percorso del file PDF
            page_num: Numero pagina (default 0 = prima pagina)
            size: Dimensione thumbnail (width, height)
            
        Returns:
            Percorso file thumbnail o None se errore
        """
        try:
            # Check cache first
            cache_path = self.get_cache_path(pdf_path)
            if os.path.exists(cache_path):
                # Check se il thumbnail è più recente del PDF
                pdf_mtime = os.path.getmtime(pdf_path)
                thumb_mtime = os.path.getmtime(cache_path)
                if thumb_mtime > pdf_mtime:
                    return cache_path
            
            # Verifica che il PDF esista
            if not os.path.exists(pdf_path):
                print(f"PDF non trovato: {pdf_path}")
                return None

            # Apri PDF con PyMuPDF
            doc = fitz.open(pdf_path)
            if page_num >= len(doc):
                print(f"Pagina {page_num} non trovata in {pdf_path}")
                doc.close()
                return None
            
            # Estrai pagina
            page = doc[page_num]
            
            # Render pagina come immagine (zoom 2x per qualità migliore)
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            
            # Converti in PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(BytesIO(img_data))
            
            # Ridimensiona mantenendo aspect ratio
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Salva in cache
            img.save(cache_path, "PNG", optimize=True)
            doc.close()
            
            print(f"Thumbnail generato: {cache_path}")
            return cache_path
            
        except Exception as e:
            print(f"Errore generazione thumbnail per {pdf_path}: {e}")
            return None
    
    def get_thumbnail_base64(self, pdf_path, page_num=0, size=(200, 150)):
        """
        Ottieni thumbnail come base64 per embedding diretto
        
        Returns:
            Stringa base64 o None se errore
        """
        try:
            thumbnail_path = self.generate_thumbnail(pdf_path, page_num, size)
            if thumbnail_path and os.path.exists(thumbnail_path):
                with open(thumbnail_path, 'rb') as f:
                    img_data = f.read()
                return base64.b64encode(img_data).decode('utf-8')
            return None
        except Exception as e:
            print(f"Errore conversione base64: {e}")
            return None
    
    def cleanup_old_thumbnails(self, max_age_days=30):
        """Rimuovi thumbnail vecchi dalla cache"""
        try:
            current_time = datetime.now().timestamp()
            max_age_seconds = max_age_days * 24 * 3600
            
            removed = 0
            for filename in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        removed += 1
            
            print(f"Cleanup: rimosse {removed} thumbnail vecchi")
            return removed
        except Exception as e:
            print(f"Errore cleanup thumbnail: {e}")
            return 0
    
    def get_cache_stats(self):
        """Ottieni statistiche sulla cache"""
        try:
            if not os.path.exists(self.cache_dir):
                return {'total_files': 0, 'total_size_mb': 0}
            
            files = [f for f in os.listdir(self.cache_dir) if f.endswith('.png')]
            total_size = sum(os.path.getsize(os.path.join(self.cache_dir, f)) for f in files)
            
            return {
                'total_files': len(files),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'cache_dir': self.cache_dir
            }
        except Exception as e:
            print(f"Errore statistiche cache: {e}")
            return {'total_files': 0, 'total_size_mb': 0}

# Istanza globale del servizio
thumbnail_service = ThumbnailService()

def get_pdf_thumbnail(pdf_path, page_num=0, size=(200, 150)):
    """Funzione comoda per ottenere thumbnail"""
    return thumbnail_service.get_thumbnail_base64(pdf_path, page_num, size)

def generate_pdf_thumbnail(pdf_path, page_num=0, size=(200, 150)):
    """Funzione comoda per generare thumbnail e ottenere percorso"""
    return thumbnail_service.generate_thumbnail(pdf_path, page_num, size)
