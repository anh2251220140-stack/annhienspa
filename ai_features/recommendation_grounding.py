"""FR-22 only: typed numeric facts, exact values and service-scoped history.

No ORM/network/index access. The shared FR-21/23 grounder is intentionally unchanged.
Failures contain fixed codes, never the rejected text or personal data.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
import re
import unicodedata

NUMBER = r"[+\-−]?(?:[.,]\d+|\d+(?:[.,]\d+|[ \u00a0\u202f]\d+)*)(?:[eE][+\-]?\d+)?"
WORDS = r"(?:khong|mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi|tram|linh|le|nua)"
WORD_NUMBER = rf"{WORDS}(?:\s+{WORDS})*(?:\s+(?:tu|lam))?"
UNITS = r"(?:phan\s+tram|percent|trieu(?:\s+(?:dong|vnd))?|nghin(?:\s+(?:dong|vnd))?|ngan(?:\s+(?:dong|vnd))?|vnd|dong|phut|minutes?|min|gio|tieng|hours?|lan|luot|buoi|tuoi|buoc|ml|kg|cm|mm|lit|%|₫|[dkhpg])"
TOKEN = re.compile(
    rf"(?P<date>\b\d{{4}}-\d{{1,2}}-\d{{1,2}}\b|\b\d{{1,2}}[/.\-]\d{{1,2}}[/.\-]\d{{4}}\b|\bngay\s+\d{{1,2}}\s+thang\s+\d{{1,2}}\s+nam\s+\d{{4}}\b)"
    rf"|(?P<millions>{NUMBER}|{WORD_NUMBER})\s*trieu\s*(?P<thousands>{NUMBER}|{WORD_NUMBER})\s*(?:nghin|ngan|k)(?![a-z])(?:\s*(?:dong|vnd|d)(?![a-z]))?"
    rf"|(?P<hours>{NUMBER}|{WORD_NUMBER})\s*(?:gio|tieng|hours?|h)(?![a-z])\s*(?:va\s+)?(?P<minutes>{NUMBER}|{WORD_NUMBER})\s*(?:phut|minutes?|min|p)(?![a-z])"
    rf"|(?P<number>{NUMBER})\s*(?P<unit>{UNITS}(?![a-z]))?"
    rf"|\b(?P<words>{WORD_NUMBER})\s+(?P<wordunit>{UNITS}(?![a-z]))", re.I)
GROUPED = re.compile(r"[1-9]\d{0,2}(?P<sep>[.,])\d{3}(?:(?P=sep)\d{3})*")


def fold(text):
    text = unicodedata.normalize("NFKC", str(text)).lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


def word_value(raw):
    if raw == "nua":
        return Decimal("0.5")
    units = dict(khong=0, mot=1, hai=2, ba=3, bon=4, tu=4, nam=5, lam=5, sau=6, bay=7, tam=8, chin=9)
    words = raw.split()
    hundreds = 0
    if "tram" in words:
        if len(words) < 2 or words[1] != "tram" or units.get(words[0], 0) == 0:
            raise ValueError
        hundreds = units[words[0]] * 100
        words = words[2:]
        if words[:1] in (["linh"], ["le"]):
            words = words[1:]
    if not words:
        return Decimal(hundreds)
    if len(words) == 1:
        return Decimal(hundreds + (10 if words[0] == "muoi" else units[words[0]]))
    if words[0] == "muoi" and len(words) == 2:
        return Decimal(hundreds + 10 + units[words[1]])
    if len(words) in (2, 3) and words[1] == "muoi" and units.get(words[0], 0) >= 2:
        return Decimal(hundreds + units[words[0]] * 10 + (units[words[2]] if len(words) == 3 else 0))
    raise ValueError


def decimal_value(raw, *, money=False):
    """Exact VN/English decimals and strict thousands groups, never float rounding."""
    raw = raw.strip().replace("−", "-")
    if not re.search(r"\d", raw):
        return word_value(raw)
    if len(raw) > 64 or re.search(r"[eE]", raw):
        raise ValueError
    sign = "-" if raw.startswith("-") else ""
    raw = raw.lstrip("+-")
    if " " in raw:
        if not money or not re.fullmatch(r"[1-9]\d{0,2}(?: \d{3})+(?:[.,]\d{1,2})?", raw):
            raise ValueError
        raw = raw.replace(" ", "")
    if "." in raw and "," in raw:
        sep = "." if raw.rfind(".") > raw.rfind(",") else ","
        integer, fraction = raw.rsplit(sep, 1)
        if not money or not GROUPED.fullmatch(integer) or sep in integer or not fraction.isdecimal():
            raise ValueError
        raw = integer.replace(",", "").replace(".", "") + "." + fraction
    elif raw.count(".") + raw.count(",") > 1:
        if not money or not GROUPED.fullmatch(raw):
            raise ValueError
        raw = raw.replace(".", "").replace(",", "")
    elif money and GROUPED.fullmatch(raw):
        raw = raw.replace(".", "").replace(",", "")
    else:
        raw = raw.replace(",", ".")
    value = Decimal(sign + raw)
    if not value.is_finite():
        raise ValueError
    return value


def prefix(text, position):
    return re.split(r"[.!?;]\s+|\n", text[:position])[-1][-120:]


def money_role(text, position):
    context = prefix(text, position).rsplit(",", 1)[-1]
    labels = [(m.start(), "budget") for m in re.finditer(r"\bngan sach\b", context)]
    labels += [(m.start(), "price") for m in re.finditer(r"\b(?:gia|chi phi|muc phi|don gia)\b", context)]
    return max(labels)[1] if labels else "price"


def decode(match, text):
    if match["date"]:
        digits = list(map(int, re.findall(r"\d+", match["date"])))
        y, m, d = digits if digits[0] >= 1000 else digits[::-1]
        return "date", date(y, m, d), ""
    if match["millions"]:
        millions, thousands = decimal_value(match["millions"], money=True), decimal_value(match["thousands"], money=True)
        if millions < 0 or not 0 <= thousands < 1000:
            raise ValueError
        return "money", millions * 1000000 + thousands * 1000, ""
    if match["hours"]:
        h, m = decimal_value(match["hours"], money=True), decimal_value(match["minutes"], money=True)
        if h < 0 or not 0 <= m < 60:
            raise ValueError
        return "duration", h * 60 + m, ""
    raw, unit = match["number"] or match["words"], (match["unit"] or match["wordunit"] or "").strip()
    unit = " ".join(unit.split())
    context = prefix(text, match.start())
    is_money = unit in {"vnd", "dong", "d", "₫", "k"} or unit.startswith(("nghin", "ngan", "trieu"))
    if not unit and re.search(r"\b(?:gia|chi phi|muc phi|ngan sach)\s+(?:(?:la|chi|tu|khoang|toi da)\s+)?$", context):
        is_money = True
    integer_unit = unit in {"lan", "luot", "buoi", "gio", "tieng", "hour", "hours", "h", "phut", "minute", "minutes", "min", "p"}
    value = decimal_value(raw, money=is_money or integer_unit)
    if re.match(r"\s*ruoi\b", text[match.end():]):
        value += Decimal("0.5")
    if is_money:
        scale = 1000000 if unit.startswith("trieu") else 1000 if unit == "k" or unit.startswith(("nghin", "ngan")) else 1
        return "money", value * scale, ""
    if unit in {"gio", "tieng", "hour", "hours", "h"}:
        return "duration", value * 60, ""
    if unit in {"phut", "minute", "minutes", "min", "p"}:
        return "duration", value, ""
    if unit in {"lan", "luot", "buoi"}:
        return "count", value, ""
    if unit in {"%", "phan tram", "percent"}:
        return "percent", value, ""
    if unit:
        return "measure", value, unit
    if re.search(r"\bnam\s+$", context):
        return "year", value, ""
    return "bare", value, ""


@dataclass(frozen=True)
class NumericCheck:
    code: str | None
    # Used only for the existing privacy check; never logged or persisted.
    privacy_text: str = ""


def check_recommendation_numbers(reason, service, budget, history, candidates):
    text = fold(reason)
    if re.search(r"\b(?:nan|inf|infinity)\b|[+\-−]{2,}\s*\d|\d[.,]{2,}\d", text):
        return NumericCheck("MALFORMED_NUMBER")
    entities = {s.pk: s for s in candidates}
    entities[service.pk] = service
    records = {r["serviceId"]: r for r in history}
    named = []
    protected = []
    # Permit natural, explicitly qualified names only when the suffix uniquely
    # identifies one candidate. Never infer an entity merely from a matching value.
    aliases = {}
    for s in entities.values():
        words = fold(s.name).split()
        for length in range(2, min(4, len(words)) + 1):
            suffix = " ".join(words[-length:])
            for label in ("dich vu ", "lieu trinh "):
                aliases.setdefault(label + suffix, set()).add(s.pk)
    for s in entities.values():
        name = fold(s.name)
        names = {name} | {alias for alias, ids in aliases.items() if ids == {s.pk}}
        for name in names - {""}:
            for m in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text):
                named.append((m.start(), m.end(), s))
                protected.append((m.start(), m.end()))

    def scoped(position, end):
        def resolve(rows, key, reverse):
            ordered = sorted(rows, key=key, reverse=reverse)
            best = key(ordered[0])
            tied = {row[2].pk:row[2] for row in ordered if key(row) == best}
            return service if service.pk in tied else next(iter(tied.values())) if len(tied) == 1 else None
        boundary = position - len(prefix(text, position))
        after = [(start, -(stop-start), s) for start, stop, s in named if start >= end and start-end <= 32
                 and text[end:start].strip() in {"", "cua", "cho"}]
        if after:
            return resolve(after, lambda row: row[:2], False)
        names = [(end, end-start, s) for start, end, s in named if start >= boundary and end <= position]
        return resolve(names, lambda row: row[:2], True) if names else service

    def public_facts(s):
        return fold(" ".join((s.description[:500], s.benefits[:500], s.suitable[:300], s.steps[:300], s.note[:300])))

    def context_words(value):
        return set(re.findall(r"[a-z]+", value)) - {
            "co", "la", "va", "cua", "cho", "voi", "theo", "trong", "phan", "tram", "gia", "dich", "vu",
            "ml", "kg", "cm", "mm", "lit", "tuoi", "buoc", "g", "giup", "ho", "tro", "cham", "soc", "da",
            "cong", "thuc", "chua", "tang", "giam", "hieu", "qua"}

    def supported_public(kind, value, unit, s, position, end):
        public = public_facts(s)
        answer_words = context_words(text[max(0, position-24):end+24])
        for source in TOKEN.finditer(public):
            try:
                if decode(source, public) != (kind, value, unit):
                    continue
            except (ValueError, InvalidOperation, KeyError):
                continue
            source_words = context_words(public[max(0, source.start()-24):source.end()+24])
            bare_percent = not re.search(r"[a-z]", text[:position] + text[end:])
            if answer_words & source_words or not answer_words and not source_words and bare_percent:
                return True
        return False

    masked = list(text)
    with localcontext() as ctx:
        ctx.prec = 100
        for token in TOKEN.finditer(text):
            if token["words"] == "sau" and unicodedata.normalize("NFKC", reason).lower()[token.start():token.start()+3] == "sau":
                # "Sau lần trước" is a preposition; "sáu lần" is a count.
                continue
            if any(start <= token.start() < end for start, end in protected):
                continue
            s = scoped(token.start(), token.end())
            if s is None:
                return NumericCheck("AMBIGUOUS_SERVICE_REFERENCE")
            public = public_facts(s)
            # Digits inside an exact sourced identifier (e.g. B5) are not quantities.
            identifier = re.search(r"\w*[a-z]\d\w*", text[max(0, token.start()-25):token.end()+25])
            if identifier and not token["hours"] and not token["millions"]:
                offset = max(0, token.start()-25)
                if offset+identifier.start() <= token.start() and token.end() <= offset+identifier.end():
                    if re.search(r"(?<!\w)"+re.escape(identifier.group())+r"(?!\w)", public):
                        continue
                    return NumericCheck("UNSUPPORTED_IDENTIFIER")
            try:
                kind, value, unit = decode(token, text)
            except (ValueError, InvalidOperation, KeyError):
                return NumericCheck("MALFORMED_NUMBER")
            context = prefix(text, token.start())
            # A valid value in the wrong role is still unsupported (e.g. a
            # history date written as a price, or minutes written as currency).
            if re.search(r"\b(?:gia|chi phi|ngan sach)\s+(?:(?:la|chi|tu|khoang|toi da)\s+)?$", context):
                if kind != "money":
                    return NumericCheck("NUMERIC_ROLE_MISMATCH")
            if re.search(r"\bthoi luong\s+(?:la\s+)?$", context) and kind != "duration":
                return NumericCheck("NUMERIC_ROLE_MISMATCH")
            record = records.get(s.pk)
            if kind == "money":
                expected = Decimal(str(budget)) if budget is not None and money_role(text, token.start()) == "budget" else Decimal(str(s.price))
                if money_role(text, token.start()) == "budget" and budget is None:
                    return NumericCheck("BUDGET_NOT_CONFIGURED")
                if value != expected:
                    return NumericCheck("PRICE_OR_BUDGET_MISMATCH")
            elif kind == "duration":
                if value != Decimal(s.duration_minutes):
                    return NumericCheck("DURATION_MISMATCH")
            elif kind == "count":
                if not record or value != Decimal(record["count"]):
                    return NumericCheck("HISTORY_COUNT_MISMATCH")
            elif kind in {"date", "year"}:
                dates = {date.fromisoformat(record[k]) for k in ("firstUsed", "lastUsed")} if record else set()
                context = prefix(text, token.start())
                if record and "gan nhat" in context:
                    dates = {date.fromisoformat(record["lastUsed"])}
                elif record and "dau tien" in context:
                    dates = {date.fromisoformat(record["firstUsed"])}
                if value not in (dates if kind == "date" else {Decimal(d.year) for d in dates}):
                    return NumericCheck("HISTORY_DATE_MISMATCH")
            elif kind in {"percent", "measure"}:
                if not supported_public(kind, value, unit, s, token.start(), token.end()):
                    return NumericCheck("UNSUPPORTED_PERCENT_OR_MEASURE")
            else:
                return NumericCheck("UNSCOPED_NUMBER")
            masked[token.start():token.end()] = " " * (token.end()-token.start())
    return NumericCheck(None, "".join(masked))
