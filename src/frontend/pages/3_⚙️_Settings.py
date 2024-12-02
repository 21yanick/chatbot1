"""
Settings Page - Zentrale Einstellungsverwaltung für den Fahrzeugexperten-Chatbot

Diese Seite ermöglicht die Verwaltung aller Benutzereinstellungen:
- Theme/Design
- Chat-Verhalten
- Debug-Optionen
- Anzeigeoptionen
"""

import streamlit as st
from src.config.settings import settings
from src.frontend.utils.state_manager import StateManager

def render_theme_settings():
    """Rendert die Theme/Design-Einstellungen."""
    st.subheader("🎨 Design & Erscheinungsbild")
    
    # Info über Theme-Einstellung
    st.info(
        "🎨 Das Design (Hell/Dunkel) können Sie über das Streamlit-Menü (☰) "
        "oben rechts unter 'Settings' > 'Theme' anpassen."
    )
    
    # Andere Design-Optionen
    st.toggle(
        "Kompakter Modus",
        value=st.session_state.get("compact_mode", False),
        help="Reduziert Abstände und Größen für mehr Inhalt"
    )

def render_chat_settings():
    """Rendert die Chat-bezogenen Einstellungen."""
    st.subheader("💬 Chat-Einstellungen")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.toggle(
            "Zeitstempel anzeigen",
            value=st.session_state.get("show_timestamps", False),
            help="Zeigt Zeitstempel für jede Nachricht an"
        )
        
        st.toggle(
            "Quellen automatisch ausklappen",
            value=st.session_state.get("show_sources", False),
            help="Klappt Quellenangaben automatisch aus"
        )
    
    with col2:
        st.number_input(
            "Maximale Nachrichtenlänge",
            min_value=100,
            max_value=4000,
            value=st.session_state.get("max_message_length", 2000),
            help="Maximale Länge einer Chatnachricht in Zeichen"
        )
        
        st.slider(
            "Antwort-Geschwindigkeit",
            min_value=0.0,
            max_value=2.0,
            value=st.session_state.get("response_speed", 1.0),
            help="Geschwindigkeit der Textgenerierung (0=schnell, 2=langsam)"
        )

def render_debug_settings():
    """Rendert die Debug- und Entwicklereinstellungen."""
    st.subheader("🛠️ Entwickleroptionen")
    
    debug_mode = st.toggle(
        "Debug-Modus",
        value=st.session_state.get("debug_mode", False),
        help="Zeigt zusätzliche technische Informationen an"
    )
    
    if debug_mode:
        st.info(
            "Der Debug-Modus ist aktiviert. Sie sehen nun zusätzliche "
            "technische Informationen in der Anwendung."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.toggle(
                "Performance-Metriken anzeigen",
                value=st.session_state.get("show_performance", False)
            )
        with col2:
            st.toggle(
                "API-Aufrufe protokollieren",
                value=st.session_state.get("log_api_calls", False)
            )
        
        # Debug-Informationen
        with st.expander("🔍 Debug-Informationen", expanded=False):
            st.json({
                "session_id": st.session_state.get("session_id", "Nicht verfügbar"),
                "theme": st.session_state.get("theme", "System"),
                "debug_settings": {
                    "show_performance": st.session_state.get("show_performance", False),
                    "log_api_calls": st.session_state.get("log_api_calls", False)
                },
                "chat_settings": {
                    "show_timestamps": st.session_state.get("show_timestamps", False),
                    "show_sources": st.session_state.get("show_sources", False),
                    "max_message_length": st.session_state.get("max_message_length", 2000),
                    "response_speed": st.session_state.get("response_speed", 1.0)
                }
            })

def main():
    """Hauptfunktion der Settings-Page."""
    st.title("⚙️ Einstellungen")
    st.write(
        "Hier können Sie verschiedene Aspekte der Anwendung an Ihre "
        "Bedürfnisse anpassen."
    )
    
    # Tabs für bessere Organisation
    tab1, tab2, tab3 = st.tabs(
        ["🎨 Design", "💬 Chat", "🛠️ Entwickler"]
    )
    
    with tab1:
        render_theme_settings()
    
    with tab2:
        render_chat_settings()
    
    with tab3:
        render_debug_settings()
    
    # Einstellungen zurücksetzen
    st.divider()
    if st.button("🔄 Alle Einstellungen zurücksetzen", type="secondary"):
        # Liste der zu löschenden Einstellungen
        settings_to_reset = [
            "theme", "compact_mode", "show_timestamps", "show_sources",
            "max_message_length", "response_speed", "debug_mode",
            "show_performance", "log_api_calls"
        ]
        
        # Einstellungen aus Session State entfernen
        for key in settings_to_reset:
            if key in st.session_state:
                del st.session_state[key]
        
        st.success("✅ Alle Einstellungen wurden zurückgesetzt!")
        st.rerun()

if __name__ == "__main__":
    state_manager = StateManager()
    main()