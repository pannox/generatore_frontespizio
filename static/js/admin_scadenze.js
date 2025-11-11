function showAddScadenzaModal() {
    document.getElementById('addScadenzaModal').style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}

document.getElementById('addScadenzaForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const nome = document.getElementById('newScadenzaNome').value;
    const descrizione = document.getElementById('newScadenzaDescrizione').value;
    const rilevazione_quote = document.getElementById('newRilevazioneQuote').checked;

    try {
        const response = await fetch(`/api/admin/scadenze/${flottaId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nome, descrizione, rilevazione_quote })
        });
        const result = await response.json();
        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
});

function editScadenza(id, nome, descrizione, rilevazioneQuote = 'false') {
    document.getElementById('editScadenzaId').value = id;
    document.getElementById('editScadenzaNome').value = nome;
    document.getElementById('editScadenzaDescrizione').value = descrizione;
    // Converte la stringa JSON in booleano
    const rilevazioneQuoteBool = JSON.parse(rilevazioneQuote);
    document.getElementById('editRilevazioneQuote').checked = rilevazioneQuoteBool;
    document.getElementById('editScadenzaModal').style.display = 'block';
}

document.getElementById('editScadenzaForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const id = document.getElementById('editScadenzaId').value;
    const nome = document.getElementById('editScadenzaNome').value;
    const descrizione = document.getElementById('editScadenzaDescrizione').value;
    const rilevazione_quote = document.getElementById('editRilevazioneQuote').checked;

    try {
        const response = await fetch(`/api/admin/scadenze/${flottaId}/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nome, descrizione, rilevazione_quote })
        });
        const result = await response.json();
        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
});

async function deleteScadenza(id) {
    try {
        const response = await fetch(`/api/admin/scadenze/${flottaId}/${id}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
}

// Drag and Drop per riordinare le scadenze
let draggedElement = null;

document.querySelectorAll('.draggable-row').forEach(row => {
    row.addEventListener('dragstart', function(e) {
        draggedElement = this;
        this.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
    });

    row.addEventListener('dragend', function() {
        this.classList.remove('dragging');
        document.querySelectorAll('.draggable-row').forEach(r => r.classList.remove('drag-over'));
    });

    row.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';

        if (draggedElement !== this) {
            this.classList.add('drag-over');
        }
    });

    row.addEventListener('dragleave', function() {
        this.classList.remove('drag-over');
    });

    row.addEventListener('drop', async function(e) {
        e.preventDefault();
        this.classList.remove('drag-over');

        if (draggedElement !== this) {
            const fromId = draggedElement.getAttribute('data-id');
            const toId = this.getAttribute('data-id');

            try {
                const response = await fetch(`/api/admin/scadenze/${flottaId}/reorder`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ fromId, toId })
                });

                const result = await response.json();

                if (result.success) {
                    location.reload();
                }
            } catch (error) {
                console.error(error);
            }
        }
    });
});
