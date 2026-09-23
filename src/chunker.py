from pdf_loader import load_pdf

def create_chunks(text,chunk_size=500,overlap=50):
    chunks=[]
    start=0
    while start<len(text):
        end=start+chunk_size
        chunk=text[start:end]
        chunks.append(chunk)
        start=end-overlap
    return chunks

if __name__ == "__main__":
    text = load_pdf("data/2024-wttc-introduction-to-ai.pdf")

    chunks = create_chunks(text)

    print("Total chunks:", len(chunks))

    for i, chunk in enumerate(chunks[:3]):
        print(f"\n--- Chunk {i + 1} ---")
        print(chunk)