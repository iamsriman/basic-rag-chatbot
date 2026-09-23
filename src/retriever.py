from embedding import model
from vector_store import collection

def retrieve(query, top_k=3):
    query_embedding= model.encode([query])
    results=collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=top_k
    )
    return results

if __name__=="__main__":
    query="what is supervised learning?"
    results=retrieve(query, top_k=3)
    print("\nRetrieved documents:\n")

    for document in results:
        print("--------------------------------")
        print(document["ids"])
        