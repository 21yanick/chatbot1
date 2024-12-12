# Erstelle eine neue Datei test_env.py im Root-Verzeichnis
from src.config.settings import settings
print(f"API Key: {settings.openai_api_key[:10]}...")  # Zeigt nur die ersten 10 Zeichen
print(f"Database Dir: {settings.database.persist_directory}")
print(f"Collection: {settings.database.collection_name}")
print(f"Max Messages: {settings.chat.max_context_messages}")