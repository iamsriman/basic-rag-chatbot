import chromadb
from pdf_loader import load_pdf
from chunker import create_chunks
from embedding import create_embeddings

client = chromadb.PersistentClient(path="./chroma_db")
collection=client.get_or_create_collection(
    name="documents"
)

def add_documents(chunks, embeddings):
    ids=[f'chunk_{i}' for i in range(len(chunks))]
    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings.tolist()
    )
    print(f"added {len(chunks)} chunks to ChromaDB")


if __name__== "__main__":
    text=load_pdf("data/2024-wttc-introduction-to-ai.pdf")
    chunks=create_chunks(text)
    embeddings= create_embeddings(chunks)
    add_documents(chunks, embeddings)
    print("total documents: ",collection.count())