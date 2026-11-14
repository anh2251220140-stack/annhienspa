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


def normalize(value):
    value = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in value if not unicodedata.combining(c))))


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
    object_id: int | None
    name: str
    text: str


class Retriever(Protocol):
    def retrieve(self, question: str, *, limit: int) -> list[Source]: ...


class Provider(Protocol):
    name: str

    def answer(self, question: str, sources: list[Source]) -> str: ...


class CatalogRetriever:
    """Small lexical retrieval adapter. It reads only public fields from the live catalog."""

    def retrieve(self, question, *, limit=3):
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
        service_overview = re.fullmatch(
            r"dich vu|tu van dich vu|(?:(?:spa|an nhien spa|an nhien|ben minh) )?co (?:nhung |cac )?dich vu (?:nao|gi)(?: vay| a| khong a)?",
            generic,
        )
        for item in Service.objects.filter(is_active=True, category__is_active=True).order_by("pk"):
            add("service", item.pk, item.name, f"{item.name}: {money(item.price)} · {item.duration_minutes} phút.",
                [item.name], bool(service_overview))
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
    return MockProvider()
