"""Conservative numeric equivalence, never arithmetic inference or unit conversion."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

TOKENS = re.compile(r"[+\-−]?(?:[.,]\d+(?:[.,:/–—-]\d+)*|\d+(?:[.,:/–—-]\d+)*)(?:[eE][+\-]?\d+)?")
GROUPED = re.compile(r"[1-9]\d{0,2}(?P<sep>[.,])\d{3}(?:(?P=sep)\d{3})*")
SUFFIX = re.compile(r"\s*(%|phần\s+trăm|vnd\b|vnđ\b|đồng\b|₫|đ\b|phút\b|giờ\b|kg\b|ml\b|cm\b|mm\b|km\b|lít\b|lit\b)", re.I)


@dataclass(frozen=True)
class Claim:
    kind: str
    value: object
    grouped_alternative: object = None


def claims(text):
    for match in TOKENS.finditer(text):
        raw = match.group()
        decimal_context = bool(re.search(r"(?:thập\s+phân|decimal)\s*(?:là\s*)?[:=]?\s*$",
                                         text[max(0, match.start() - 48):match.start()], re.I))
        suffix = SUFFIX.match(text, match.end())
        unit = suffix.group(1).lower() if suffix else ""
        if unit in {"%", "phần trăm"} or unit.startswith("phần"):
            kind = "percent"
        elif unit in {"vnd", "vnđ", "đồng", "₫", "đ"}:
            kind = "money"
        elif unit:
            kind = "unit:" + unit
        else:
            kind = "number"
        # Dates, clocks, ranges, exponents, versions and malformed compounds are
        # literal claims. Never turn 09:00 into 900 or 16/11/2026 into an amount.
        if any(c in raw.lstrip("+-−") for c in ":/–—-eE"):
            yield Claim("literal:" + kind, raw)
            continue
        sign = -1 if raw.startswith(("-", "−")) else 1
        unsigned = raw.lstrip("+-−")
        def exact(value):
            # Decimal construction is exact; arithmetic with the ambient decimal
            # precision could round a long invented number into an existing one.
            return Decimal(("-" if sign < 0 else "") + value)
        try:
            if unsigned.isdecimal():
                yield Claim(kind, exact(unsigned))
                continue
            if "." in unsigned and "," in unsigned:
                # The final separator is decimal; the other must be strictly
                # grouped in the integer part. Reject malformed 1,23.45.
                separator = "." if unsigned.rfind(".") > unsigned.rfind(",") else ","
                integer, fraction = unsigned.rsplit(separator, 1)
                other = "," if separator == "." else "."
                if not fraction.isdecimal() or not GROUPED.fullmatch(integer) or separator in integer:
                    raise ValueError
                value = exact(integer.replace(other, "") + "." + fraction)
                yield Claim(kind, value)
                continue
            count = unsigned.count(".") + unsigned.count(",")
            if count > 1:
                if not GROUPED.fullmatch(unsigned):
                    raise ValueError
                # Multiple separators can be grouped amounts, never percentages
                # or measured decimal values without unambiguous notation.
                if kind not in {"money", "number"} or decimal_context:
                    raise ValueError
                yield Claim(kind, exact(unsigned.replace(".", "").replace(",", "")))
                continue
            separator = "." if "." in unsigned else ","
            integer, fraction = unsigned.split(separator)
            decimal = exact(integer + "." + fraction)
            if GROUPED.fullmatch(unsigned) and kind in {"money", "number"} and not decimal_context:
                grouped = exact(integer + fraction)
                if kind == "money":
                    yield Claim(kind, grouped)
                else:
                    # Bare 1.234 is ambiguous. A source is NOT silently promoted
                    # to 1234. In an answer, allow grouping only when a definite
                    # integer in the retrieved sources anchors that value.
                    yield Claim("literal:number", raw, grouped)
            else:
                yield Claim(kind, decimal)
        except (InvalidOperation, ValueError):
            yield Claim("literal:" + kind, raw)


def numeric_claims_supported(answer, source_texts):
    available = {(claim.kind, claim.value) for text in source_texts for claim in claims(text)}
    for claim in claims(answer):
        allowed_kinds = ("number", "money") if claim.kind in {"number", "money"} else (claim.kind,)
        if any((kind, claim.value) in available for kind in allowed_kinds):
            continue
        if claim.grouped_alternative is not None and any(
                (kind, claim.grouped_alternative) in available for kind in ("number", "money")):
            continue
        return False
    return True
