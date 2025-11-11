function showAddOperazioneModal() {
    document.getElementById('addOperazioneModal').style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}

function toggleMesiValidi(checkbox) {
    const mesiGroup = document.getElementById('mesiValidiGroup');
    if (checkbox.checked) {
        mesiGroup.style.display = 'none';
        // Deseleziona tutti i mesi
        document.querySelectorAll('.mese-checkbox').forEach(cb => cb.checked = false);
    } else {
        mesiGroup.style.display = 'block';
    }
}

function toggleMesiValidiEdit(checkbox) {
    const mesiGroup = document.getElementById('mesiValidiEditGroup');
    if (checkbox.checked) {
        mesiGroup.style.display = 'none';
        // Deseleziona tutti i mesi
        document.querySelectorAll('.mese-checkbox-edit').forEach(cb => cb.checked = false);
    } else {
        mesiGroup.style.display = 'block';
    }
}

document.getElementById('addOperazioneForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const titolo = document.getElementById('newTitolo').value;
    const descrizione = document.getElementById('newDescrizione').value;
    const cdl = document.getElementById('newCdl').value;
    const flotta_id = document.getElementById('newFlotta').value;
    const sempreVisibile = document.getElementById('newSempreVisibile').checked;

    let mesi_validi = [];
    if (!sempreVisibile) {
        document.querySelectorAll('.mese-checkbox:checked').forEach(cb => {
            mesi_validi.push(parseInt(cb.value));
        });
    }

    try {
        const response = await fetch('/api/admin/operazioni-globali', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ titolo, descrizione, cdl, flotta_id, mesi_validi })
        });
        const result = await response.json();
        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
});

function editOperazione(id, titolo, descrizione, cdl, mesiValidi, flottaId) {
    document.getElementById('editId').value = id;
    document.getElementById('editTitolo').value = titolo;
    document.getElementById('editDescrizione').value = descrizione;
    document.getElementById('editCdl').value = cdl;
    document.getElementById('editFlotta').value = flottaId || '';

    // Gestisci checkbox "sempre visibile"
    const sempreVisibile = !mesiValidi || mesiValidi.length === 0;
    document.getElementById('editSempreVisibile').checked = sempreVisibile;

    const mesiGroup = document.getElementById('mesiValidiEditGroup');
    if (sempreVisibile) {
        mesiGroup.style.display = 'none';
    } else {
        mesiGroup.style.display = 'block';
        // Seleziona i mesi appropriati
        document.querySelectorAll('.mese-checkbox-edit').forEach(cb => {
            cb.checked = mesiValidi.includes(parseInt(cb.value));
        });
    }

    document.getElementById('editOperazioneModal').style.display = 'block';
}

document.getElementById('editOperazioneForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const id = document.getElementById('editId').value;
    const titolo = document.getElementById('editTitolo').value;
    const descrizione = document.getElementById('editDescrizione').value;
    const cdl = document.getElementById('editCdl').value;
    const flotta_id = document.getElementById('editFlotta').value;
    const sempreVisibile = document.getElementById('editSempreVisibile').checked;

    let mesi_validi = [];
    if (!sempreVisibile) {
        document.querySelectorAll('.mese-checkbox-edit:checked').forEach(cb => {
            mesi_validi.push(parseInt(cb.value));
        });
    }

    try {
        const response = await fetch(`/api/admin/operazioni-globali/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ titolo, descrizione, cdl, flotta_id, mesi_validi })
        });
        const result = await response.json();
        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
});

async function deleteOperazione(id) {
    if (!confirm('Sei sicuro di voler eliminare questa operazione globale?')) return;

    try {
        const response = await fetch(`/api/admin/operazioni-globali/${id}`, {
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
