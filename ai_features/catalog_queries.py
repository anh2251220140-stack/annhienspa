"""Live, read-only FR-21 catalog routing; vector search remains for other context."""
import re
from pathlib import Path

from django.conf import settings
from django.utils.html import strip_tags

from .chat_intents import normalize, is_service_list_question, service_query_terms


def website_information():
    """Reuse the published footer and shared hours, never invent opening days."""
    root = Path(settings.BASE_DIR) / "templates"
    page = (root / "pages/index.html").read_text(encoding="utf-8")
    footer = page.partition("KẾT NỐI VỚI AN NHIÊN")[2]
    footer = re.split(r"<div\b[^>]*\bfooter-bottom\b[^>]*>", footer, maxsplit=1)[0]
    hours = (root / "partials/user_hours.html").read_text(encoding="utf-8")
    footer = re.sub(r"{%\s*include\s+[\"']partials/user_hours.html[\"']\s*%}", hours, footer)
    return " ".join(strip_tags(re.sub(r"{%.*?%}", "", footer)).split())


def booking_guidance(question):
    q = normalize(question)
    return "dat lich" in q and any(x in q for x in ("cach", "huong dan", "quy trinh", "lam sao", "nhu the nao"))


def product_list_question(question):
    q = normalize(question)
    return q in {"san pham", "san pham cham soc"} or bool(re.fullmatch(
        r"(?:(?:spa|an nhien spa|ben minh) )?(?:co )?(?:nhung |cac )?"
        r"san pham(?: cham soc)? (?:nao|gi)(?: hien nay| vay| a| khong a)?", q
    ))


def promotion_question(question):
    q = normalize(question)
    return (any(x in q for x in ("khuyen mai", "uu dai", "giam gia", "voucher", "ma giam", "chuong trinh"))
            or bool(re.search(r"\bma [a-z0-9]+\b", q)))


def general_relaxation_question(question):
    return bool(re.fullmatch(
        r"(?:(?:toi (?:met moi|muon thu gian)|spa|ben minh) )?"
        r"(?:co )?(?:dich vu|lieu trinh) thu gian (?:nao|gi)(?: vay| a)?",
        normalize(question),
    ))


def routed_documents(question, documents):
    """None means semantic retrieval; [] means recognized but no matching record.

    Match meaningful query phrases, not every conversational word. Category names
    may help locate real services, but category records are never service answers.
    """
    q = normalize(question)
    q = re.sub(r"\bda am\b", "da nong", q)
    kinds = set()
    if promotion_question(q):
        kinds.add("promotion")
    information_requested = any(x in q for x in ("may gio", "gio hoat dong", "mo cua", "dong cua", "chu nhat", "cuoi tuan", "ngay nghi", "thu bay",
                                                "dia chi", "lien he", "o dau", "dien thoai"))
    if information_requested:
        kinds.add("spa")
    if booking_guidance(question):
        kinds.add("spa")
    if any(x in q for x in ("san pham", "my pham", "thuong hieu", "tinh dau")):
        kinds.add("product")
    listing = is_service_list_question(question)
    if listing:
        return [d for d in documents.values() if d.source_type == "service"]
    if general_relaxation_question(q):
        return [d for d in documents.values()
                if d.source_type == "service" and " thu gian " in f" {normalize(d.name)} "]
    if (("product" not in kinds or "dich vu" in q or "lieu trinh" in q)
            and any(x in q for x in ("dich vu", "lieu trinh", "massage", "mat xa", "cham soc", "cap am",
                                    "duong am", "goi dau", "da nong"))):
        kinds.add("service")
    # Include exact entity names/codes even in combined questions.
    exact = [d for d in documents.values() if d.source_type in {"service", "product", "promotion"}
             and any(k and f" {k} " in f" {q} " for k in
                     (normalize(d.name), normalize(d.name.split(" · ")[0])))]
    kinds.update(d.source_type for d in exact)
    if not kinds:
        return None
    groups = []
    for kind in ("service", "promotion", "product", "spa"):
        if kind not in kinds:
            continue
        pool = [d for d in documents.values() if d.source_type == kind]
        if kind == "spa":
            pool = [d for d in pool if (d.object_id == "booking" and booking_guidance(question))
                    or (d.object_id != "booking" and information_requested)]
        specific = [d for d in exact if d.source_type == kind]
        if kind == "promotion":
            code = re.search(r"\bma (?!giam\b|uu\b)([a-z0-9]+)\b", q)
            if code:
                pool = [d for d in pool if normalize(d.name.split(" · ")[0]) == code[1]
                        or f"({code[1]})" in d.text.lower()]
        if kind in {"service", "product"} and not specific and not (kind == "service" and listing):
            terms = service_query_terms(q) - {
                "lam", "on", "minh", "ben", "xin", "biet", "them", "chi", "tiet", "the", "ve", "sao",
                "hien", "nay", "dang", "nhu", "theo", "san", "pham", "cham", "soc", "da",
                "ngoai", "ra", "cung", "hay", "rat", "nhung", "mot", "vui", "long", "giup", "nhe",
                "phi", "loi", "ich", "cong", "keo", "dai", "voi",
            }
            aliases = {"mat xa": "massage", "duong am": "cap am", "rua mat": "lam sach"}
            expanded = q
            for old, new in aliases.items():
                expanded = expanded.replace(old, new)
            if kind == "service" and "massage" in expanded:
                pool = [d for d in pool if "massage" in normalize(d.name).split()]
            if kind == "service" and "da nong" in expanded:
                pool = [d for d in pool if " da nong " in f" {normalize(d.name)} "]
            # Shared benefit words (e.g. hydration) cannot override an explicit
            # body area: face care must not become hair/body care.
            if "da mat" in expanded:
                pool = [d for d in pool if "mat" in normalize(d.name).split()]
            elif any(x in expanded for x in ("toc", "da dau", "goi dau")):
                pool = [d for d in pool if any(x in normalize(d.name).split() for x in ("toc", "dau"))]
            elif "toan than" in expanded or "co the" in expanded:
                pool = [d for d in pool if any(x in normalize(d.name) for x in ("toan than", "co the", "body"))]
            terms |= set(expanded.split()) & {"massage", "mat", "toc", "am", "chan", "tay", "dau"}
            scored = [(len(terms & set(normalize(d.name).split())), d) for d in pool]
            specific = [d for score, d in sorted(scored, key=lambda row: -row[0]) if score >= 2
                        or (score == 1 and len(terms) == 1)]
            # Broad product/service questions list their real records. A specific
            # unknown treatment must not silently become the entire catalog.
            broad = (kind == "product" and product_list_question(q)) or (
                kind == "service" and any(x in q for x in ("dich vu nao", "dich vu gi", "cac dich vu", "nhung dich vu")))
            pool = specific if not broad else pool
        elif specific and not (kind == "service" and listing):
            pool = specific
        groups.append(pool)
    # Reserve a source for each requested topic before filling the source limit.
    return [group[i] for i in range(max(map(len, groups), default=0)) for group in groups if i < len(group)]
