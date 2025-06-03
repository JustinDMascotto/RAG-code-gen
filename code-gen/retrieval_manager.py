"""Retrieval and vector store management for the RAG system."""

from functools import lru_cache
from typing import List, Any, Dict
from langchain_community.vectorstores import Qdrant
from langchain_community.embeddings import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from llm_manager import estimate_tokens


class RetrievalManager:
    """Manages vector store retrieval and content processing."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize retrieval manager with configuration."""
        self.config = config
        
        # Initialize Qdrant client
        self.qdrant_client = QdrantClient(
            host=config["qdrant"]["host"],
            port=config["qdrant"]["port"]
        )
        
        # Initialize embeddings
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=config["embedding"]["model"]
        )
        
        # Initialize vector store
        self.vectorstore = Qdrant(
            client=self.qdrant_client,
            collection_name=config["qdrant"]["collection_name"],
            embeddings=self.embedding_model,
            content_payload_key="code"
        )
        
        # Initialize retriever
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": config["retriever"]["top_k"]}
        )
    
    @lru_cache(maxsize=100)
    def cached_retrieve(self, query: str) -> List[Any]:
        """Cached retrieval with error handling."""
        try:
            return self.retriever.invoke(query)
        except Exception as e:
            print(f"⚠️  Warning: Retrieval failed for query: {query[:50]}...")
            print(f"   Error: {e}")
            return []
    
    def truncate_retrieved_content(self, retrieved_docs: List[Any], max_tokens: int = 3000) -> str:
        """Truncate retrieved content to fit within token limits."""
        if not retrieved_docs:
            return "No relevant code found."
        
        content_parts = []
        current_tokens = 0
        
        for doc in retrieved_docs[:10]:  # Limit to first 10 documents
            doc_content = getattr(doc, 'page_content', str(doc))
            if hasattr(doc, 'metadata'):
                metadata = doc.metadata
                doc_text = f"// From: {metadata.get('symbol', 'unknown')}\n{doc_content}"
            else:
                doc_text = doc_content
            
            doc_tokens = estimate_tokens(doc_text)
            if current_tokens + doc_tokens > max_tokens:
                # Truncate this document to fit
                remaining_tokens = max_tokens - current_tokens
                if remaining_tokens > 100:  # Only add if we have reasonable space
                    truncated_chars = remaining_tokens * 4
                    doc_text = doc_text[:truncated_chars] + "..."
                    content_parts.append(doc_text)
                break
            
            content_parts.append(doc_text)
            current_tokens += doc_tokens
        
        return "\n\n---\n\n".join(content_parts)
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the Qdrant collection."""
        try:
            collection_info = self.qdrant_client.get_collection(
                self.config["qdrant"]["collection_name"]
            )
            vector_count = self.qdrant_client.count(
                self.config["qdrant"]["collection_name"]
            )
            return {
                "status": "connected",
                "collection": collection_info,
                "vector_count": vector_count.count
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }