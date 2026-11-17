"""Synthetic Gemini probes only; never imports production settings or business rows.

These probes exercise the shared adapter/vector index, not authenticated HTTP flows.
They do not prove a Google project's billing tier: the operator must verify it.
"""
from contextlib import ExitStack, contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, field
import ipaddress
import json
import logging
import re
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
CONFIRMATION = "FREE TIER VERIFIED; BILLING DISABLED"
FEATURES = {"fr21": 3, "fr22": 1, "fr23": 1}
STAGE_CODES = frozenset({
    "GENERATION_STARTED", "HTTP_DISPATCH_STARTED", "HTTP_RESPONSE_RECEIVED", "HTTP_RESPONSE_NOT_OK", "HTTP_RESPONSE_OK",
    "HTTP_RESPONSE_NOT_RECEIVED", "SDK_RESPONSE_RECEIVED", "RESPONSE_TEXT_READ_FAILED", "RESPONSE_TEXT_EMPTY",
    "RESPONSE_TEXT_INVALID", "RESPONSE_TEXT_TOO_LONG", "JSON_PARSE_FAILED", "JSON_NOT_OBJECT",
    "JSON_OBJECT_PARSED", "ANSWER_MISSING", "ANSWER_INVALID", "SOURCE_LIST_INVALID", "SOURCE_ID_INVALID",
    "NUMERIC_GROUNDING_FAILED", "ANSWER_VALIDATED", "FINAL_ANSWER_NOT_CREATED", "FINAL_ANSWER_BUILD_FAILED",
    "OUTPUT_PRIVACY_REJECTED",
    "REQUEST_TIMEOUT_OR_BUDGET_EXHAUSTED", "STRUCTURED_RESPONSE_FAILED", "REQUEST_NOT_SENT", "SDK_GENERATION_FAILED",
})
FAILURE_STAGE_CODES = STAGE_CODES - {
    "GENERATION_STARTED", "HTTP_DISPATCH_STARTED", "HTTP_RESPONSE_RECEIVED", "HTTP_RESPONSE_OK",
    "SDK_RESPONSE_RECEIVED", "JSON_OBJECT_PARSED", "ANSWER_VALIDATED",
}


class SafetyStop(RuntimeError):
    pass


def safe_error_details(details):
    """Keep only explicit public ErrorInfo labels and known request field paths."""
    if not isinstance(details, list):
        return []
    reasons = {"API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_SERVICE_BLOCKED",
               "API_KEY_HTTP_REFERRER_BLOCKED", "API_KEY_IP_ADDRESS_BLOCKED",
               "API_KEY_ANDROID_APP_BLOCKED", "API_KEY_IOS_APP_BLOCKED",
               "SERVICE_DISABLED", "BILLING_DISABLED", "CONSUMER_INVALID",
               "RATE_LIMIT_EXCEEDED", "RESOURCE_QUOTA_EXCEEDED", "ACCESS_TOKEN_EXPIRED",
               "ACCESS_TOKEN_SCOPE_INSUFFICIENT", "IAM_PERMISSION_DENIED"}
    domains = {"googleapis.com", "generativelanguage.googleapis.com"}
    fields = {"model", "contents", "contents[].role", "contents[].parts", "contents[].parts[].text",
              "systemInstruction", "systemInstruction.role", "systemInstruction.parts", "systemInstruction.parts[].text",
              "generationConfig", *["generationConfig." + name for name in (
                  "temperature", "topP", "topK", "frequencyPenalty", "presencePenalty", "maxOutputTokens",
                  "responseMimeType", "responseSchema", "responseJsonSchema", "thinkingConfig", "audioTranscriptionConfig")],
              "generationConfig.thinkingConfig.thinkingBudget", "generationConfig.thinkingConfig.thinkingLevel"}
    aliases = {"system_instruction": "systemInstruction", "generation_config": "generationConfig",
               "max_output_tokens": "maxOutputTokens", "response_mime_type": "responseMimeType",
               "response_schema": "responseSchema", "response_json_schema": "responseJsonSchema",
               "top_p": "topP", "top_k": "topK", "frequency_penalty": "frequencyPenalty",
               "presence_penalty": "presencePenalty", "thinking_config": "thinkingConfig",
               "thinking_budget": "thinkingBudget", "thinking_level": "thinkingLevel"}
    aliases["audio_transcription_config"] = "audioTranscriptionConfig"
    result = []
    for detail in details[:16]:
        if not isinstance(detail, dict):
            continue
        if detail.get("@type") == "type.googleapis.com/google.rpc.ErrorInfo":
            item = {"type": "google.rpc.ErrorInfo"}
            for key, allowlist in (("reason", reasons), ("domain", domains)):
                value = detail.get(key)
                if isinstance(value, str) and value in allowlist:
                    item[key] = value
            metadata = detail.get("metadata")
            if isinstance(metadata, dict) and metadata.get("service") == "generativelanguage.googleapis.com":
                item["service"] = "generativelanguage.googleapis.com"
            if len(item) > 1:
                result.append(item)
        elif detail.get("@type") == "type.googleapis.com/google.rpc.BadRequest":
            violations = detail.get("fieldViolations")
            if not isinstance(violations, list):
                continue
            safe_fields = []
            for violation in violations[:32]:
                path = violation.get("field") if isinstance(violation, dict) else None
                if not isinstance(path, str) or len(path) > 128:
                    continue
                path = re.sub(r"\[\d{1,4}\]", "[]", path)
                path = ".".join(aliases.get(segment, segment) for segment in path.split("."))
                if path in fields and path not in safe_fields:
                    safe_fields.append(path)
            if safe_fields:
                result.append({"type": "google.rpc.BadRequest", "fields": safe_fields})
    return result


def safe_google_message(message, error_type=None):
    """Return technical labels, not a redacted copy of untrusted free text.

    Only recognisable error templates and explicit public field names survive.
    Numbers, quoted values, URLs, payload excerpts and arbitrary words never do.
    """
    kinds = {"INVALID_ARGUMENT", "FAILED_PRECONDITION", "OUT_OF_RANGE", "UNAUTHENTICATED",
             "PERMISSION_DENIED", "RESOURCE_EXHAUSTED", "NOT_FOUND", "INTERNAL", "UNAVAILABLE",
             "DEADLINE_EXCEEDED", "UNKNOWN", "CANCELLED", "ALREADY_EXISTS", "ABORTED", "DATA_LOSS"}
    kind = error_type if isinstance(error_type, str) and error_type in kinds else "HTTP_ERROR"
    withheld = kind + ": source message withheld (unrecognised or unavailable)."
    if not isinstance(message, str) or not message.strip():
        return withheld
    try:
        if len(message.encode("utf-8")) > 8192:
            return withheld
    except UnicodeError:
        return withheld
    text = message.strip()
    templates = (
        (r"^Invalid JSON payload received\b", "INVALID_JSON_PAYLOAD"),
        (r"^(?:Invalid JSON payload received[^\n]{0,200}\.\s*)?Unknown name\b", "UNKNOWN_JSON_FIELD"),
        (r"^(?:Unknown name[^\n]{0,200}[:.]\s*)?Cannot find field\b", "UNKNOWN_JSON_FIELD"),
        (r"^API key (?:not valid|is invalid|is not valid)\b", "INVALID_API_KEY"),
        (r"^(?:Request contains an invalid argument|Invalid argument)\b", "INVALID_ARGUMENT"),
        (r"^(?:Unable to submit request[^\n]{0,300}|[A-Za-z_.]+[^\n]{0,80})"
         r"(?:out of range|supported range)\b", "VALUE_OUT_OF_RANGE"),
        (r"^(?:The )?(?:model|request|JSON mode|system instruction|developer instruction)\b"
         r"[^\n]{0,150}(?:not supported|does not support|not enabled)\b", "UNSUPPORTED_REQUEST_FEATURE"),
        (r"^(?:generationConfig\.|generation_config\.)?"
         r"(?:responseMimeType|response_mime_type|maxOutputTokens|max_output_tokens|temperature|topP|top_p|topK|top_k|"
         r"audioTranscriptionConfig|audio_transcription_config|thinkingConfig|thinking_config|thinkingLevel|thinking_level)"
         r"\b[^\n]{0,120}(?:not supported|unsupported|not allowed|cannot be used)\b", "UNSUPPORTED_PARAMETER"),
        (r"^(?:GenerateContentRequest\.)?(?:contents|model|systemInstruction|system_instruction)"
         r"\b[^\n]{0,100}(?:required|not specified|must not be empty)\b", "MISSING_REQUIRED_FIELD"),
        (r"^(?:The )?(?:last|final)\b[^\n]{0,120}\bmodel\b[^\n]{0,100}"
         r"(?:not supported|not allowed|must be|cannot)\b", "INVALID_FINAL_TURN"),
    )
    labels = list(dict.fromkeys(label for pattern, label in templates if re.search(pattern, text, re.I)))
    if not labels:
        return withheld
    parameters = {name: "generationConfig." + canonical for name, canonical in (
        ("temperature", "temperature"), ("topP", "topP"), ("top_p", "topP"), ("topK", "topK"), ("top_k", "topK"),
        ("maxOutputTokens", "maxOutputTokens"), ("max_output_tokens", "maxOutputTokens"),
        ("responseMimeType", "responseMimeType"), ("response_mime_type", "responseMimeType"),
        ("responseSchema", "responseSchema"), ("response_schema", "responseSchema"),
        ("responseJsonSchema", "responseJsonSchema"), ("response_json_schema", "responseJsonSchema"),
        ("thinkingConfig", "thinkingConfig"), ("thinking_config", "thinkingConfig"),
        ("audioTranscriptionConfig", "audioTranscriptionConfig"), ("audio_transcription_config", "audioTranscriptionConfig"))}
    fields = []
    tokens = re.finditer(r"(?<![\w.])[A-Za-z_]\w*(?:\[\d{1,4}\])?(?:\.[A-Za-z_]\w*(?:\[\d{1,4}\])?)*", text)
    for match in tokens:
        token = match.group()
        if token.startswith("GenerateContentRequest."):
            token = token[len("GenerateContentRequest."):]
        token = parameters.get(token, token)
        projected = safe_error_details([{"@type": "type.googleapis.com/google.rpc.BadRequest",
                                         "fieldViolations": [{"field": token}]}])
        if projected:
            for name in projected[0]["fields"]:
                if name not in fields:
                    fields.append(name)
        if len(fields) >= 16:
            break
    result = kind + ": " + "; ".join(labels)
    if fields:
        result += "; fields=" + ", ".join(fields)
    return result + ". Original text/values omitted."


def safe_error_payload(payload, http_status, *, fallback=None):
    """Project error text onto fixed public labels; NEVER return raw provider text.

    Google errors can echo credentials, prompts and arbitrary user data. Regex
    redaction cannot reliably remove all such data, so unknown messages are omitted.
    """
    result = {"http_status": http_status, "google_error_code": None,
              "google_error_status": None, "message": "Google rejected the request; raw message withheld.",
              "google_error_message_safe": safe_google_message(None), "details": []}
    try:
        # Apply the same bound to SDK exception payloads as to HTTP JSON bodies.
        if len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 16384:
            return result
        # SDK 2.34.0 also unwraps singleton response lists in APIError.__init__.
        if isinstance(payload, list) and len(payload) == 1:
            payload = payload[0]
        error = payload.get("error", payload) if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            error = fallback or {}
        # Never interpret exc.details itself as the RPC detail list. Only this
        # normalised error object's .details is passed to safe_error_details.
        fallback = fallback or {}
        code = error.get("code", fallback.get("code"))
        if type(code) is int and 100 <= code <= 599:
            result["google_error_code"] = code
        status = error.get("status", fallback.get("status"))
        if isinstance(status, str) and status in {
            "INVALID_ARGUMENT", "FAILED_PRECONDITION", "OUT_OF_RANGE", "UNAUTHENTICATED",
            "PERMISSION_DENIED", "RESOURCE_EXHAUSTED", "NOT_FOUND", "INTERNAL", "UNAVAILABLE",
            "DEADLINE_EXCEEDED", "UNKNOWN", "CANCELLED", "ALREADY_EXISTS", "ABORTED", "DATA_LOSS",
        }:
            result["google_error_status"] = status
        result["details"] = safe_error_details(error.get("details"))
        message = error.get("message", fallback.get("message"))
        result["google_error_message_safe"] = safe_google_message(message, result["google_error_status"])
        if not isinstance(message, str):
            return result
        message = message.lower()
        # Only these hard-coded public parameter names may survive classification.
        names = {"maxOutputTokens": ("maxoutputtokens", "max_output_tokens"),
                 "responseMimeType": ("responsemimetype", "response_mime_type"),
                 "temperature": ("temperature",), "thinkingBudget": ("thinkingbudget", "thinking_budget"),
                 "outputDimensionality": ("outputdimensionality", "output_dimensionality"),
                 "taskType": ("tasktype", "task_type"), "systemInstruction": ("systeminstruction", "system_instruction")}
        parameters = [name for name, tokens in names.items() if any(token in message for token in tokens)]
        if parameters:
            result["message"] = "Google error refers to parameter(s): " + ", ".join(parameters) + ". Raw message withheld."
        elif "api key" in message or "api_key" in message:
            result["message"] = "Google reported an API-key-related error. Raw message withheld."
        elif "quota" in message or "resource exhausted" in message:
            result["message"] = "Google reported a quota-related error. Raw message withheld."
    except Exception:
        pass  # JSON/body/encoding errors must never escape into diagnostics.
    return result


def safe_google_error(response):
    """HTTP response wrapper; no headers/raw bodies are retained or printed."""
    try:
        if len(response.content) <= 16384:
            return safe_error_payload(response.json(), response.status_code)
    except Exception:
        pass
    return safe_error_payload(None, response.status_code)


def safe_sdk_error(exc):
    """APIError.details is the WHOLE response JSON in google-genai 2.34.0."""
    from google.genai.errors import APIError
    if not isinstance(exc, APIError):
        return None
    code = exc.code if type(exc.code) is int and 100 <= exc.code <= 599 else None
    return safe_error_payload(exc.details, code, fallback={
        "code": exc.code, "status": exc.status, "message": exc.message})


@dataclass
class Budget:
    maximum: int
    requests: int = 0
    wire_requests: int = 0
    input_bytes: int = 0
    failed: bool = False
    sent_current: bool = False
    operation: str = "unknown"
    diagnostics: list = field(default_factory=list)
    generation_only: bool = False
    stage_codes: list = field(default_factory=list)

    def record_stage(self, code):
        if isinstance(code, str) and code in STAGE_CODES and len(self.stage_codes) < 64:
            self.stage_codes.append(code)

    def reserve(self, payload, *, embedding=False, operation="unknown"):
        size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 512
        if (self.failed or (self.generation_only and embedding) or self.requests >= self.maximum or size > (1800 if embedding else 6000)
                or self.input_bytes + size > 12000):
            self.failed = True
            raise SafetyStop("Synthetic request budget exceeded")
        self.requests += 1
        self.input_bytes += size
        self.sent_current = False
        self.operation = operation

    def check_request(self, request):
        url = request.url
        operations = {
            "/v1beta/models/gemini-3.5-flash-lite:generateContent",
            "/v1beta/models/gemini-embedding-001:embedContent",
            "/v1beta/models/gemini-embedding-001:batchEmbedContents",
        }
        if (self.failed or not self.requests or self.sent_current or self.wire_requests >= self.maximum
                or request.method != "POST" or url.scheme != "https"
                or url.host != "generativelanguage.googleapis.com" or url.port not in (None, 443)
                or url.path not in operations or url.query or url.userinfo):
            self.failed = True
            raise SafetyStop("Unexpected network request")
        if self.generation_only and not url.path.endswith(":generateContent"):
            self.failed = True
            raise SafetyStop("Generate-only forbids embedding requests")
        body = request.content
        embedding = "embed" in url.path.lower()
        if len(body) > (1800 if embedding else 6000):
            self.failed = True
            raise SafetyStop("Input byte/token bound exceeded")
        if not embedding:
            config = json.loads(body).get("generationConfig", {})
            limit = config.get("maxOutputTokens")
            if type(limit) is not int or not 1 <= limit <= 1500:
                self.failed = True
                raise SafetyStop("Missing output token bound")
        self.sent_current = True
        self.wire_requests += 1


@contextmanager
def isolation(budget):
    """Only sync official SDK HTTP is allowed; ORM/driver connections always fail."""
    from django.db.backends.base.base import BaseDatabaseWrapper
    import MySQLdb
    allowed = ContextVar("synthetic_gemini_socket", default=False)
    original_connect = socket.socket.connect
    original_send = httpx.Client.send

    def deny(*args, **kwargs):
        raise SafetyStop("Database or alternate network access forbidden")

    def connect(sock, address):
        if not allowed.get() or not isinstance(address, tuple) or address[1] != 443:
            return deny()
        try:
            if not ipaddress.ip_address(address[0]).is_global:
                return deny()
        except ValueError:
            if address[0] != "generativelanguage.googleapis.com":
                return deny()
        return original_connect(sock, address)

    def send(client, request, **kwargs):
        budget.check_request(request)
        budget.record_stage("HTTP_DISPATCH_STARTED")
        token = allowed.set(True)
        received = False
        try:
            kwargs["follow_redirects"] = False
            response = original_send(client, request, **kwargs)
            received = True
            budget.record_stage("HTTP_RESPONSE_RECEIVED")
            if response.status_code != 200:
                budget.record_stage("HTTP_RESPONSE_NOT_OK")
                # Capture before the shared adapter deliberately generalises errors.
                budget.diagnostics.append({"operation": budget.operation,
                    "api_method": request.url.path.rsplit(":", 1)[-1],
                    "model": request.url.path.split("/models/", 1)[-1].split(":", 1)[0],
                    **safe_google_error(response)})
                budget.failed = True
                raise SafetyStop("Provider rejected request; no retry")
            budget.record_stage("HTTP_RESPONSE_OK")
            return response
        except Exception as error:
            if not received:
                budget.record_stage("HTTP_RESPONSE_NOT_RECEIVED")
            if not budget.diagnostics:
                diagnostic = safe_sdk_error(error)
                if diagnostic is not None:
                    budget.diagnostics.append({"operation": budget.operation,
                        "api_method": request.url.path.rsplit(":", 1)[-1],
                        "model": request.url.path.split("/models/", 1)[-1].split(":", 1)[0],
                        **diagnostic})
            budget.failed = True
            raise SafetyStop("Provider request failed; no retry") from None
        finally:
            allowed.reset(token)

    with ExitStack() as stack:
        stack.enter_context(patch.object(BaseDatabaseWrapper, "ensure_connection", deny))
        for name in ("connect", "Connect", "Connection"):
            stack.enter_context(patch.object(MySQLdb, name, deny))
        stack.enter_context(patch.object(MySQLdb._mysql, "connect", deny))
        stack.enter_context(patch.object(socket.socket, "connect", connect))
        for name in ("connect_ex", "sendto"):
            stack.enter_context(patch.object(socket.socket, name, deny))
        stack.enter_context(patch.object(httpx.Client, "send", send))
        stack.enter_context(patch.object(httpx.AsyncClient, "send", deny))
        # No provider HTTP debug messages (headers may contain the key).
        prior = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        stack.callback(logging.disable, prior)
        yield


def configure(*, generation_only=False):
    """Standalone minimal settings: .env and config.settings are never imported."""
    import django
    from django.conf import settings
    if settings.configured:
        raise SafetyStop("Live probes require a fresh isolated process")
    settings.configure(
        BASE_DIR=ROOT, SECRET_KEY="synthetic-probe-not-a-website", USE_TZ=True,
        TIME_ZONE="Asia/Ho_Chi_Minh", AUTH_USER_MODEL="accounts.User",
        DATABASES={"default": {"ENGINE": "django.db.backends.dummy"}} if generation_only else
            {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        INSTALLED_APPS=[] if generation_only else ["django.contrib.auth", "django.contrib.contenttypes"] +
            "accounts services products employees appointments promotions billing reviews ai_features".split(),
        AI_PROVIDER="gemini", AI_PAID_CALLS_APPROVED=False,
        AI_PERSONALIZATION_EXPORT_APPROVED=False, AI_REVIEW_EXPORT_APPROVED=False,
        AI_GEMINI_MODEL="gemini-3.5-flash-lite", AI_GEMINI_EMBEDDING_MODEL="gemini-embedding-001",
        AI_GEMINI_EMBEDDING_DIMENSIONS=768,
    )
    django.setup()


def bounded_provider(budget):
    from ai_features.gemini import GeminiProvider

    class ProbeProvider(GeminiProvider):
        def _trace_stage(self, code):
            budget.record_stage(code)

        @contextmanager
        def _client(self):
            with super()._client() as client:
                try:
                    yield client
                except Exception as error:
                    if not budget.diagnostics:
                        diagnostic = safe_sdk_error(error)
                        if diagnostic is not None:
                            budget.diagnostics.append({"operation": budget.operation,
                                "model": self.name if budget.operation == "generate_content" else "gemini-embedding-001",
                                **diagnostic})
                    raise

        def structured(self, instruction, data):
            budget.reserve([instruction, data], operation="generate_content")
            return super().structured(instruction, data)

        def embed(self, texts, *, task_type="RETRIEVAL_DOCUMENT"):
            budget.reserve(texts, embedding=True, operation=(
                "query_embedding" if task_type == "RETRIEVAL_QUERY" else "document_embedding"))
            return super().embed(texts, task_type=task_type)

    return ProbeProvider()


def fr21_generation(provider):
    """One shared FR-21 answer builder: same source, prompt and adapter parameters."""
    source = SimpleNamespace(kind="service", object_id=900001, name="Dịch vụ giả lập",
                             text="Dịch vụ giả lập: 200000 VND, 60 phút.")
    answer = provider.answer("Dịch vụ giả lập giá bao nhiêu?", [source])
    if not answer:
        provider._trace_stage("FINAL_ANSWER_NOT_CREATED")
        raise SafetyStop("Ungrounded synthetic answer")
    return {"answer": answer, "sources": ["service:900001"]}


def probe(feature, provider, folder):
    """No customer IDs, history, ORM queries, or application writes are available."""
    if feature == "fr21":
        from ai_features.rag import Document, VectorIndex
        from django.test import override_settings
        document = Document("service", 900001, "Dịch vụ giả lập", "Dịch vụ giả lập: 200000 VND, 60 phút.")
        documents = {document.key: document}
        with override_settings(AI_RAG_DIRECTORY=folder / "vectors", AI_RAG_INDEX_UPDATE_APPROVED=True):
            index = VectorIndex()
            index.sync(documents, embedder=provider)
            matches = index.search(provider.embed_query("Dịch vụ giả lập giá bao nhiêu?"), documents, 0.0)
            if not matches:
                raise SafetyStop("No synthetic source retrieved")
            return fr21_generation(provider)
    if feature == "fr22":
        result = provider.structured(
            'Select eligible synthetic services only. Return {"items":[{"id":integer,"reason":string}]}.',
            {"budget": 300000, "minutesMaximum": 90, "needs": "face", "candidates": [
                {"id": 900001, "name": "Dịch vụ giả lập", "price": 200000, "minutes": 60, "group": "face"}]})
        items = result.get("items")
        if (not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict)
                or type(items[0].get("id")) is not int or items[0]["id"] != 900001
                or not isinstance(items[0].get("reason"), str) or not 1 <= len(items[0]["reason"]) <= 400):
            raise SafetyStop("Invalid synthetic recommendation")
        return result
    if feature != "fr23":
        raise SafetyStop("Unknown feature")
    result = provider.structured(
        'Analyze synthetic review. Return sentiment (positive/neutral/negative), themes (1-5 strings), '
        'summary (string), priority (low/medium/high), actions (1-5 strings). No identifying information.',
        {"rating": 5, "comment": "Nhận xét giả lập: không gian yên tĩnh, phục vụ chu đáo."})
    if (result.get("sentiment") not in {"positive", "neutral", "negative"}
            or result.get("priority") not in {"low", "medium", "high"}
            or not isinstance(result.get("summary"), str) or not 1 <= len(result["summary"]) <= 1000):
        raise SafetyStop("Invalid synthetic analysis")
    for field, limit in (("themes", 100), ("actions", 300)):
        values = result.get(field)
        if (not isinstance(values, list) or not 1 <= len(values) <= 5
                or any(not isinstance(v, str) or not 1 <= len(v) <= limit for v in values)):
            raise SafetyStop("Invalid synthetic analysis fields")
    return result


def synthetic_fallback(feature):
    """Local fixture-only fallback; never misrepresents a failed probe as AI."""
    if feature == "fr22":
        return {"mode": "rule", "items": [{"id": 900001, "price": 200000, "minutes": 60,
                "reason": "Dữ liệu giả lập đáp ứng ngân sách 300000 và thời lượng tối đa 90 phút."}]}
    if feature == "fr23":
        return {"mode": "rule", "sentiment": "positive", "priority": "low",
                "summary": "Theo 5 sao của fixture; chưa có phân tích nội dung bằng AI.",
                "actions": ["Đọc nhận xét giả lập và xác minh trước khi phản hồi."]}
    return {"mode": "fallback", "message": "Chưa có câu trả lời Gemini được xác minh từ tài liệu giả lập."}


def generate_only(feature):
    if feature != "fr21":
        raise SafetyStop("Generate-only requires FR-21; no other feature is approved")
    return live(feature, generation_only=True)


def live(feature, *, generation_only=False):
    from tools.openai_test import hidden_input
    if feature not in FEATURES or (generation_only and feature != "fr21") or not sys.stdin.isatty():
        raise SafetyStop("One feature and an interactive terminal are required")
    print("Verify THIS key's project in AI Studio: Free tier, billing disabled, model quota available.")
    print("The launcher cannot inspect billing or guarantee zero cost. If unsure, cancel now.")
    if input(f"Type {CONFIRMATION}: ").strip() != CONFIRMATION:
        raise SafetyStop("Free Tier was not verified; no key will be requested")
    budget = Budget(1 if generation_only else FEATURES[feature], generation_only=generation_only)
    key = None
    with isolation(budget):
        if generation_only:
            configure(generation_only=True)
        else:
            configure()
        from django.test import override_settings
        key = hidden_input("Gemini Free Tier test API key (hidden): ")
        try:
            with (nullcontext(None) if generation_only else TemporaryDirectory(prefix="annhien-gemini-live-")) as temp, override_settings(
                AI_GEMINI_API_KEY=key, AI_GEMINI_REQUESTS_APPROVED=True,
                AI_GEMINI_FREE_TIER_CONFIRMED=True, AI_GEMINI_FREE_TIER_ONLY=True,
            ):
                from ai_features.config import time_budget
                try:
                    with time_budget(provider="gemini"):
                        if generation_only:
                            output = fr21_generation(bounded_provider(budget))
                        else:
                            output = probe(feature, bounded_provider(budget), Path(temp))
                    if key in json.dumps(output, ensure_ascii=False):
                        budget.record_stage("OUTPUT_PRIVACY_REJECTED")
                        raise SafetyStop("Secret in provider response")
                    status = "PASS"
                except Exception:
                    budget.failed = True
                    # Never echo a provider exception, request, key, or malformed response.
                    output = synthetic_fallback(feature)
                    status = "FALLBACK"
                if generation_only:
                    # This mode reports diagnostics only, never prompts or model response text.
                    output = {"grounded_response_validated": status == "PASS"}
        finally:
            key = None  # No file/env storage; Python cannot promise memory zeroisation.
    if budget.wire_requests == 0:
        budget.record_stage("REQUEST_NOT_SENT")
    return {"feature": feature, "status": status, "synthetic_only": True,
            "scope": "FR-21 generateContent only; synthetic sources" if generation_only else
                "adapter/vector synthetic probe; not authenticated application acceptance",
            "maximum_requests": budget.maximum, "attempted_operations": budget.requests,
            "http_requests": budget.wire_requests, "database_connections": 0,
            "diagnostics": budget.diagnostics, "stage_codes": budget.stage_codes,
            "failure_stage_code": next((code for code in budget.stage_codes if code in FAILURE_STAGE_CODES), None),
            "result": output}
