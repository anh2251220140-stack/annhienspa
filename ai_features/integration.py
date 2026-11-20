"""Shared grounding validation; external AI is Gemini-only."""
from .numeric_grounding import numeric_claims_supported
from .chat_intents import is_service_list_question


class ProviderUnavailable(Exception):
    pass


class GroundedProvider:
    """Grounding/citation validation shared by external adapters."""
    def _trace_stage(self, code):
        """Optional launcher observer; no payload and no production side effects."""
        pass

    def answer(self, question, sources):
        if is_service_list_question(question):
            sources = [source for source in sources if source.kind == "service"]
            if not sources:
                return ""
        result = self.structured(
            "Answer in Vietnamese using ONLY the supplied sources. If insufficient return "
            '{"answer":"","sources":[]}. Otherwise return {"answer":str,"sources":[source IDs]}. '
            "Each source has a kind: category is a grouping only, service is an actual service, "
            "product is a care product and promotion is an offer. Never list a category, product "
            "or promotion as a service. List only service records when asked for services; "
            "for those service-list requests only, if no service records are supplied, return an empty answer. "
            "Cite sources for every fact. Do not promise eligibility for a promotion. "
            "Preserve all numeric values, prices, durations, dates and percentages "
            "exactly as written in the supplied sources. Do not convert units, "
            "round numbers, abbreviate amounts or invent percentages. "
            "If a numeric fact cannot be stated exactly as supplied, omit that fact.",
            {"question": question, "sources": [
                {"id": f"{s.kind}:{s.object_id}", "kind": s.kind, "name": s.name, "text": s.text} for s in sources]},
        )
        answer, refs = result.get("answer"), result.get("sources")
        valid = {f"{s.kind}:{s.object_id}" for s in sources}
        if (not isinstance(answer, str) or len(answer) > 1700 or not isinstance(refs, list)
                or not refs or any(not isinstance(x, str) or x not in valid for x in refs)):
            if "answer" not in result:
                self._trace_stage("ANSWER_MISSING")
            elif not isinstance(answer, str) or len(answer) > 1700:
                self._trace_stage("ANSWER_INVALID")
            elif not isinstance(refs, list) or not refs:
                self._trace_stage("SOURCE_LIST_INVALID")
            else:
                self._trace_stage("SOURCE_ID_INVALID")
            return ""
        # Numeric claims must occur in retrieved facts; an ungrounded amount/date falls back.
        if not numeric_claims_supported(answer, (s.text for s in sources)):
            self._trace_stage("NUMERIC_GROUNDING_FAILED")
            return ""
        try:
            names = [s.name for s in sources if f"{s.kind}:{s.object_id}" in refs]
            output = answer.strip() + "\nNguồn: " + "; ".join(dict.fromkeys(names))
        except Exception:
            self._trace_stage("FINAL_ANSWER_BUILD_FAILED")
            raise
        self._trace_stage("ANSWER_VALIDATED")
        return output


class OpenAIProvider(GroundedProvider):
    """Retired import compatibility only: every entry point fails before any I/O."""
    def __init__(self):
        raise ProviderUnavailable("OpenAI is disabled; use Gemini or internal fallback")

    def _post(self, *args, **kwargs):
        raise ProviderUnavailable("OpenAI is disabled")

    def structured(self, *args, **kwargs):
        raise ProviderUnavailable("OpenAI is disabled")

    def embed(self, *args, **kwargs):
        raise ProviderUnavailable("OpenAI is disabled")
