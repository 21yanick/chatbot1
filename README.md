# Fahrzeugexperten-Chatbot

Ein kontextbewusster Chatbot für Fahrzeugexperten, der Fragen zu Fahrzeugen und zum Straßenverkehrsrecht beantwortet.

## Installation

1. Repository klonen:
```bash
git clone [repository-url]
cd fahrzeugexperten-chatbot
```

2. Virtuelle Umgebung erstellen und aktivieren:
```bash
python -m venv venv
source venv/bin/activate  # Unter Windows: venv\Scripts\activate
```

3. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

4. Umgebungsvariablen konfigurieren:
```bash
cp .env.example .env
# .env-Datei mit entsprechenden Werten füllen
```

## Entwicklung

1. Tests ausführen:
```bash
pytest
```

2. Anwendung starten:
```bash
streamlit run src/frontend/app.py
```

## Projektstruktur

- `src/`: Quellcode
  - `frontend/`: Streamlit-UI
  - `backend/`: Geschäftslogik
  - `api/`: API-Endpunkte
  - `config/`: Konfigurationsdateien
- `tests/`: Tests
- `docs/`: Dokumentation
- `data/`: Datendateien
