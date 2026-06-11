import os
from langchain_community.llms import Ollama
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1")
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def get_llm():
    # langchain_community.llms.Ollama se conecta al puerto de ollama
    # Aumentamos el timeout a 300 segundos para dar tiempo a cargar el modelo en CPU
    return Ollama(base_url=OLLAMA_URL, model=LLM_MODEL, timeout=300)

def get_embeddings():
    return FastEmbedEmbeddings(model_name=EMBED_MODEL)
