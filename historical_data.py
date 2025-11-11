import json
import os
from datetime import datetime
from typing import List, Dict, Any

HISTORY_FILE = 'data/pdf_history.json'

def ensure_data_directory():
    """Assicura che la directory data esista"""
    os.makedirs('data', exist_ok=True)

def load_pdf_history() -> List[Dict[str, Any]]:
    """Carica lo storico delle generazioni PDF"""
    ensure_data_directory()
    
    if not os.path.exists(HISTORY_FILE):
        return []
    
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Errore nel caricamento storico: {e}")
        return []

def save_pdf_generation(data: Dict[str, Any]):
    """Salva una nuova generazione PDF nello storico"""
    ensure_data_directory()
    
    # Carica storico esistente
    history = load_pdf_history()
    
    # Aggiungi timestamp e ID
    generation_record = {
        'id': len(history) + 1,
        'timestamp': datetime.now().isoformat(),
        'date': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        **data
    }
    
    # Aggiungi allo storico
    history.append(generation_record)
    
    # Aggiorna contatore scadenze
    update_scadenze_counter(data.get('scadenze_ids', []))
    
    # Salva su file
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"✅ Storico salvato: {generation_record['id']} - {data.get('flotta_nome', 'N/A')}")
    except Exception as e:
        print(f"❌ Errore salvataggio storico: {e}")

def update_scadenze_counter(scadenze_ids: List[str]):
    """Aggiorna il contatore delle scadenze stampate"""
    ensure_data_directory()
    
    counter_file = 'data/scadenze_counter.json'
    
    # Carica contatore esistente
    if os.path.exists(counter_file):
        try:
            with open(counter_file, 'r', encoding='utf-8') as f:
                counter = json.load(f)
        except:
            counter = {}
    else:
        counter = {}
    
    # Incrementa contatore per ogni scadenza
    for scadenza_id in scadenze_ids:
        counter[scadenza_id] = counter.get(scadenza_id, 0) + 1
    
    # Salva contatore aggiornato
    try:
        with open(counter_file, 'w', encoding='utf-8') as f:
            json.dump(counter, f, ensure_ascii=False, indent=2)
        print(f"✅ Contatore scadenze aggiornato: {scadenze_ids}")
    except Exception as e:
        print(f"❌ Errore aggiornamento contatore: {e}")

def get_scadenze_counter() -> Dict[str, int]:
    """Ottieni il contatore delle scadenze stampate"""
    ensure_data_directory()
    
    counter_file = 'data/scadenze_counter.json'
    
    if os.path.exists(counter_file):
        try:
            with open(counter_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    return {}

def get_scadenze_counts_with_names(config) -> List[Dict[str, Any]]:
    """Ottieni conteggi per flotta (somma di tutte le scadenze)"""
    counter = get_scadenze_counter()
    flotte_counts = {}
    
    # Raggruppa conteggi per flotta
    for flotta in config.get('flotte', []):
        flotta_id = flotta.get('id', '')
        flotta_nome = flotta.get('nome', '')
        total_count = 0
        
        for scadenza in flotta.get('scadenze', []):
            scadenza_id = scadenza.get('id', '')
            count = counter.get(scadenza_id, 0)
            total_count += count
        
        if total_count > 0:  # Solo flotte con almeno una stampa
            flotte_counts[flotta_id] = {
                'flotta_nome': flotta_nome,
                'flotta_id': flotta_id,
                'conteggio': total_count
            }
    
    # Converti in lista e ordina per conteggio decrescente
    result = list(flotte_counts.values())
    result.sort(key=lambda x: x['conteggio'], reverse=True)
    return result

def get_filtered_history(filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Ottieni storico con filtri applicati"""
    history = load_pdf_history()
    
    if not filters:
        return history
    
    filtered = history.copy()
    
    # Filtro per flotta
    if filters.get('flotta'):
        filtered = [h for h in filtered if h.get('flotta_id') == filters['flotta']]
    
    # Filtro per strumento
    if filters.get('strumento'):
        filtered = [h for h in filtered if h.get('strumento') == filters['strumento']]
    
    # Filtro per data
    if filters.get('data_da'):
        data_da = datetime.fromisoformat(filters['data_da'])
        filtered = [h for h in filtered if datetime.fromisoformat(h['timestamp']) >= data_da]
    
    if filters.get('data_a'):
        data_a = datetime.fromisoformat(filters['data_a'])
        filtered = [h for h in filtered if datetime.fromisoformat(h['timestamp']) <= data_a]
    
    return sorted(filtered, key=lambda x: x['timestamp'], reverse=True)

def get_statistics() -> Dict[str, Any]:
    """Calcola statistiche sullo storico"""
    history = load_pdf_history()
    
    if not history:
        return {
            'totali': 0,
            'per_mese': {},
            'per_flotta': {},
            'per_strumento': {}
        }
    
    stats = {
        'totali': len(history),
        'per_mese': {},
        'per_flotta': {},
        'per_strumento': {}
    }
    
    for record in history:
        # Per mese
        mese = record['date'][:7]  # YYYY/MM
        stats['per_mese'][mese] = stats['per_mese'].get(mese, 0) + 1
        
        # Per flotta
        flotta = record.get('flotta_nome', 'Sconosciuta')
        stats['per_flotta'][flotta] = stats['per_flotta'].get(flotta, 0) + 1
        
        # Per strumento
        strumento = record.get('strumento', 'Sconosciuto')
        stats['per_strumento'][strumento] = stats['per_strumento'].get(strumento, 0) + 1
    
    return stats

def export_to_csv(filters: Dict[str, Any] = None) -> str:
    """Esporta lo storico in formato CSV"""
    import csv
    import io
    
    history = get_filtered_history(filters)
    
    if not history:
        return ""
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'ID', 'Data', 'Flotta', 'Scadenze', 'Strumento', 
        'Sede Tecnica', 'Numero Ordine', 'Nome File', 'Dimensione (KB)'
    ])
    
    # Data
    for record in history:
        writer.writerow([
            record.get('id', ''),
            record.get('date', ''),
            record.get('flotta_nome', ''),
            '; '.join(record.get('scadenze_nomi', [])),
            record.get('strumento', ''),
            record.get('sede_tecnica', ''),
            record.get('numero_ordine', ''),
            record.get('filename', ''),
            record.get('file_size_kb', '')
        ])
    
    return output.getvalue()
