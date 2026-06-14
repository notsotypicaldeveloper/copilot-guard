"""
Permission-gated RAG Copilot answerer.

Simulates how Microsoft 365 Copilot answers questions — but ONLY over files
the requesting identity can access (scope == 'everyone' for the intern identity).

This is the mechanic that makes the before/after demo work:
  - BEFORE: salary file is scope='everyone' → Copilot finds and answers with salary
  - AFTER:  CopilotGuard restricts it → scope='restricted' → Copilot refuses
"""
from typing import Optional

from backend.config import get_openai_client, MODEL_NAME
from backend.tenant.data import get_adapter


def ask_copilot(question: str, identity: str = "intern") -> dict:
    """
    Answer `question` using only files accessible to `identity`.

    identity='intern' → can read scope='everyone' files only
    identity='admin'  → can read all files (used for architecture demos)

    Returns dict with: answer, sources_used, access_denied
    """
    adapter = get_adapter()
    all_items = adapter.list_items()

    # Permission gate — intern only sees 'everyone' scoped files
    if identity == "admin":
        accessible_ids = [i["id"] for i in all_items]
    else:
        accessible_ids = [i["id"] for i in all_items if i["scope"] == "everyone"]

    # Build context from accessible file contents
    context_parts = []
    sources_used = []
    for file_id in accessible_ids:
        content = adapter.get_item_content(file_id)
        if content:
            meta = next((i for i in all_items if i["id"] == file_id), {})
            context_parts.append(f"[{meta.get('name', file_id)}]\n{content}")
            sources_used.append(meta.get("name", file_id))

    if not context_parts:
        return {
            "answer": "I'm sorry, I couldn't find any information you have access to that answers this question.",
            "sources_used": [],
            "access_denied": True,
        }

    context = "\n\n---\n\n".join(context_parts)

    client = get_openai_client()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Microsoft 365 Copilot, an AI assistant integrated into the enterprise. "
                    "Answer the user's question using ONLY the documents provided below. "
                    "If the answer is in the documents, provide it directly and cite the source file. "
                    "If the answer is NOT in the provided documents, say: "
                    "'I'm sorry, I couldn't find information you have access to that answers this question.' "
                    "Never make up information not in the documents."
                ),
            },
            {
                "role": "user",
                "content": f"Documents I have access to:\n\n{context}\n\n---\n\nQuestion: {question}",
            },
        ],
        temperature=0.1,
        max_tokens=400,
    )

    answer = response.choices[0].message.content.strip()
    access_denied = "couldn't find" in answer.lower() or "don't have access" in answer.lower()

    return {
        "answer": answer,
        "sources_used": sources_used if not access_denied else [],
        "access_denied": access_denied,
    }
