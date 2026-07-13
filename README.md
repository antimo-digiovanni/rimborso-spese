# Expense Hub

Applicazione Django separata dal portale San Vincenzo, pensata come MVP multi-azienda per rimborsi spese.

## Cosa include

- aziende con tenant logico e codice invito
- creazione tenant direttamente dal nome azienda durante la registrazione del primo dipendente
- registrazione self-service dei dipendenti
- dashboard personale per ogni dipendente
- inserimento richieste rimborso con allegato ricevuta
- pannello aziendale per approvare, respingere o segnare rimborsate le richieste
- installazione come PWA da browser mobile compatibili
- pannello Django admin per gestire aziende, dipendenti e rimborsi

## Avvio locale

```powershell
Push-Location .\expense_hub
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py createsuperuser
..\.venv\Scripts\python.exe manage.py runserver
Pop-Location
```

## Bootstrap prima azienda

```powershell
Push-Location .\expense_hub
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py bootstrap_company_admin --company-name "Acme Logistics" --invite-code ACME2026 --admin-email admin@acme.example --password "ChangeMe123!" --first-name "Mario" --last-name "Rossi"
Pop-Location
```

Questo comando crea o aggiorna l'azienda, il suo codice invito e il primo utente con permessi di gestione aziendale.

## Ambiente consigliato per produzione

- `SECRET_KEY`
- `DEBUG=0`
- `ALLOWED_HOSTS=your-domain.onrender.com`
- `DATABASE_URL=<postgres-url>`
- `DEFAULT_FROM_EMAIL=noreply@your-domain.com`
- `USE_S3_MEDIA=1`
- `AWS_ACCESS_KEY_ID=<bucket-key>`
- `AWS_SECRET_ACCESS_KEY=<bucket-secret>`
- `AWS_STORAGE_BUCKET_NAME=<bucket-name>`
- `AWS_S3_REGION_NAME=<bucket-region>`
- `AWS_S3_ENDPOINT_URL=<https://...>`
- `AWS_S3_CUSTOM_DOMAIN=<cdn-or-public-domain-opzionale>`

Con questa configurazione i dati si separano cosi:

- `DATABASE_URL` conserva dati strutturati come utenti, aziende, richieste, stati e riferimenti agli allegati.
- lo storage S3 compatibile conserva i file veri: loghi aziendali in `company-logos/` e scontrini in `receipts/anno/mese/`.
- se `USE_S3_MEDIA=0`, i file tornano a essere salvati localmente in `media/`, utile solo in sviluppo.

## Deploy Render

Se vuoi pubblicarla come servizio separato dal progetto attuale, conviene usare una repo dedicata che contenga solo la cartella expense_hub.

Se invece la tieni nello stesso monorepo, su Render devi impostare Root Directory = expense_hub.

## Preparazione repo separata

Da questo workspace puoi esportare solo la nuova app in una cartella pulita, senza trascinarti dietro cedolini web:

```powershell
Push-Location .\expense_hub
.\export_for_repo.ps1
Pop-Location
```

La cartella di output predefinita sarA `..\expense_hub_publish` e conterrA solo i file utili alla nuova app.

Poi puoi pubblicarla come repo autonoma con un flusso minimo del tipo:

```powershell
Push-Location .\expense_hub_publish
git init
git add .
git commit -m "Initial Expense Hub"
git branch -M main
git remote add origin <nuova-repo-github>
git push -u origin main
Pop-Location
```

Su Render, se usi la repo separata, non serve Root Directory: la root sarA gia la nuova app.

Build command:

```text
pip install -r requirements.txt
```

Pre-deploy command:

```text
python manage.py migrate --noinput
```

Start command:

```text
python -m gunicorn expense_hub_project.wsgi:application --bind 0.0.0.0:${PORT:-10000}
```

## Persistenza consigliata su Render

Per non perdere file o dati ai riavvii:

- collega un database Postgres Render e imposta `DATABASE_URL`
- collega uno storage S3 compatibile come Cloudflare R2, AWS S3 o Backblaze B2
- abilita `USE_S3_MEDIA=1`

In questo modo il servizio web resta stateless: l'app gira su Render, i dati tabellari vanno su Postgres e i file caricati restano nel bucket.