"""Read-only retrieval and a local provider for the first chat release."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.utils import timezone

from core.catalog_data import _promotion_discount_label, money
from products.models import CareProduct
from promotions.models import Promotion
from services.models import Service

from .chat_intents import is_service_list_question, normalize, is_service_request_question, service_query_terms


# Reject obvious secrets and private identifiers before storage or retrieval.
PRIVATE_INPUT = re.compile(
    r"-----BEGIN |\b(?:sk-(?:proj-)?[a-z0-9_-]{8,}|AIza[a-z0-9_-]{25,}|eyJ[a-z0-9_-]+\.[a-z0-9_-]+\.[a-z0-9_-]+)\b"
    r"|\b(?:bearer\s+\S+|(?:mat khau|password|passcode|api[_ -]?key|secret|token|otp|ma pin)\b)"
    r"|[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?<!\w)(?:\+?\d[ .()-]?){9,}\d?(?!\w)", re.IGNORECASE,
)


def contains_private_input(text):
    plain = "".join(c for c in unicodedata.normalize("NFKD", text.lower().replace("đ", "d"))
                    if not unicodedata.combining(c) and unicodedata.category(c) != "Cf")
    return bool(PRIVATE_INPUT.search(plain))


@dataclass(frozen=True)
class Source:
    kind: str
    object_id: int | str | None
    name: str
    text: str
    fingerprint: str = ""


class Retriever(Protocol):
    def retrieve(self, question: str, *, limit: int) -> list[Source]: ...


class Provider(Protocol):
    name: str

    def answer(self, question: str, sources: list[Source]) -> str: ...


class CatalogRetriever:
    """Small lexical retrieval adapter. It reads only public fields from the live catalog."""

    def retrieve(self, question, *, limit=3):
        from .catalog_queries import booking_guidance
        q = f" {normalize(question)} "
        if any(x in q for x in (" huy lich ", " thanh toan ", " chan doan ", " chua benh ", " dieu tri benh ")) or (
                " dat lich " in q and not booking_guidance(question)):
            return []
        if is_service_list_question(question):
            return [Source("service", s.pk, s.name,
                           f"{s.name}: {money(s.price)} · {s.duration_minutes} phút.")
                    for s in Service.objects.filter(is_active=True, category__is_active=True).order_by("pk")[:limit]]
        from .rag import public_documents
        from .catalog_queries import routed_documents
        documents = public_documents()
        routed = routed_documents(question, documents)
        if routed is not None:
            return [Source(d.source_type, d.object_id, d.name, d.text[:2000], d.digest)
                    for d in routed[:limit]]
        query = f" {normalize(question)} "
        # This release only returns catalog facts for recognized questions.
        if any(term in query for term in (" dat lich ", " huy lich ", " thanh toan ", " chan doan ",
                                          " chua benh ", " dieu tri benh ")):
            return []
        info = settings.AI_CHAT_SPA_INFORMATION.strip()
        if info and any(term in query for term in (" gio mo cua ", " dia chi ", " lien he ", " o dau ")):
            return [Source("spa", None, "Thông tin Spa", info)]

        ranked = []

        def add(kind, object_id, name, summary, keys, broad=False):
            score = max((len(key) for key in map(normalize, keys) if key and f" {key} " in query), default=0)
            if score or broad:
                ranked.append((score, Source(kind, object_id, name, summary)))

        generic = query.strip()
        service_overview = is_service_list_question(question)
        if not service_overview and is_service_request_question(question):
            terms = service_query_terms(question)
            for item in Service.objects.filter(
                is_active=True, category__is_active=True
            ).order_by("pk"):
                if terms.intersection(set(normalize(item.name).split())):
                    add("service", item.pk, item.name,
                        f"{item.name}: {money(item.price)} · {item.duration_minutes} phút.",
                        [item.name])
            return [source for _, source in ranked[:limit]]
        for item in Service.objects.filter(is_active=True, category__is_active=True).order_by("pk"):
            add("service", item.pk, item.name, f"{item.name}: {money(item.price)} · {item.duration_minutes} phút.",
                [item.name], bool(service_overview))
        if service_overview:
            return [source for _, source in ranked[:limit]]
        for item in CareProduct.objects.filter(is_active=True).order_by("pk"):
            add("product", item.pk, item.name, f"{item.name}: {item.description}", [item.name],
                generic in {"san pham", "san pham cham soc", "spa co san pham nao"})
        today = timezone.localdate()
        for item in Promotion.objects.filter(is_active=True, start_date__lte=today, end_date__gte=today).order_by("pk"):
            discount = _promotion_discount_label(item.discount_type, item.discount_value)
            add("promotion", item.pk, item.name,
                f"{item.name} ({item.code}): {discount}, hiệu lực đến {item.end_date:%d/%m/%Y}. "
                "Xem điều kiện áp dụng trên trang Khuyến mãi.", [item.name, item.code, *(item.aliases or "").splitlines()],
                generic in {"khuyen mai", "khuyen mai hien co", "uu dai"})
        ranked.sort(key=lambda match: -match[0])
        return [source for _, source in ranked[:limit]]


class MockProvider:
    """Echoes retrieved facts locally so UI and persistence can be exercised without inference."""

    name = "local-mock-v1"

    def answer(self, question, sources):
        return "\n".join(source.text[:600] for source in sources)


def get_provider() -> Provider:
    from .config import option
    if option("AI_PROVIDER", "mock") != "mock":
        from .provider_factory import external_provider
        return external_provider()
    return MockProvider()
