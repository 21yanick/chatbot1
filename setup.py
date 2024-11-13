# setup.py

from setuptools import setup, find_packages

setup(
    name="fahrzeugexperten-chatbot",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'streamlit>=1.28.1',
        'langchain>=0.0.335',
        'chromadb>=0.4.17',
        'python-dotenv>=1.0.0',
        'pydantic>=2.5.2',
        'openai>=1.3.7',
        'pytest>=7.4.3',
        'pytest-asyncio>=0.21.1',
    ],
    python_requires='>=3.12',
)