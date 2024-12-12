from setuptools import setup, find_packages

setup(
    name="fahrzeugexperten-chatbot",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'streamlit==1.40.1',
        'langchain==0.3.7',
        'langchain-community==0.3.7',
        'langchain-core==0.3.17',
        'langchain-openai==0.2.8',
        'chromadb==0.5.18',
        'chroma-hnswlib==0.7.6',  # wichtig für chromadb
        'python-dotenv==1.0.1',
        'pydantic==2.9.2',
        'pydantic-settings==2.6.1',
        'pydantic_core==2.23.4',  # wichtig für pydantic
        'openai==1.54.4',
        'PyYAML==6.0.2',
        'fastapi==0.115.5',
        'uvicorn==0.32.0',
        'python-dateutil==2.9.0.post0',
        'tiktoken==0.8.0',  # für OpenAI token counting
        'httpx==0.27.2',  # spezifische Version aus dem funktionierenden venv
        'coloredlogs==15.0.1',
        'SQLAlchemy==2.0.35',
        'langchain-text-splitters==0.3.2',
        'langsmith==0.1.142',  # Version aus dem funktionierenden venv
    ],
    python_requires='>=3.12',
)