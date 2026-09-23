from embedding import model
from vector_store import collection


def retrieve(query, top_k=3, chat_id=None):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")

    query_embedding = model.encode([query])
    query_options = {
        "query_embeddings": query_embedding.tolist(),
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if chat_id:
        query_options["where"] = {"chat_id": chat_id}

    results = collection.query(**query_options)
    return results


if __name__ == "__main__":
    query = "what is supervised learning?"
    results = retrieve(query, top_k=3)
    print("\nRetrieved documents:\n")

    for document in results["documents"][0]:
        print("--------------------------------")
        print(document)
        