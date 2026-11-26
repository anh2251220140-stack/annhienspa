"""Durable ORM index for the public catalog, shared by Vercel instances."""
from hashlib import sha256
import json

from .config import enabled, remaining
from .integration import ProviderUnavailable
from .models import RagDocumentIndex
from .provider_factory import embedding_identity, embedding_provider
from .rag import chunks, cosine, validate_vectors


class DatabaseVectorIndex:
    def __init__(self):
        profile = embedding_identity()
        self.dimensions = profile["dimensions"]
        self.namespace = sha256(json.dumps(["rag-v1", profile], sort_keys=True).encode()).hexdigest()

    def _rows(self):
        return RagDocumentIndex.objects.filter(namespace=self.namespace)

    def invalidate(self, keys):
        self._rows().filter(document_key__in=keys).delete()

    def sync(self, documents, embedder=None):
        previous = dict(self._rows().values_list("document_key", "digest"))
        removed = previous.keys() - documents.keys()
        changed = [doc for key, doc in documents.items() if previous.get(key) != doc.digest]
        if (changed or removed) and not enabled("AI_RAG_INDEX_UPDATE_APPROVED"):
            raise ProviderUnavailable("Vector indexing/update requires separate approval")
        self.invalidate(removed)
        if not changed:
            return 0
        embedder = embedder or embedding_provider()
        indexed = 0
        for doc in changed:
            remaining()
            parts = list(chunks(doc.text))
            if not parts:
                self.invalidate([doc.key])
                continue
            vectors = embedder.embed(parts)
            validate_vectors(vectors, self.dimensions)
            if len(vectors) != len(parts):
                raise ProviderUnavailable("Embedding count mismatch")
            # A document's digest and all its chunks are replaced in one row.
            RagDocumentIndex.objects.update_or_create(
                namespace=self.namespace, document_key=doc.key,
                defaults={"digest": doc.digest, "chunks": list(zip(parts, vectors))},
            )
            indexed += 1
        return indexed

    def ready(self, documents):
        return any(
            key in documents and documents[key].digest == digest
            for key, digest in self._rows().values_list("document_key", "digest")
        )

    def search(self, query_vector, documents, threshold):
        validate_vectors([query_vector], self.dimensions)
        result = []
        current = {k: d.digest for k, d in documents.items()}
        for row in self._rows().filter(document_key__in=current).iterator(chunk_size=32):
            if current[row.document_key] != row.digest:
                continue
            for text, vector in row.chunks:
                validate_vectors([vector], self.dimensions)
                score = cosine(query_vector, vector)
                if score >= threshold:
                    result.append((score, documents[row.document_key], text))
        return result
