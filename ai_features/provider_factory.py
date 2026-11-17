"""Gemini-only external selection; mock vectors are local lexical hashes."""
import hashlib
import math
import re

from .config import option
from .integration import ProviderUnavailable


class LocalEmbeddingProvider:
    """Deterministic lexical vectors, not a remote semantic embedding model."""
    dimensions = 256

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in re.findall(r"\w+", text.casefold()):
                slot = int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:4], "big") % self.dimensions
                vector[slot] += 1
            norm = math.sqrt(sum(x * x for x in vector))
            vectors.append([x / norm for x in vector] if norm else vector)
        return vectors

    def embed_query(self, text):
        return self.embed([text])[0]


def external_provider():
    if option("AI_PROVIDER", "mock") == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider()
    raise ProviderUnavailable("Only Gemini is allowed as an external AI provider")


def embedding_provider():
    if option("AI_PROVIDER", "mock") == "mock":
        return LocalEmbeddingProvider()
    return external_provider()


def embedding_identity():
    name = option("AI_PROVIDER", "mock")
    if name == "gemini":
        from .gemini import embedding_spec
        return embedding_spec()
    if name == "mock":
        return {"provider": "mock", "model": "local-lexical-sha256", "version": "1",
                "dimensions": LocalEmbeddingProvider.dimensions, "task": "lexical",
                "normalization": "l2"}
    raise ProviderUnavailable("Only Gemini or local mock embeddings are allowed")
