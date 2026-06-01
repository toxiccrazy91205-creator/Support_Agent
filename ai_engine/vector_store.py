import os
import chromadb
from chromadb.config import Settings

CHROMA_DIR = os.path.join(os.path.dirname(__file__), 'chroma_db')

def get_chroma_collection():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(name="knowledge_base")
    return collection

def seed_knowledge_base():
    collection = get_chroma_collection()
    
    if collection.count() > 0:
        return

    documents = [
        "Our working hours are Monday to Friday, 9 AM to 6 PM.",
        "We offer software development, AI consulting, and web design services.",
        "Our pricing starts at $50/hour for basic consultation.",
        "You can view our complete service catalog at https://example.com/catalog.pdf"
    ]
    ids = ["faq1", "faq2", "faq3", "catalog1"]
    
    collection.add(
        documents=documents,
        ids=ids
    )

def search_knowledge_base(query, n_results=1):
    collection = get_chroma_collection()
    results = collection.query(query_texts=[query], n_results=n_results)
    if results['documents'] and len(results['documents'][0]) > 0:
        return results['documents'][0][0]
    return "No relevant information found."
