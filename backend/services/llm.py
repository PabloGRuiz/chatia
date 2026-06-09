import os
from langchain_community.llms import Ollama
from langchain_community.embeddings import OllamaEmbeddings
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

def get_llm():
    # langchain_community.llms.Ollama se conecta al puerto de ollama
    # Aumentamos el timeout a 300 segundos para dar tiempo a cargar el modelo en CPU
    return Ollama(base_url=OLLAMA_URL, model=LLM_MODEL, timeout=300)

def get_embeddings():
    return OllamaEmbeddings(base_url=OLLAMA_URL, model=EMBED_MODEL)
