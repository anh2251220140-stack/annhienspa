"""Pure FR-21 intent helpers; no ORM, provider or index access."""
import re
import unicodedata


def normalize(value):
    value = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in value if not unicodedata.combining(c))))



def is_service_list_question(question):
    return bool(re.fullmatch(
        r"dich vu|tu van dich vu|(?:(?:spa|an nhien spa|an nhien|ben minh) )?co (?:nhung |cac )?dich vu (?:nao|gi)(?: vay| a| khong a)?"
        r"|(?:ke ten|liet ke) (?:cac |nhung )?(?:dich vu|lieu trinh)(?: tai spa| cua spa)?"
        r"|(?:toi muon )?(?:xem )?danh sach dich vu(?: tai spa| cua spa)?",
        normalize(question),
    ))


_SERVICE_QUERY_STOP_WORDS = {
    "toi", "muon", "tim", "hieu", "co", "nao", "gi", "vay", "a", "khong",
    "spa", "an", "nhien", "dich", "vu", "lieu", "trinh",
    "gia", "bao", "nhieu", "ban", "huong", "dan", "su", "dung",
    "tu", "van", "cho", "tai",
    "thoi", "gian", "thuc", "hien", "lau", "va",
    "nhung", "khach", "hang",
    "phu", "hop", "voi", "doi", "tuong", "la", "duoc", "ai",
}

def is_service_request_question(question):
    value = normalize(question)
    return any(phrase in value for phrase in (
        "cham soc da mat",
        "cap am da mat",
        "duong am da mat",
        "lam sach da mat",
        "phuc hoi da mat",
    ))

def service_query_terms(question):
    return set(normalize(question).split()) - _SERVICE_QUERY_STOP_WORDS
