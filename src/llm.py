import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client=genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def generate_answer(question, context):
    prompt = f"""
You are a helpful assistant answering questions based on the provided context.

Context:
{context}

Question:
{question}

Instructions:
- Answer using the provided context.
- If the answer is not present in the context, say that you don't know.
- Do not make up information.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text
