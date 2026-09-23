from pdf_loader import load_pdf


def create_chunks(text, chunk_size=500, overlap=50):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size")

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end - overlap, start + 1)

    return chunks


if __name__ == "__main__":
    text = load_pdf("data/2024-wttc-introduction-to-ai.pdf")

    chunks = create_chunks(text)

    print("Total chunks:", len(chunks))

    for i, chunk in enumerate(chunks[:3]):
        print(f"\n--- Chunk {i + 1} ---")
        print(chunk)