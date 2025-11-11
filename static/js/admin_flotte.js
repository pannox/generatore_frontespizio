// Gestione Modal
function showAddFlottaModal() {
    document.getElementById('addFlottaModal').style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Click outside modal to close
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}

// Aggiungi Flotta
document.getElementById('addFlottaForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const nome = document.getElementById('newFlottaNome').value;
    const multioggetto = document.getElementById('newFlottaMultioggetto').checked;

    try {
        const response = await fetch('/api/admin/flotte', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nome, multioggetto })
        });

        const result = await response.json();

        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
});

// Modifica Flotta
function editFlotta(id, nome, multioggetto = 'false') {
    document.getElementById('editFlottaId').value = id;
    document.getElementById('editFlottaNome').value = nome;
    document.getElementById('editFlottaMultioggetto').checked = multioggetto === 'true';
    document.getElementById('editFlottaModal').style.display = 'block';
}

document.getElementById('editFlottaForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const id = document.getElementById('editFlottaId').value;
    const nome = document.getElementById('editFlottaNome').value;
    const multioggetto = document.getElementById('editFlottaMultioggetto').checked;

    try {
        const response = await fetch(`/api/admin/flotte/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nome, multioggetto })
        });

        const result = await response.json();

        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
});

// Elimina Flotta
async function deleteFlotta(id) {
    try {
        const response = await fetch(`/api/admin/flotte/${id}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
}

// Drag and Drop per riordinare le flotte
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
                const response = await fetch('/api/admin/flotte/reorder', {
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

// Upload Template Operazioni
function uploadTemplateOperazioni(flottaId) {
    document.getElementById('uploadTemplateFlottaId').value = flottaId;
    document.getElementById('uploadTemplateModal').style.display = 'block';
}

document.getElementById('uploadTemplateForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const flottaId = document.getElementById('uploadTemplateFlottaId').value;
    const fileInput = document.getElementById('templateOperazioniFile');
    const file = fileInput.files[0];

    if (!file) return;

    const formData = new FormData();
    formData.append('template', file);

    try {
        const response = await fetch(`/api/admin/flotte/${flottaId}/upload-template`, {
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
