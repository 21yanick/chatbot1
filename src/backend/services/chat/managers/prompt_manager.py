"""
Prompt Manager Modul für die Verwaltung und Erstellung von Chat-Prompts.
Verwaltet Templates und erstellt kontextbezogene Prompts für den LLM.
"""

from typing import Dict, Any, Optional
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage

from src.config.settings import settings
from src.config.logging_config import get_logger, log_execution_time

class PromptManagerError(Exception):
    """Basisklasse für PromptManager-spezifische Fehler."""
    pass

class PromptManager:
    """
    Verwaltet Prompt-Templates und erstellt kontextbezogene Prompts.
    
    Verantwortlich für:
    - Verwaltung von Prompt-Templates
    - Anpassung von Prompts basierend auf Kontext
    - Formatierung von System- und Benutzer-Prompts
    """
    
    def __init__(self):
        """Initialisiert den PromptManager mit Standard-Templates."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.templates = self._initialize_templates()

    def _initialize_templates(self) -> Dict[str, str]:
        """
        Initialisiert die Standard-Prompt-Templates.
        
        Returns:
            Dict mit Template-Namen und deren Inhalt
        """
        return {
            "default": """Du bist ein Fahrzeug-Experten-Assistent aus dem Kanton Solothurn in der Schweiz.
            Du bist sehr Schweiz bezogen und Kanton Solothurn.
            Nutze den folgenden Kontext und Chat-Verlauf, um die Frage des Benutzers zu beantworten.
            Wenn du die Antwort nicht weisst, sag es einfach ehrlich - erfinde keine Informationen.

            Kontext:
            {context}

            Chat-Verlauf:
            {chat_history}

            Benutzeranfrage: {query}

            Antworte in der gleichen Sprache wie die Anfrage. Sei präzise aber gründlich.""",
            
            "document_analysis": """Du bist ein Fahrzeug-Experten-Assistent, der sich auf die Analyse von Dokumenten spezialisiert.
            Analysiere die folgenden Dokumente im Kontext der Benutzeranfrage.
            Beziehe dich spezifisch auf die relevanten Abschnitte.

            Dokumente:
            {context}

            Benutzeranfrage: {query}

            Liefere eine strukturierte Analyse mit Verweisen auf die Quellen.""",
            
            "technical": """Du bist ein technischer Fahrzeug-Experte.
            Beantworte die folgende Frage mit Fokus auf technische Details und Spezifikationen.
            Nutze den bereitgestellten Kontext, aber ergänze auch mit deinem Fachwissen.

            Kontext:
            {context}

            Chat-Verlauf:
            {chat_history}

            Technische Anfrage: {query}

            Liefere eine detaillierte technische Erklärung."""
        }

    def create_prompt(
        self,
        template_name: str = "default",
        **kwargs: Any
    ) -> ChatPromptTemplate:
        """
        Erstellt einen Prompt basierend auf einem Template.
        
        Args:
            template_name: Name des zu verwendenden Templates
            **kwargs: Template-Variablen
            
        Returns:
            Formatierter ChatPromptTemplate
            
        Raises:
            PromptManagerError: Bei Template- oder Formatierungsfehlern
        """
        try:
            with log_execution_time(self.logger, "create_prompt"):
                if template_name not in self.templates:
                    raise PromptManagerError(f"Template nicht gefunden: {template_name}")
                
                template = self.templates[template_name]
                
                # Erstelle ChatPromptTemplate
                prompt = ChatPromptTemplate.from_messages([
                    SystemMessage(content=template)
                ])
                
                self.logger.info(
                    "Prompt erstellt",
                    extra={
                        "template": template_name,
                        "variables": list(kwargs.keys())
                    }
                )
                
                return prompt
            
        except Exception as e:
            self.logger.error(
                f"Fehler bei der Prompt-Erstellung: {str(e)}",
                extra={
                    "template": template_name,
                    "variables": list(kwargs.keys())
                }
            )
            raise PromptManagerError(f"Prompt-Erstellung fehlgeschlagen: {str(e)}")

    def add_template(self, name: str, template: str) -> None:
        """
        Fügt ein neues Template hinzu.
        
        Args:
            name: Name des Templates
            template: Template-String
            
        Raises:
            PromptManagerError: Bei ungültigen Templates
        """
        try:
            if not template or not isinstance(template, str):
                raise ValueError("Template muss ein nicht-leerer String sein")
            
            self.templates[name] = template
            
            self.logger.info(
                "Template hinzugefügt",
                extra={"template_name": name}
            )
            
        except Exception as e:
            self.logger.error(
                f"Fehler beim Hinzufügen des Templates: {str(e)}",
                extra={"template_name": name}
            )
            raise PromptManagerError(f"Template konnte nicht hinzugefügt werden: {str(e)}")

    def remove_template(self, name: str) -> bool:
        """
        Entfernt ein Template.
        
        Args:
            name: Name des zu entfernenden Templates
            
        Returns:
            True wenn erfolgreich entfernt
            
        Raises:
            PromptManagerError: Bei geschützten Templates
        """
        try:
            if name == "default":
                raise PromptManagerError("Das Standard-Template kann nicht entfernt werden")
            
            if name in self.templates:
                del self.templates[name]
                self.logger.info(
                    "Template entfernt",
                    extra={"template_name": name}
                )
                return True
            
            self.logger.warning(
                "Template zum Entfernen nicht gefunden",
                extra={"template_name": name}
            )
            return False
            
        except Exception as e:
            self.logger.error(
                f"Fehler beim Entfernen des Templates: {str(e)}",
                extra={"template_name": name}
            )
            raise PromptManagerError(f"Template konnte nicht entfernt werden: {str(e)}")

    def get_template(self, name: str) -> Optional[str]:
        """
        Ruft ein Template ab.
        
        Args:
            name: Name des Templates
            
        Returns:
            Template-String oder None wenn nicht gefunden
        """
        template = self.templates.get(name)
        if template:
            self.logger.debug(
                "Template abgerufen",
                extra={"template_name": name}
            )
        else:
            self.logger.warning(
                "Template nicht gefunden",
                extra={"template_name": name}
            )
        return template

    def format_prompt(
        self,
        template_name: str = "default",
        variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Formatiert ein Template mit Variablen.
        
        Args:
            template_name: Name des Templates
            variables: Dict mit Template-Variablen
            
        Returns:
            Formatierter Prompt-String
            
        Raises:
            PromptManagerError: Bei Formatierungsfehlern
        """
        try:
            with log_execution_time(self.logger, "format_prompt"):
                template = self.get_template(template_name)
                if not template:
                    raise PromptManagerError(f"Template nicht gefunden: {template_name}")
                
                variables = variables or {}
                formatted_prompt = template.format(**variables)
                
                self.logger.info(
                    "Prompt formatiert",
                    extra={
                        "template": template_name,
                        "variables": list(variables.keys())
                    }
                )
                
                return formatted_prompt
            
        except Exception as e:
            self.logger.error(
                f"Fehler bei der Prompt-Formatierung: {str(e)}",
                extra={
                    "template": template_name,
                    "variables": list(variables.keys() if variables else [])
                }
            )
            raise PromptManagerError(f"Prompt-Formatierung fehlgeschlagen: {str(e)}")