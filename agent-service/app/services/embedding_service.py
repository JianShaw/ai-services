from langchain_openai import OpenAIEmbeddings

from app.config.settings import settings

_embeddings: OpenAIEmbeddings | None = None


def get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.embedding_api_key or settings.openai_api_key,
            base_url=settings.embedding_base_url or settings.openai_base_url,
            check_embedding_ctx_length=False,
            tiktoken_enabled=False,
            chunk_size=10,
        )
    return _embeddings
