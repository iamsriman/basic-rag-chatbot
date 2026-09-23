from retriever import retrieve
from llm import generate_answer


def build_context(documents):
    return "\n\n".join(documents)


def rag(question):
    results = retrieve(question, top_k=3)

    documents = results["documents"][0]

    context = build_context(documents)

    answer = generate_answer(
        question=question,
        context=context
    )

    return answer


if __name__ == "__main__":
    question = input("Ask a question: ")

    answer = rag(question)

    print("\nAnswer:")
    print(answer)