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

// Toggle visibilità mesi per nuovo
document.getElementById('newValiditaSempre').addEventListener('change', function() {
    document.getElementById('newMesiContainer').style.display = this.checked ? 'none' : 'block';
});

// Toggle visibilità mesi per edit
document.getElementById('editValiditaSempre').addEventListener('change', function() {
    document.getElementById('editMesiContainer').style.display = this.checked ? 'none' : 'block';
});

document.getElementById('addOperazioneForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const titolo = document.getElementById('newOperazioneTitolo').value;
    const descrizione = document.getElementById('newOperazioneDescrizione').value;
    const cdl = document.getElementById('newOperazioneCDL').value;
    const sempre = document.getElementById('newValiditaSempre').checked;

    let mesiValidi = [];
    if (!sempre) {
        const checkboxes = document.querySelectorAll('input[name="newMesi"]:checked');
        mesiValidi = Array.from(checkboxes).map(cb => parseInt(cb.value));
    }

    try {
        const response = await fetch(`/api/admin/operazioni/${flottaId}/${scadenzaId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ titolo, descrizione, cdl, mesi_validi: mesiValidi })
        });
        const result = await response.json();
        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
});

function editOperazione(id, titolo, descrizione, cdl, mesiValidi = []) {
    document.getElementById('editOperazioneId').value = id;
    document.getElementById('editOperazioneTitolo').value = titolo;
    document.getElementById('editOperazioneDescrizione').value = descrizione;
    document.getElementById('editOperazioneCDL').value = cdl || '';

    // Gestione validità temporale
    const sempre = !mesiValidi || mesiValidi.length === 0;
    document.getElementById('editValiditaSempre').checked = sempre;
    document.getElementById('editMesiContainer').style.display = sempre ? 'none' : 'block';

    // Reset tutti i checkbox dei mesi
    document.querySelectorAll('input[name="editMesi"]').forEach(cb => {
        cb.checked = false;
    });

    // Seleziona i mesi validi
    if (mesiValidi && mesiValidi.length > 0) {
        mesiValidi.forEach(mese => {
            const checkbox = document.querySelector(`input[name="editMesi"][value="${mese}"]`);
            if (checkbox) checkbox.checked = true;
        });
    }

    document.getElementById('editOperazioneModal').style.display = 'block';
}

document.getElementById('editOperazioneForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const id = document.getElementById('editOperazioneId').value;
    const titolo = document.getElementById('editOperazioneTitolo').value;
    const descrizione = document.getElementById('editOperazioneDescrizione').value;
    const cdl = document.getElementById('editOperazioneCDL').value;
    const sempre = document.getElementById('editValiditaSempre').checked;

    let mesiValidi = [];
    if (!sempre) {
        const checkboxes = document.querySelectorAll('input[name="editMesi"]:checked');
        mesiValidi = Array.from(checkboxes).map(cb => parseInt(cb.value));
    }

    try {
        const response = await fetch(`/api/admin/operazioni/${flottaId}/${scadenzaId}/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ titolo, descrizione, cdl, mesi_validi: mesiValidi })
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
    try {
        const response = await fetch(`/api/admin/operazioni/${flottaId}/${scadenzaId}/${id}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) {
            location.reload();
        }
    } catch (error) {
        console.error(error);
    }
}
