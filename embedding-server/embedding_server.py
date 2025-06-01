from fastapi import FastAPI, Request
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing import List

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

app = FastAPI()

class EmbedRequest(BaseModel):
    texts: List[str]

@app.post("/embed")
async def embed_texts(request: EmbedRequest):
    vectors = model.encode(request.texts, normalize_embeddings=True)
    return {"embeddings": [v.tolist() for v in vectors]}