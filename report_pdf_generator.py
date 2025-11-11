from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
import os
import re


def clean_text(text):
    """
    Pulisce il testo da caratteri speciali che causano problemi nel PDF
    """
    if not text:
        return ""
    
    # Converti in stringa se non lo è già
    text = str(text)
    
    # Rimuovi caratteri di controllo e caratteri non stampabili
    # Mantieni solo caratteri ASCII stampabili e alcuni caratteri speciali comuni
    cleaned = re.sub(r'[^\x20-\x7E\xC0-\xFF]', '', text)
    
    # Rimuovi caratteri che potrebbero causare problemi in ReportLab
    cleaned = cleaned.replace('\x00', '')  # Null byte
    cleaned = cleaned.replace('\ufffd', '')  # Replacement character
    
    # Sostituisci caratteri problematici con equivalenti sicuri
    cleaned = cleaned.replace('…', '...')
    cleaned = cleaned.replace('"', '"').replace('"', '"')
    cleaned = cleaned.replace(''', "'").replace(''', "'")
    
    return cleaned.strip()


def generate_report_pdf(report_data):
    """
    Genera un PDF semplice con tabelle del report

    Args:
        report_data: Dizionario con i dati del report

    Returns:
        Path del file PDF generato
    """

    # Crea il nome del file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_frontespizio_{timestamp}.pdf"
    filepath = os.path.join('temp_pdfs', filename)

    # Assicurati che la cartella esista
    os.makedirs('temp_pdfs', exist_ok=True)

    # Crea il documento in landscape per più spazio
    pdf_doc = SimpleDocTemplate(filepath, pagesize=landscape(A4),
                           rightMargin=1.5*cm, leftMargin=1.5*cm,
                           topMargin=1.5*cm, bottomMargin=1.5*cm)

    # Stili
    styles = getSampleStyleSheet()
    elements = []

    # Titolo
    title = Paragraph("<b>REPORT FRONTESPIZIO TRENI</b>", styles['Title'])
    elements.append(title)

    date_text = Paragraph(
        f"Generato il: {datetime.now().strftime('%d/%m/%Y alle %H:%M')}",
        styles['Normal']
    )
    elements.append(date_text)
    elements.append(Spacer(1, 0.5*cm))

    # Statistiche generali
    stats_data = [
        ['STATISTICHE GENERALI'],
        ['Totale Flotte', 'Totale Scadenze', 'Totale Documenti', 'Totale Operazioni'],
        [
            str(report_data['totale_flotte']),
            str(report_data['totale_scadenze']),
            str(report_data['totale_documenti']),
            str(report_data['totale_operazioni'])
        ]
    ]

    stats_table = Table(stats_data, colWidths=[6.5*cm, 6.5*cm, 6.5*cm, 6.5*cm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('SPAN', (0, 0), (-1, 0)),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, 1), colors.lightgrey),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(stats_table)
    elements.append(Spacer(1, 1*cm))
    
    # Sezione 1: Lista completa documenti per flotta
    elements.append(PageBreak())
    doc_title = Paragraph("<b>LISTA COMPLETA DOCUMENTI PER FLOTTA</b>", styles['Heading2'])
    elements.append(doc_title)
    elements.append(Spacer(1, 0.5*cm))
    
    # Controlla se ci sono flotte con documenti
    flotte_con_documenti = False
    
    for flotta in report_data['flotte']:
        # Raccogli tutti i documenti della flotta
        tutti_documenti = []
        for scadenza in flotta['scadenze']:
            for doc in scadenza['documenti']:
                tutti_documenti.append({
                    'nome': clean_text(doc['nome']),
                    'scadenza': clean_text(scadenza['nome'])
                })
        
        # Mostra la flotta solo se ha documenti
        if tutti_documenti:
            flotte_con_documenti = True
            flotta_subtitle = Paragraph(f"<b>Flotta: {flotta['nome']}</b>", styles['Heading3'])
            elements.append(flotta_subtitle)
            elements.append(Spacer(1, 0.3*cm))
            
            doc_data = [['Nome Documento', 'Scadenza']]
            for doc in tutti_documenti:
                doc_data.append([doc['nome'], doc['scadenza']])
            
            doc_table = Table(doc_data, colWidths=[20*cm, 6.7*cm])
            doc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(doc_table)
            elements.append(Spacer(1, 0.8*cm))
    
    # Se nessuna flotta ha documenti, mostra messaggio
    if not flotte_con_documenti:
        no_docs = Paragraph("Nessuna flotta contiene documenti.", styles['Normal'])
        elements.append(no_docs)
        elements.append(Spacer(1, 0.8*cm))
    
    # Sezione 2: Lista completa operazioni per flotta
    elements.append(PageBreak())
    op_title = Paragraph("<b>LISTA COMPLETA OPERAZIONI AGGIUNTIVE PER FLOTTA</b>", styles['Heading2'])
    elements.append(op_title)
    elements.append(Spacer(1, 0.5*cm))
    
    # Controlla se ci sono flotte con operazioni
    flotte_con_operazioni = False
    
    for flotta in report_data['flotte']:
        # Raccogli tutte le operazioni della flotta
        tutte_operazioni = []
        for scadenza in flotta['scadenze']:
            for op in scadenza['operazioni']:
                tutte_operazioni.append({
                    'titolo': clean_text(op.get('titolo', op)),
                    'descrizione': clean_text(op.get('descrizione', '')),
                    'cdl': clean_text(op.get('cdl', '')),
                    'scadenza': clean_text(scadenza['nome'])
                })
        
        # Mostra la flotta solo se ha operazioni aggiuntive
        if tutte_operazioni:
            flotte_con_operazioni = True
            flotta_subtitle = Paragraph(f"<b>Flotta: {flotta['nome']}</b>", styles['Heading3'])
            elements.append(flotta_subtitle)
            elements.append(Spacer(1, 0.3*cm))
            
            op_data = [['Titolo', 'Descrizione', 'CDL', 'Scadenza']]
            for op in tutte_operazioni:
                try:
                    # Usa Paragraph per titolo e descrizione per forzare l'andata a capo
                    titolo_paragraph = Paragraph(op['titolo'] or '-', styles['Normal'])
                    descrizione_paragraph = Paragraph(op['descrizione'] or '-', styles['Normal'])
                    scadenza_paragraph = Paragraph(op['scadenza'] or '-', styles['Normal'])
                    op_data.append([titolo_paragraph, descrizione_paragraph, op['cdl'] or '-', scadenza_paragraph])
                except Exception as e:
                    print(f"Errore nell'elaborazione operazione: {e}, dati: {op}")
                    # Aggiungi una riga di errore invece di fallire tutto
                    op_data.append(['Errore', 'Errore nell\'elaborazione', '-', '-'])
            
            op_table = Table(op_data, colWidths=[5*cm, 15*cm, 3*cm, 3.7*cm])
            op_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            
            elements.append(op_table)
            elements.append(Spacer(1, 0.8*cm))
    
    # Se nessuna flotta ha operazioni, mostra messaggio
    if not flotte_con_operazioni:
        no_ops = Paragraph("Nessuna flotta contiene operazioni aggiuntive.", styles['Normal'])
        elements.append(no_ops)
        elements.append(Spacer(1, 0.8*cm))

    # Operazioni Globali
    if report_data.get('operazioni_globali'):
        elements.append(PageBreak())
        global_title = Paragraph("<b>OPERAZIONI GLOBALI</b>", styles['Heading2'])
        elements.append(global_title)
        elements.append(Spacer(1, 0.3*cm))

        global_data = [['Flotta', 'Titolo', 'Descrizione', 'CDL', 'Mesi']]
        for op in report_data['operazioni_globali']:
            # Usa Paragraph per titolo e descrizione per forzare l'andata a capo
            titolo_clean = clean_text(op['titolo'])
            titolo_paragraph = Paragraph(titolo_clean, styles['Normal'])
            descrizione_text = clean_text(op.get('descrizione', '-'))
            descrizione_paragraph = Paragraph(descrizione_text, styles['Normal'])
            
            cdl = clean_text(op.get('cdl', '-'))
            flotta_spec = clean_text(op.get('flotta_nome', 'Tutte'))
            mesi = f"{len(op.get('mesi_validi', []))} mesi" if op.get('mesi_validi') else 'Sempre'
            global_data.append([flotta_spec, titolo_paragraph, descrizione_paragraph, cdl, mesi])

        global_table = Table(global_data, colWidths=[4*cm, 5*cm, 10*cm, 4*cm, 3.7*cm])
        global_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        elements.append(global_table)

    # Genera il PDF
    try:
        pdf_doc.build(elements)
        return filepath
    except Exception as e:
        print(f"Errore nella generazione del PDF: {e}")
        raise
