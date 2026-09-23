import chromadb
from pdf_loader import load_pdf
from chunker import create_chunks
from embedding import create_embeddings

client = chromadb.PersistentClient(path="./chroma_db")
collection=client.get_or_create_collection(
    name="documents"
)

def add_documents(chunks, embeddings, chat_id=None, document_id=None, metadatas=None):
    ids=[f'chunk_{document_id or "legacy"}_{i}' for i in range(len(chunks))]
    if metadatas is None:
        metadatas = [{} for _ in chunks]
    else:
        metadatas = [metadata.copy() for metadata in metadatas]

    for metadata in metadatas:
        if chat_id:
            metadata["chat_id"] = chat_id
        if document_id:
            metadata["document_id"] = document_id

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings.tolist(),
        metadatas=metadatas
    )
    print(f"added {len(chunks)} chunks to ChromaDB")


if __name__== "__main__":
    text=load_pdf("data/2024-wttc-introduction-to-ai.pdf")
    chunks=create_chunks(text)
    embeddings= create_embeddings(chunks)
    add_documents(chunks, embeddings)
    print("total documents: ",collection.count())