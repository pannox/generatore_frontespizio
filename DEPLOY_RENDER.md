# 🚀 Guida Deploy su Render.com

## Preparazione Completata ✅

Il progetto è ora pronto per il deploy su Render! Ho aggiunto:
- `requirements.txt` con Gunicorn
- `render.yaml` (configurazione automatica)
- `build.sh` (script di setup)
- `.gitignore` (file da non caricare)
- `.env.example` (template variabili ambiente)

---

## 📋 PASSO 1: Preparare il Repository Git

### 1.1 Inizializza Git (se non l'hai già fatto)
```bash
cd c:\Users\gpann\Desktop\FRONTESPIZIO_python
git init
git add .
git commit -m "Prepara progetto per deploy su Render"
```

### 1.2 Crea Repository su GitHub
1. Vai su https://github.com/new
2. Nome repository: `frontespizio-generator` (o nome a tua scelta)
3. **NON** aggiungere README, .gitignore o licenza (li hai già)
4. Clicca "Create repository"

### 1.3 Carica il codice su GitHub
```bash
git branch -M main
git remote add origin https://github.com/TUO_USERNAME/frontespizio-generator.git
git push -u origin main
```

---

## 📋 PASSO 2: Deploy su Render

### 2.1 Crea Account Render
1. Vai su https://render.com
2. Clicca "Get Started"
3. Registrati con GitHub (consigliato) o email

### 2.2 Collega Repository
1. Nel dashboard Render, clicca **"New +"** → **"Web Service"**
2. Clicca **"Connect GitHub"** o **"Connect GitLab"**
3. Autorizza Render ad accedere ai tuoi repository
4. Seleziona il repository `frontespizio-generator`

### 2.3 Configura il Servizio

Render rileverà automaticamente il file `render.yaml`, ma verifica:

**Settings Base:**
- **Name:** `frontespizio-generator` (o nome a tua scelta)
- **Region:** Frankfurt (EU Central) - più vicino all'Italia
- **Branch:** `main`
- **Runtime:** Python 3
- **Build Command:** `./build.sh`
- **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 app:app`

**Instance Type:**
- **FREE** (per test) - va in sleep dopo 15 min inattività
- **Starter ($7/mese)** - sempre online, 512 MB RAM (CONSIGLIATO)

### 2.4 Configura Variabili d'Ambiente

Nella sezione **Environment Variables**, aggiungi:

| Key | Value |
|-----|-------|
| `PYTHON_VERSION` | `3.11.0` |
| `SECRET_KEY` | `[genera stringa casuale lunga]` |
| `ADMIN_PASSWORD` | `treno` (o cambia) |
| `MASTER_PASSWORD` | `368769` (o cambia) |
| `FLASK_ENV` | `production` |

**Per generare SECRET_KEY sicura:**
```python
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2.5 Configura Disco Persistente (IMPORTANTE!)

I file caricati (PDF) vanno salvati su disco persistente:

1. Scorri fino a **"Disks"**
2. Clicca **"Add Disk"**
3. Configura:
   - **Name:** `pdf-storage`
   - **Mount Path:** `/opt/render/project/src/uploaded_pdfs`
   - **Size:** 10 GB (espandibile)

### 2.6 Deploy!

1. Clicca **"Create Web Service"**
2. Render inizierà il build automaticamente
3. Attendi 3-5 minuti per il primo deploy

**Log da monitorare:**
- Vedrai l'installazione dipendenze
- Setup poppler-utils
- Avvio Gunicorn
- "Application startup complete" = SUCCESS! 🎉

---

## 📋 PASSO 3: Configura Dominio Personalizzato

### 3.1 Dominio Gratuito Render
Render ti dà automaticamente: `https://frontespizio-generator.onrender.com`

### 3.2 Dominio Personalizzato

**Se hai già un dominio:**
1. Nel dashboard Render, vai al tuo servizio
2. Tab **"Settings"** → **"Custom Domains"**
3. Clicca **"Add Custom Domain"**
4. Inserisci: `www.tuodominio.it` o `tuodominio.it`
5. Render ti darà un record DNS da configurare

**Nel tuo registrar dominio (es. Cloudflare, Namecheap):**
- Tipo: `CNAME`
- Nome: `www` (o `@` per root)
- Valore: quello fornito da Render (es. `frontespizio-generator.onrender.com`)
- TTL: Automatico

**Se NON hai un dominio:**
1. Compra su Cloudflare/Namecheap (~10€/anno)
2. Segui i passaggi sopra

**SSL/HTTPS:** Automatico e GRATUITO! ✅

---

## 📋 PASSO 4: Verifica Funzionamento

### 4.1 Testa l'Applicazione
1. Apri `https://frontespizio-generator.onrender.com`
2. Verifica che carichi la home
3. Prova a generare un PDF
4. Controlla upload e thumbnail

### 4.2 Monitora Log
Nel dashboard Render → **"Logs"** puoi vedere:
- Richieste HTTP
- Errori eventuali
- Uso risorse

---

## 🔧 Aggiornamenti Futuri

Ogni volta che fai modifiche:

```bash
git add .
git commit -m "Descrizione modifiche"
git push
```

Render farà **deploy automatico** in 2-3 minuti! 🚀

---

## ⚙️ Comandi Utili

### Rollback a versione precedente
Nel dashboard Render → **"Manual Deploy"** → scegli commit precedente

### Riavvia servizio
Dashboard → **"Manual Deploy"** → **"Deploy latest commit"**

### Vedi metriche
Dashboard → **"Metrics"** (CPU, RAM, richieste)

---

## 💰 Costi

**Piano FREE:**
- Hosting: GRATIS
- Storage: 1 GB incluso
- Limitazione: sleep dopo 15 min inattività

**Piano Starter ($7/mese = ~84€/anno):**
- Hosting: sempre online
- 512 MB RAM
- Storage: espandibile (+$1/GB extra)
- SSL incluso
- Backup automatici

---

## 🆘 Risoluzione Problemi

### Build fallisce
- Controlla log build in Render
- Verifica che `build.sh` sia eseguibile
- Assicurati che `requirements.txt` sia corretto

### App non si avvia
- Controlla log runtime
- Verifica variabili d'ambiente
- Assicurati porta sia `$PORT` (variabile Render)

### File PDF non vengono salvati
- Verifica che disco persistente sia montato
- Path corretto: `/opt/render/project/src/uploaded_pdfs`

### Performance lente
- Upgrade a piano Starter
- Aumenta workers Gunicorn (nel comando start)

---

## 📞 Supporto

- **Render Docs:** https://render.com/docs
- **Community:** https://community.render.com
- **Status:** https://status.render.com

---

🎉 **Il tuo progetto è pronto per il deploy!**

Segui i passi sopra e in 15 minuti sarai online con il tuo dominio personalizzato!
