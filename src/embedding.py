from sentence_transformers import SentenceTransformer
from pdf_loader import load_pdf
from chunker import create_chunks
model=SentenceTransformer("all-MiniLM-L6-v2")
def create_embeddings(chunks):
    embeddings=model.encode(chunks)
    return embeddings


if __name__ == "__main__":

    text = load_pdf("data/2024-wttc-introduction-to-ai.pdf")

    chunks = create_chunks(text)

    embeddings = create_embeddings(chunks)
    print(chunks[0])
    print(embeddings[0])
    print("Number of chunks:", len(chunks))
    print("Number of embeddings:", len(embeddings))
    print("Embedding dimension:", len(embeddings[0]))