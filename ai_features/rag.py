"""Local vector index for a small Spa catalog (SQLite + exact cosine search).

This auxiliary index never contains customer, booking, invoice or review rows.
The live ORM catalog remains authoritative, including during stale/index failures.
"""
from dataclasses import asdict, dataclass
from contextlib import contextmanager
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sqlite3

from django.conf import settings
from django.utils import timezone

from core.catalog_data import _promotion_discount_label, money
from products.models import CareProduct
from promotions.models import Promotion
from services.models import Service, ServiceCategory

from .config import enabled, option, remaining
from .integration import ProviderUnavailable
from .provider_factory import embedding_identity, embedding_provider
from .providers import Source, normalize
from .chat_intents import is_service_list_question


@dataclass(frozen=True)
class Document:
    source_type: str
    object_id: int | str
    name: str
    text: str
    category: str = ""
    status: str = "active"

    @property
    def key(self):
        return f"{self.source_type}:{self.object_id}"

    @property
    def digest(self):
        return sha256(json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def public_documents():
    result = []
    for c in ServiceCategory.objects.filter(is_active=True).order_by("pk"):
        result.append(Document("category", c.pk, c.name, f"{c.name}: {c.description or ''}", str(c.pk)))
    for s in Service.objects.filter(is_active=True, category__is_active=True).select_related("category").order_by("pk"):
        text = f"{s.name}: {money(s.price)} · {s.duration_minutes} phút. " + " ".join(
            str(getattr(s, f) or "") for f in ("description", "introduction", "benefits", "steps", "suitable", "note"))
        result.append(Document("service", s.pk, s.name, text, str(s.category_id)))
    for p in CareProduct.objects.filter(is_active=True).order_by("pk"):
        text = p.name + ": " + " ".join(str(getattr(p, f) or "") for f in (
            "description", "skin_type", "suitable_for", "benefits", "ingredients", "usage_instructions", "note"))
        result.append(Document("product", p.pk, p.name, text, p.product_type))
    today = timezone.localdate()
    for p in Promotion.objects.filter(is_active=True, start_date__lte=today, end_date__gte=today).prefetch_related("services").order_by("pk"):
        text = (f"{p.name} ({p.code}): {_promotion_discount_label(p.discount_type, p.discount_value)}. "
                f"Từ {p.start_date:%d/%m/%Y} đến {p.end_date:%d/%m/%Y}. "
                f"Giá trị tối thiểu: {money(p.min_amount) if p.min_amount is not None else 'không cấu hình'}. "
                f"Giảm tối đa: {money(p.max_discount) if p.max_discount is not None else 'không cấu hình'}. "
                f"Lượt/khách: {p.per_customer_limit or 'không cấu hình'}. "
                f"Dịch vụ: {', '.join(s.name for s in p.services.all()) or 'theo phạm vi chương trình'}. "
                f"{p.description or ''} {p.detail} {p.conditions} {p.note} {p.scope_note}. "
                "Khả năng áp dụng thực tế phải được hệ thống hóa đơn kiểm tra; không bảo đảm đủ điều kiện.")
        result.append(Document("promotion", p.pk, f"{p.code} · {p.name}", text))
    info = str(option("AI_CHAT_SPA_INFORMATION", "")).strip()
    if info:
        result.append(Document("spa", "information", "Thông tin Spa", info))
    else:
        from .catalog_queries import website_information
        result.append(Document("spa", "information", "Thông tin Spa trên website", website_information()))
    result.append(Document("spa", "booking", "Hướng dẫn đặt lịch trên website",
        "Đăng nhập tài khoản khách hàng, mở trang booking.html hoặc chọn Đặt lịch tại dịch vụ. "
        "Chọn dịch vụ, nhân viên, ngày và khung giờ còn trống, kiểm tra thông tin rồi gửi yêu cầu đặt lịch. "
        "Theo dõi trạng thái tại Lịch hẹn của tôi. Chatbot chỉ hướng dẫn, không tự đặt, hủy lịch hoặc thanh toán."))
    # Only an explicitly configured, reviewed local JSON file is imported, never arbitrary uploads/URLs.
    approved = option("AI_RAG_APPROVED_DOCUMENTS", "")
    if approved:
        data = json.loads(Path(approved).read_text(encoding="utf-8"))
        if not isinstance(data, list) or len(data) > 200:
            raise ValueError("Invalid approved RAG documents")
        for i, d in enumerate(data):
            if not isinstance(d, dict) or set(d) != {"title", "text"} or not all(isinstance(v, str) for v in d.values()):
                raise ValueError("Invalid approved RAG document")
            result.append(Document("faq", i, d["title"][:150], d["text"][:20000]))
    return {d.key: d for d in result}


def chunks(text, size=400, overlap=50):
    """Approximately 400 tokens with 50-token overlap, using UTF-8 byte estimates.

    A Vietnamese word may span several model tokens; counting words as tokens
    underestimates context sizes. Exact provider-token counts are not claimed.
    """
    tokens = list(re.finditer(r"\w+|[^\w\s]", text, re.UNICODE))
    costs = [max(1, math.ceil(len(t.group().encode("utf-8")) / 4)) for t in tokens]
    start = 0
    while start < len(tokens):
        end, total = start, 0
        while end < len(tokens) and (end == start or total + costs[end] <= size):
            total += costs[end]
            end += 1
        yield text[tokens[start].start():tokens[end - 1].end()]
        if end == len(tokens):
            break
        next_start, retained = end, 0
        while next_start > start + 1 and retained < overlap:
            next_start -= 1
            retained += costs[next_start]
        start = max(start + 1, next_start)


def cosine(a, b):
    if len(a) != len(b) or not a:
        return 0.0
    denominator = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / denominator if denominator else 0.0


class VectorIndex:
    def __init__(self):
        root = Path(option("AI_RAG_DIRECTORY", settings.BASE_DIR / ".rag-index"))
        root.mkdir(parents=True, exist_ok=True)
        db = settings.DATABASES["default"]
        self.profile = embedding_identity()
        identity = [db["ENGINE"], str(db["NAME"]), db.get("HOST", ""), db.get("PORT", ""),
                    "vector-index-v2", self.profile]
        namespace = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
        self.path = root / f"vectors-{namespace}.sqlite3"
        with self.connect() as cx:
            cx.execute("CREATE TABLE IF NOT EXISTS documents (key TEXT PRIMARY KEY, digest TEXT, metadata TEXT, updated_at TEXT)")
            cx.execute("CREATE TABLE IF NOT EXISTS chunks (key TEXT, position INTEGER, text TEXT, vector TEXT, PRIMARY KEY(key,position))")
            cx.execute("CREATE TABLE IF NOT EXISTS embedding_config (id INTEGER PRIMARY KEY CHECK(id=1), profile TEXT, dimensions INTEGER)")
            profile = json.dumps(self.profile, sort_keys=True)
            stored = cx.execute("SELECT profile FROM embedding_config WHERE id=1").fetchone()
            if stored and stored[0] != profile:
                raise ProviderUnavailable("Vector store embedding profile mismatch")
            if not stored:
                size = self.profile["dimensions"] if type(self.profile["dimensions"]) is int else None
                cx.execute("INSERT INTO embedding_config VALUES (1,?,?)", (profile, size))

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=3)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def invalidate(self, keys):
        with self.connect() as cx:
            for key in keys:
                cx.execute("DELETE FROM chunks WHERE key=?", (key,))
                cx.execute("DELETE FROM documents WHERE key=?", (key,))

    def sync(self, documents, embedder=None):
        embedder = embedder or embedding_provider()
        with self.connect() as cx:
            previous = dict(cx.execute("SELECT key,digest FROM documents"))
        removed = set(previous) - set(documents)
        changed = [d for k, d in documents.items() if previous.get(k) != d.digest]
        if (changed or removed) and not enabled("AI_RAG_INDEX_UPDATE_APPROVED"):
            raise ProviderUnavailable("Vector indexing/update requires separate approval")
        self.invalidate(removed)
        # Unchanged vectors are retained. A failed embedding never marks new content as indexed.
        for document in changed:
            remaining()
            parts = list(chunks(document.text))
            if not parts:
                continue
            vectors = embedder.embed(parts)
            if len(vectors) != len(parts):
                raise ValueError("Embedding count mismatch")
            with self.connect() as cx:
                dimension = self._check_vectors(cx, vectors)
                cx.execute("UPDATE embedding_config SET dimensions=? WHERE id=1", (dimension,))
                cx.execute("DELETE FROM chunks WHERE key=?", (document.key,))
                cx.executemany("INSERT INTO chunks VALUES (?,?,?,?)", [
                    (document.key, i, text, json.dumps(vector)) for i, (text, vector) in enumerate(zip(parts, vectors))])
                updated = timezone.now().isoformat()
                metadata = {**asdict(document), "updated_at": updated, "content_hash": document.digest,
                            "embedding": self.profile, "vector_dimensions": dimension}
                cx.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?)", (
                    document.key, document.digest, json.dumps(metadata, ensure_ascii=False), updated))
        return len(changed)

    def _check_vectors(self, cx, vectors):
        stored = cx.execute("SELECT dimensions FROM embedding_config WHERE id=1").fetchone()[0]
        if type(self.profile["dimensions"]) is int and stored != self.profile["dimensions"]:
            raise ProviderUnavailable("Stored embedding dimension metadata is invalid")
        if not isinstance(vectors, list) or not vectors or not isinstance(vectors[0], list) or not vectors[0]:
            raise ProviderUnavailable("Invalid vector data")
        size = len(vectors[0])
        if stored is not None and size != stored:
            raise ProviderUnavailable("Vector dimensions do not match this index")
        for vector in vectors:
            if (not isinstance(vector, list) or len(vector) != size
                    or any(type(x) not in (int, float) or not math.isfinite(x) for x in vector)
                    or not any(vector)):
                raise ProviderUnavailable("Invalid vector data")
        return size

    def ready(self, documents):
        with self.connect() as cx:
            return any(k in documents and documents[k].digest == digest for k, digest in cx.execute(
                "SELECT d.key,d.digest FROM documents d WHERE EXISTS (SELECT 1 FROM chunks c WHERE c.key=d.key)"))

    def search(self, query_vector, documents, threshold):
        result = []
        with self.connect() as cx:
            self._check_vectors(cx, [query_vector])
            for key, digest in cx.execute("SELECT key,digest FROM documents"):
                # Live metadata filtering BEFORE scoring: hide expired, inactive or modified records.
                if key not in documents or documents[key].digest != digest:
                    continue
                for text, vector in cx.execute("SELECT text,vector FROM chunks WHERE key=?", (key,)):
                    stored = json.loads(vector)
                    self._check_vectors(cx, [stored])
                    score = cosine(query_vector, stored)
                    if score >= threshold:
                        result.append((score, documents[key], text))
        return result


class RAGRetriever:
    def retrieve(self, question, *, limit=5):
        q = f" {normalize(question)} "
        from .catalog_queries import booking_guidance
        if any(x in q for x in (" huy lich ", " thanh toan ", " chan doan ", " chua benh ", " dieu tri benh ")) or (
                " dat lich " in q and not booking_guidance(question)):
            return []
        documents = public_documents()
        if is_service_list_question(question):
            # Listing is an authoritative catalog read, not a similarity guess.
            # Categories/products/promotions must never become bookable services.
            services = [d for d in documents.values() if d.source_type == "service"]
            return [Source(d.source_type, d.object_id, d.name, d.text[:2000], d.digest)
                    for d in services[:min(5, max(3, limit))]]
        from .catalog_queries import routed_documents
        routed = routed_documents(question, documents)
        if routed is not None:
            # Dynamic facts never need query embeddings or an index rebuild.
            return [Source(d.source_type, d.object_id, d.name, d.text[:2000], d.digest)
                    for d in routed[:min(5, max(3, limit))]]

        # Exact catalog matches avoid unnecessary remote query embeddings.
        exact = []
        query_tokens = set(q.split())
        for d in documents.values():
            keys = [
                normalize(d.name),
                normalize(d.name.split(" · ")[0])
            ]
            name_match = any(k and f" {k} " in q for k in keys)
            code_match = (
                d.source_type == "promotion"
                and normalize(d.name.split(" · ")[0]) in query_tokens
            )
            if name_match or code_match:
                exact.append(Source(
                    d.source_type, d.object_id,
                    d.name, d.text[:2000], d.digest
                ))
        if exact:
            return exact[:min(5, max(3, limit))]

        if not documents:
            return []
        index = VectorIndex()
        if not enabled("AI_RAG_INDEX_UPDATE_APPROVED") and not index.ready(documents):
            return []
        embedder = embedding_provider()
        # Includes only changed/new records; no full embedding rebuild on catalog changes.
        if enabled("AI_RAG_INDEX_UPDATE_APPROVED"):
            index.sync(documents, embedder)
        vector = embedder.embed_query(question) if hasattr(embedder, "embed_query") else embedder.embed([question])[0]
        # Re-read after embedding: an Admin change during inference invalidates the old snapshot.
        documents = public_documents()
        matches = index.search(vector, documents, float(option("AI_RAG_MIN_SIMILARITY", 0.35)))
        # Exact service names/promotion codes complement semantic paraphrase matching.
        for d in documents.values():
            keys = [normalize(d.name), normalize(d.name.split(" · ")[0])]
            if any(k and f" {k} " in q for k in keys):
                matches.append((1.1, d, d.text))
        matches.sort(key=lambda row: -row[0])
        selected, seen = [], set()
        for _, d, text in matches:
            if d.key in seen:
                continue
            seen.add(d.key)
            selected.append(Source(d.source_type, d.object_id, d.name, text[:2000], d.digest))
            if len(selected) == min(5, max(3, limit)):
                break
        return selected


def sources_current(sources):
    documents = public_documents()
    return all(s.fingerprint and f"{s.kind}:{s.object_id}" in documents
               and documents[f"{s.kind}:{s.object_id}"].digest == s.fingerprint for s in sources)
