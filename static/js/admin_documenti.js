function showAddDocumentoModal() {
    if (currentDocCount >= maxDocumenti) {
        return;
    }
    
    // Carica PDF disponibili
    loadAvailablePDFsForAdd();
    
    // Resetta checkbox e campi
    document.getElementById('senzaPdf').checked = false;
    document.getElementById('pdfFieldGroup').style.display = 'block';
    document.getElementById('newDocumentoPDF').required = true;
    document.getElementById('newDocumentoNome').value = '';
    
    document.getElementById('addDocumentoModal').style.display = 'block';
}

function togglePdfField() {
    const senzaPdf = document.getElementById('senzaPdf').checked;
    const pdfFieldGroup = document.getElementById('pdfFieldGroup');
    const pdfInput = document.getElementById('newDocumentoPDF');
    
    if (senzaPdf) {
        pdfFieldGroup.style.display = 'none';
        pdfInput.required = false;
        pdfInput.value = ''; // Svuota il file selezionato
    } else {
        pdfFieldGroup.style.display = 'block';
        pdfInput.required = true;
    }
}

function switchAddTab(tabName) {
    // Nascondi tutte le tab
    document.querySelectorAll('#addDocumentoModal .tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Rimuovi active da tutti i pulsanti
    document.querySelectorAll('#addDocumentoModal .tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Mostra la tab selezionata
    if (tabName === 'upload') {
        document.getElementById('addUploadTab').classList.add('active');
        document.querySelectorAll('#addDocumentoModal .tab-btn')[0].classList.add('active');
    } else {
        document.getElementById('addSelectTab').classList.add('active');
        document.querySelectorAll('#addDocumentoModal .tab-btn')[1].classList.add('active');
    }
}

async function loadAvailablePDFsForAdd() {
    try {
        const response = await fetch('/api/available_pdfs');
        const result = await response.json();
        
        const select = document.getElementById('addExistingPDFSelect');
        select.innerHTML = '<option value="">-- Seleziona PDF --</option>';
        
        if (result.success && result.pdfs.length > 0) {
            result.pdfs.forEach(pdf => {
                const option = document.createElement('option');
                option.value = pdf.path;
                option.textContent = `${pdf.filename} (${pdf.size_mb} MB)`;
                select.appendChild(option);
            });
        } else {
            select.innerHTML = '<option value="">-- Nessun PDF disponibile --</option>';
        }
    } catch (error) {
        console.error('Errore caricamento PDF:', error);
        document.getElementById('addExistingPDFSelect').innerHTML = '<option value="">-- Errore caricamento --</option>';
    }
}

async function refreshPDFsForAdd() {
    const select = document.getElementById('addExistingPDFSelect');
    const originalHTML = select.innerHTML;
    
    // Mostra stato di caricamento
    select.innerHTML = '<option value="">-- Aggiornamento in corso... --</option>';
    
    try {
        const response = await fetch('/api/refresh_pdfs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            select.innerHTML = '<option value="">-- Seleziona PDF --</option>';
            
            result.pdfs.forEach(pdf => {
                const option = document.createElement('option');
                option.value = pdf.path;
                option.textContent = `${pdf.filename} (${pdf.size_mb} MB)`;
                select.appendChild(option);
            });
            
            // Mostra messaggio di successo
            console.log(`✅ ${result.message}`);
        } else {
            select.innerHTML = '<option value="">-- Errore refresh --</option>';
            console.error('❌ Errore: ' + result.error);
        }
    } catch (error) {
        console.error('Errore refresh PDF:', error);
        select.innerHTML = originalHTML;
        console.error('❌ Errore durante l\'aggiornamento dei PDF');
    }
}

// Mostra info PDF quando selezionato nel modal aggiungi
document.getElementById('addExistingPDFSelect').addEventListener('change', function(e) {
    const selectedOption = e.target.options[e.target.selectedIndex];
    const pdfInfo = document.getElementById('addPdfInfo');
    const pdfDetails = document.getElementById('addPdfDetails');
    
    if (e.target.value) {
        const text = selectedOption.textContent;
        pdfDetails.textContent = text;
        pdfInfo.style.display = 'block';
        
        // Auto-compila il nome con il filename
        const filename = selectedOption.textContent.split(' (')[0];
        document.getElementById('addSelectDocumentoNome').value = filename;
    } else {
        pdfInfo.style.display = 'none';
        document.getElementById('addSelectDocumentoNome').value = '';
    }
});

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}

// Auto-compila nome documento dal file PDF
document.getElementById('newDocumentoPDF').addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) {
        // Rimuovi estensione .pdf e usa come nome
        const nomeFile = file.name.replace('.pdf', '');
        document.getElementById('newDocumentoNome').value = nomeFile;
    }
});

document.getElementById('addDocumentoForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const nome = document.getElementById('newDocumentoNome').value;
    const fileInput = document.getElementById('newDocumentoPDF');
    const file = fileInput.files[0];
    const senzaPdf = document.getElementById('senzaPdf').checked;

    if (!senzaPdf && !file) {
        console.warn('Seleziona un file PDF o spunta "Senza PDF"');
        return;
    }

    if (!nome) {
        console.warn('Inserisci un nome per il documento');
        return;
    }

    const formData = new FormData();
    formData.append('nome', nome);
    formData.append('obbligatorio', true);
    
    // Aggiungi PDF solo se non è "senza pdf"
    if (!senzaPdf && file) {
        formData.append('pdf', file);
    }

    // Aggiungi strumento se presente
    const strumentoSelect = document.getElementById('newDocumentoStrumento');
    if (strumentoSelect) {
        formData.append('strumento', strumentoSelect.value);
    }

    try {
        const response = await fetch(`/api/admin/documenti/${flottaId}/${scadenzaId}`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
});

function editDocumento(id, nome) {
    document.getElementById('editDocumentoId').value = id;
    document.getElementById('editDocumentoNome').value = nome;
    document.getElementById('editDocumentoModal').style.display = 'block';
}

document.getElementById('editDocumentoForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const id = document.getElementById('editDocumentoId').value;
    const nome = document.getElementById('editDocumentoNome').value;

    try {
        const response = await fetch(`/api/admin/documenti/${flottaId}/${scadenzaId}/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nome, obbligatorio: true }) // Tutti i documenti sono obbligatori
        });
        const result = await response.json();
        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
});

async function deleteDocumento(id) {
    try {
        const response = await fetch(`/api/admin/documenti/${flottaId}/${scadenzaId}/${id}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
}

function uploadPDF(docId) {
    document.getElementById('uploadDocumentoId').value = docId;
    document.getElementById('selectDocumentoId').value = docId;
    
    // Carica PDF disponibili
    loadAvailablePDFs();
    
    // Resetta le tab alla prima
    switchTab('upload');
    
    document.getElementById('uploadPDFModal').style.display = 'block';
}

function switchTab(tabName) {
    // Nascondi tutte le tab
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Rimuovi active da tutti i pulsanti
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Mostra la tab selezionata
    if (tabName === 'upload') {
        document.getElementById('uploadTab').classList.add('active');
        document.querySelectorAll('.tab-btn')[0].classList.add('active');
    } else {
        document.getElementById('selectTab').classList.add('active');
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
    }
}

async function loadAvailablePDFs() {
    try {
        const response = await fetch('/api/available_pdfs');
        const result = await response.json();
        
        const select = document.getElementById('existingPDFSelect');
        select.innerHTML = '<option value="">-- Seleziona PDF --</option>';
        
        if (result.success && result.pdfs.length > 0) {
            result.pdfs.forEach(pdf => {
                const option = document.createElement('option');
                option.value = pdf.path;
                option.textContent = `${pdf.filename} (${pdf.size_mb} MB)`;
                select.appendChild(option);
            });
        } else {
            select.innerHTML = '<option value="">-- Nessun PDF disponibile --</option>';
        }
    } catch (error) {
        console.error('Errore caricamento PDF:', error);
        document.getElementById('existingPDFSelect').innerHTML = '<option value="">-- Errore caricamento --</option>';
    }
}

async function refreshPDFs() {
    const select = document.getElementById('existingPDFSelect');
    const originalHTML = select.innerHTML;
    
    // Mostra stato di caricamento
    select.innerHTML = '<option value="">-- Aggiornamento in corso... --</option>';
    
    try {
        const response = await fetch('/api/refresh_pdfs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            select.innerHTML = '<option value="">-- Seleziona PDF --</option>';
            
            result.pdfs.forEach(pdf => {
                const option = document.createElement('option');
                option.value = pdf.path;
                option.textContent = `${pdf.filename} (${pdf.size_mb} MB)`;
                select.appendChild(option);
            });
            
            // Mostra messaggio di successo
            console.log(`✅ ${result.message}`);
        } else {
            select.innerHTML = '<option value="">-- Errore refresh --</option>';
            console.error('❌ Errore: ' + result.error);
        }
    } catch (error) {
        console.error('Errore refresh PDF:', error);
        select.innerHTML = originalHTML;
        console.error('❌ Errore durante l\'aggiornamento dei PDF');
    }
}

// Mostra info PDF quando selezionato
document.getElementById('existingPDFSelect').addEventListener('change', function(e) {
    const selectedOption = e.target.options[e.target.selectedIndex];
    const pdfInfo = document.getElementById('pdfInfo');
    const pdfDetails = document.getElementById('pdfDetails');
    
    if (e.target.value) {
        const text = selectedOption.textContent;
        pdfDetails.textContent = text;
        pdfInfo.style.display = 'block';
    } else {
        pdfInfo.style.display = 'none';
    }
});

document.getElementById('uploadPDFForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const docId = document.getElementById('uploadDocumentoId').value;
    const fileInput = document.getElementById('pdfFile');
    const file = fileInput.files[0];

    if (!file) return;

    const formData = new FormData();
    formData.append('pdf', file);

    try {
        const response = await fetch(`/api/upload_pdf/${flottaId}/${scadenzaId}/${docId}`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        if (result.success) {
            // Mostra messaggio di stato (linked/uploaded)
            if (result.status === 'linked') {
                console.log('✅ ' + result.message);
            } else {
                console.log('✅ ' + result.message);
            }
            location.reload();
        } else {
            console.error('❌ Errore: ' + result.error);
        }
    } catch (error) {
        console.error(error);
        console.error('❌ Errore durante il caricamento del PDF');
    }
});

// Gestore per il form di selezione PDF
document.getElementById('selectPDFForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const docId = document.getElementById('selectDocumentoId').value;
    const pdfPath = document.getElementById('existingPDFSelect').value;

    if (!pdfPath) {
        console.warn('Seleziona un PDF dalla lista');
        return;
    }

    try {
        const response = await fetch(`/api/link_pdf/${flottaId}/${scadenzaId}/${docId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ pdf_path: pdfPath })
        });
        
        const result = await response.json();
        if (result.success) {
            console.log('✅ ' + result.message);
            location.reload();
        } else {
            console.error('❌ Errore: ' + result.error);
        }
    } catch (error) {
        console.error(error);
        console.error('❌ Errore durante il collegamento del PDF');
    }
});

// Gestore per il form di aggiunta con PDF esistente
document.getElementById('addSelectDocumentoForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const nome = document.getElementById('addSelectDocumentoNome').value;
    const pdfPath = document.getElementById('addExistingPDFSelect').value;
    const fileInput = document.getElementById('newDocumentoPDF');

    if (!pdfPath) {
        console.warn('Seleziona un PDF dalla lista');
        return;
    }

    if (!nome) {
        console.warn('Inserisci un nome per il documento');
        return;
    }

    const formData = new FormData();
    formData.append('nome', nome);
    formData.append('obbligatorio', true);
    formData.append('pdf_path', pdfPath); // Passiamo il path invece del file

    // Aggiungi strumento se presente
    const strumentoSelect = document.getElementById('addSelectDocumentoStrumento');
    if (strumentoSelect) {
        formData.append('strumento', strumentoSelect.value);
    }

    try {
        const response = await fetch(`/api/admin/documenti/${flottaId}/${scadenzaId}`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        if (result.success) {
            console.log('✅ Documento aggiunto con PDF esistente: ' + nome);
            location.reload();
        } else {
            console.error('❌ Errore: ' + result.error);
        }
    } catch (error) {
        console.error(error);
        console.error('❌ Errore durante l\'aggiunta del documento');
    }
});

// Drag and Drop per riordinare documenti
let draggedRow = null;

document.addEventListener('DOMContentLoaded', function() {
    const table = document.getElementById('documentiTable');
    if (!table) return;

    table.addEventListener('dragstart', function(e) {
        if (e.target.classList.contains('draggable-row')) {
            draggedRow = e.target;
            e.target.classList.add('dragging');
        }
    });

    table.addEventListener('dragend', function(e) {
        if (e.target.classList.contains('draggable-row')) {
            e.target.classList.remove('dragging');
            e.target.classList.remove('drag-over');
        }
    });

    table.addEventListener('dragover', function(e) {
        e.preventDefault();
        const afterElement = getDragAfterElement(table, e.clientY);
        const dragging = document.querySelector('.dragging');
        
        if (afterElement == null) {
            table.appendChild(dragging);
        } else {
            table.insertBefore(dragging, afterElement);
        }
    });

    table.addEventListener('drop', async function(e) {
        e.preventDefault();
        
        // Ottieni il nuovo ordine
        const rows = Array.from(table.querySelectorAll('tr[data-id]'));
        const newOrder = rows.map(row => row.getAttribute('data-id'));
        
        // Invia al server
        try {
            const response = await fetch(`/api/admin/documenti/${flottaId}/${scadenzaId}/reorder`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ order: newOrder })
            });
            
            const result = await response.json();
            if (result.success) {
                // Aggiorna i numeri di riga
                rows.forEach((row, index) => {
                    row.querySelector('td:first-child').textContent = index + 1;
                });
            } else {
                console.error('Errore nel salvataggio dell\'ordine');
                location.reload();
            }
        } catch (error) {
            console.error('Errore:', error);
            console.error('Errore nel salvataggio dell\'ordine');
            location.reload();
        }
    });
});

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.draggable-row:not(.dragging)')];
    
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}
