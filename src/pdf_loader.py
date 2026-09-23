import fitz
def load_pdf(file_path):
    document= fitz.open(file_path)
    text=""
    for page in document:
        text+=page.get_text()
    document.close()
    return text

if __name__ == "__main__":
    text = load_pdf("data/2024-wttc-introduction-to-ai.pdf")

    print(text)
    