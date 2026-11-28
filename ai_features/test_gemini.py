from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from .config import time_budget
from .gemini import CHAT_MODEL, EMBEDDING_MODEL, GeminiProvider
from .integration import ProviderUnavailable
from .provider_factory import embedding_identity, external_provider
from .providers import Source
from .rag import Document, RAGRetriever, VectorIndex


@override_settings(AI_PROVIDER="gemini", AI_GEMINI_REQUESTS_APPROVED=True,
                   AI_GEMINI_FREE_TIER_CONFIRMED=True, AI_GEMINI_FREE_TIER_ONLY=True,
                   AI_PAID_CALLS_APPROVED=False, AI_GEMINI_API_KEY="fake-only")
class GeminiDeadlineTests(SimpleTestCase):
    def test_8000_is_rejected_before_client_creation(self):
        with self.settings(AI_GEMINI_HTTP_TIMEOUT_MS=8000), patch("google.genai.Client") as client:
            with self.assertRaises(TimeoutError), GeminiProvider()._client():
                pass
            client.assert_not_called()

    def test_10000_and_12000_allocations(self):
        for value in (10000, 12000):
            with self.settings(AI_GEMINI_HTTP_TIMEOUT_MS=value), patch("google.genai.Client") as client:
                with GeminiProvider()._client():
                    pass
                self.assertEqual(client.call_args.kwargs["http_options"].timeout, value)

    def test_sdk_wire_headers_at_10000_and_12000(self):
        from tools.test_gemini_live import GeminiLiveTests
        for value in (10000, 12000):
            with self.settings(AI_GEMINI_HTTP_TIMEOUT_MS=value):
                _, _, requests = GeminiLiveTests().execute_probe("fr22")
                self.assertEqual(int(requests[0].headers["X-Server-Timeout"]), value // 1000)

    def test_low_remainder_falls_back_without_rounding_up(self):
        from .config import gemini_timeout_ms
        self.assertEqual(gemini_timeout_ms(11.8), 11000)
        self.assertEqual(gemini_timeout_ms(10.5), 10000)
        for seconds in (0, 8, 9.99, 10.1):
            with self.assertRaises(TimeoutError):
                gemini_timeout_ms(seconds)

    def test_shared_40s_budget_covers_three_12s_operations_then_stops(self):
        from .config import deadline, remaining
        now = [100.]
        with patch("ai_features.config.monotonic", side_effect=lambda: now[0]), time_budget(), patch("google.genai.Client") as client:
            self.assertEqual(deadline.get(), 140.)
            for _ in range(3):
                with GeminiProvider()._client():
                    now[0] += 12
            self.assertEqual(client.call_count, 3)
            self.assertEqual(remaining(), 4.)
            with self.assertRaises(TimeoutError), GeminiProvider()._client():
                pass
            self.assertEqual(client.call_count, 3)

    def test_actual_fr21_mock_wire_sequence_has_legal_deadlines_within_total(self):
        from tools.test_gemini_live import GeminiLiveTests
        from .config import remaining
        helper = GeminiLiveTests()
        now = [100.]
        def advance():
            now[0] += 12
        with patch("ai_features.config.monotonic", side_effect=lambda: now[0]), time_budget():
            _, budget, requests = helper.execute_probe("fr21", advance=advance)
            self.assertEqual(budget.wire_requests, 3)
            self.assertEqual([int(r.headers["X-Server-Timeout"]) for r in requests], [12, 12, 12])
            self.assertEqual(remaining(), 4)

    def test_nested_budget_never_extends_parent_and_mock_stays_8s(self):
        from .config import deadline
        with self.settings(AI_PROVIDER="mock"), patch("ai_features.config.monotonic", return_value=100):
            with time_budget():
                self.assertEqual(deadline.get(), 108)
                with time_budget(provider="gemini"):
                    self.assertEqual(deadline.get(), 108)
        self.assertIsNone(deadline.get())

    def test_pre_send_hook_rejects_8s_or_deadline_exceeding_remainder(self):
        import httpx
        from .config import check_gemini_deadline
        for header, left in (("8", 40), ("12", 11), ("nan", 40), ("bad", 40)):
            with self.assertRaises(TimeoutError):
                check_gemini_deadline(httpx.Request("POST", "https://example.test", headers={"X-Server-Timeout": header}), left)
        for header in ("10", "12"):
            check_gemini_deadline(httpx.Request("POST", "https://example.test", headers={"X-Server-Timeout": header}), 40)

    def test_sdk_error_crosses_yield_but_public_structured_error_is_safe(self):
        from google.genai.errors import ClientError
        from .integration import ProviderUnavailable
        original = ClientError(400, {"error": {"message": "PRIVATE", "status": "INVALID_ARGUMENT"}})
        with patch("google.genai.Client") as client:
            with self.assertRaises(ClientError) as caught, GeminiProvider()._client():
                raise original
            self.assertIs(caught.exception, original)
            client.return_value.__enter__.return_value.models.generate_content.side_effect = original
            with self.assertRaises(ProviderUnavailable) as caught:
                GeminiProvider().structured("synthetic", {})
            self.assertNotIn("PRIVATE", str(caught.exception))

    def test_launcher_observes_sdk_error_before_public_boundary_sanitizes_it(self):
        from google.genai.errors import ClientError
        from tools.gemini_live import Budget, bounded_provider
        budget = Budget(1)
        with patch("google.genai.Client") as sdk:
            sdk.return_value.__enter__.return_value.models.generate_content.side_effect = ClientError(
                400, {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "PRIVATE"}})
            with self.assertRaises(ProviderUnavailable):
                bounded_provider(budget).structured("synthetic", {})
        self.assertEqual(budget.diagnostics[0]["http_status"], 400)
        self.assertEqual(budget.diagnostics[0]["google_error_status"], "INVALID_ARGUMENT")
        self.assertNotIn("PRIVATE", json.dumps(budget.diagnostics))

    def test_slow_setup_and_serialization_stop_before_transport(self):
        import httpx
        from .config import deadline
        now = [100.]
        with patch("ai_features.config.monotonic", side_effect=lambda: now[0]), time_budget(), patch("google.genai.Client") as client:
            def setup(*args, **kwargs):
                now[0] = 139
                return MagicMock()
            client.side_effect = setup
            with self.assertRaises(TimeoutError), GeminiProvider()._client():
                pass
        with patch("ai_features.config.monotonic", side_effect=lambda: now[0]), time_budget(), patch("google.genai.Client") as client:
            with GeminiProvider()._client():
                hook = client.call_args.kwargs["http_options"].client_args["event_hooks"]["request"][0]
                now[0] = deadline.get() - 9
                with self.assertRaises(TimeoutError):
                    hook(httpx.Request("POST", "https://example.test", headers={"X-Server-Timeout": "12"}))

    def test_fr22_and_fr23_short_budget_keep_rule_fallback(self):
        from contextlib import nullcontext
        from decimal import Decimal
        from . import assistance
        from .config import deadline
        service = SimpleNamespace(pk=1, name="Synthetic", description="", price=Decimal(200000), duration_minutes=60,
                                  suitable="", steps="", note="")
        customer = MagicMock()
        customer.appointments.filter.return_value.order_by.return_value.values_list.return_value = []
        inputs = {"skin": "", "needs": "face", "budget": "300000", "duration": "", "interests": ""}
        token = deadline.set(8.)
        try:
            with patch("ai_features.config.monotonic", return_value=0), \
                    self.settings(AI_PERSONALIZATION_EXPORT_APPROVED=True, AI_REVIEW_EXPORT_APPROVED=True), \
                    patch("google.genai.Client") as sdk, patch.object(assistance, "profile_inputs", return_value=inputs), \
                    patch.object(assistance, "candidates", return_value=[service]), \
                    patch.object(assistance, "linked_care_products", return_value=[]), \
                    patch.object(assistance.AIRecommendation.objects, "create"):
                self.assertEqual(assistance.recommend(customer, {})["mode"], "rule")
                review = SimpleNamespace(pk=1, rating=5, comment="Synthetic comment")
                with patch.object(assistance.Review.objects, "filter") as reviews, \
                        patch.object(assistance.Review.objects, "select_for_update") as locked, \
                        patch.object(assistance.transaction, "atomic", return_value=nullcontext()), \
                        patch.object(assistance.AIReviewAnalysis.objects, "update_or_create", return_value=(None, True)) as store, \
                        patch.object(assistance, "serialize_analysis", return_value={"mode": "rule"}):
                    reviews.return_value.first.return_value = review
                    locked.return_value.get.return_value = review
                    self.assertEqual(assistance.analyze_review(1)["mode"], "rule")
                    self.assertEqual(store.call_args.kwargs["defaults"]["mode"], "rule")
                sdk.assert_not_called()
        finally:
            deadline.reset(token)


@contextmanager
def fake_sdk(*, text='{"ok":true}', vectors=None):
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(text=text)
    client.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=v) for v in (vectors or [[3., 4.] + [0.]*766])])
    with patch.object(GeminiProvider, "_client") as connection:
        connection.return_value.__enter__.return_value = client
        yield client


@override_settings(AI_PROVIDER="gemini", AI_GEMINI_REQUESTS_APPROVED=False, AI_GEMINI_FREE_TIER_CONFIRMED=False,
                   AI_PAID_CALLS_APPROVED=False, AI_GEMINI_FREE_TIER_ONLY=True, AI_GEMINI_EMBEDDING_DIMENSIONS=768)
class GeminiAdapterTests(SimpleTestCase):
    def test_factory_and_model_configuration(self):
        self.assertIsInstance(external_provider(), GeminiProvider)
        self.assertEqual(external_provider().name, CHAT_MODEL)
        self.assertEqual(embedding_identity()["model"], EMBEDDING_MODEL)
        with self.settings(AI_GEMINI_MODEL="configured-model"):
            self.assertEqual(external_provider().name, "configured-model")

    def test_unapproved_requests_do_not_read_key_or_construct_sdk(self):
        from . import gemini
        def values(name, default=None):
            if name == "AI_GEMINI_API_KEY":
                raise AssertionError("Key must not be read")
            return default
        with patch.object(gemini, "option", side_effect=values), patch("google.genai.Client") as sdk:
            with self.assertRaises(ProviderUnavailable), GeminiProvider()._client():
                pass
            sdk.assert_not_called()

    def test_missing_key_is_safe_before_sdk_initialization(self):
        # Only the policy reader is mocked; no live approval setting is switched on.
        with patch("ai_features.gemini.enabled", side_effect=lambda n: n != "AI_PAID_CALLS_APPROVED"), self.settings(AI_GEMINI_API_KEY=""), patch("google.genai.Client") as sdk:
            with self.assertRaises(ProviderUnavailable), GeminiProvider()._client():
                pass
            sdk.assert_not_called()

    def test_paid_flag_or_unconfirmed_free_project_refuses_calls(self):
        for predicate in (lambda n: True, lambda n: False, lambda n: n == "AI_GEMINI_REQUESTS_APPROVED"):
            with patch("ai_features.gemini.enabled", side_effect=predicate), patch("google.genai.Client") as sdk:
                with self.assertRaises(ProviderUnavailable), GeminiProvider()._client():
                    pass
                sdk.assert_not_called()

    def test_unverified_models_and_dimensions_refuse_calls(self):
        for overrides in ({"AI_GEMINI_MODEL": "gemini-pro-latest"}, {"AI_GEMINI_EMBEDDING_MODEL": "text-embedding-004"},
                          {"AI_GEMINI_EMBEDDING_DIMENSIONS": 12}, {"AI_GEMINI_FREE_TIER_ONLY": False}):
            with self.settings(**overrides), patch("ai_features.gemini.enabled", side_effect=lambda n: n != "AI_PAID_CALLS_APPROVED"), patch("google.genai.Client") as sdk:
                with self.assertRaises(ProviderUnavailable), GeminiProvider()._client():
                    pass
                sdk.assert_not_called()

    def test_sdk_developer_endpoint_timeout_no_retry_no_cloud_credentials(self):
        with patch("ai_features.gemini.enabled", side_effect=lambda n: n != "AI_PAID_CALLS_APPROVED"), self.settings(AI_GEMINI_API_KEY="synthetic-not-a-key"), patch("google.genai.Client") as sdk, time_budget():
            with GeminiProvider()._client():
                pass
        options = sdk.call_args.kwargs
        self.assertFalse(options["vertexai"])
        self.assertFalse(options["enterprise"])
        self.assertNotIn("credentials", options)
        http = options["http_options"]
        self.assertEqual(http.base_url, "https://generativelanguage.googleapis.com")
        self.assertEqual(http.retry_options.attempts, 1)
        self.assertEqual(http.timeout, 12000)
        self.assertFalse(http.client_args["trust_env"])
        self.assertFalse(http.client_args["follow_redirects"])

    def test_sdk_auth_quota_and_server_errors_do_not_expose_messages(self):
        from google.genai import errors
        import httpx
        for error in (errors.ClientError(401, {"error": {"message": "synthetic-private"}}),
                      errors.ClientError(403, {"error": {"message": "synthetic-private"}}),
                      errors.ClientError(429, {"error": {"message": "synthetic-private"}}),
                      errors.ServerError(503, {"error": {"message": "synthetic-private"}}),
                      httpx.ReadTimeout("synthetic-private")):
            with patch("ai_features.gemini.enabled", side_effect=lambda n: n != "AI_PAID_CALLS_APPROVED"), self.settings(AI_GEMINI_API_KEY="synthetic-not-a-key"), patch("google.genai.Client", side_effect=error):
                with self.assertRaises((ProviderUnavailable, TimeoutError)) as caught, GeminiProvider()._client():
                    pass
                self.assertNotIn("synthetic", str(caught.exception))

    def test_structured_json_and_no_tools(self):
        with fake_sdk() as sdk:
            self.assertEqual(GeminiProvider().structured("fixture", {"question": "fixture"}), {"ok": True})
        config = sdk.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertTrue(config.automatic_function_calling.disable)
        self.assertFalse(config.tools)

    def test_invalid_empty_blocked_or_nonobject_json_falls_back(self):
        for text in (None, "", "[]", "bad-json", '{"x":NaN}', "x"*20001):
            with self.subTest(text_type=type(text).__name__), fake_sdk(text=text):
                with self.assertRaises(ProviderUnavailable):
                    GeminiProvider().structured("fixture", {})

    def test_generation_timeout_is_preserved(self):
        with fake_sdk() as sdk:
            sdk.models.generate_content.side_effect = TimeoutError("synthetic-private")
            with self.assertRaises(TimeoutError) as error:
                GeminiProvider().structured("fixture", {})
            self.assertNotIn("synthetic-private", str(error.exception))

    def test_embeddings_have_expected_dimensions_and_are_normalized(self):
        with fake_sdk() as sdk:
            vector = GeminiProvider().embed(["fixture"])[0]
        self.assertEqual(len(vector), 768)
        self.assertAlmostEqual(vector[0], .6)
        self.assertAlmostEqual(vector[1], .8)
        self.assertAlmostEqual(sum(v*v for v in vector), 1.)
        self.assertEqual(sdk.models.embed_content.call_args.kwargs["config"].task_type, "RETRIEVAL_DOCUMENT")

    def test_query_embedding_uses_retrieval_query_task(self):
        with fake_sdk() as sdk:
            GeminiProvider().embed_query("fixture")
        config = sdk.models.embed_content.call_args.kwargs["config"]
        self.assertEqual(config.task_type, "RETRIEVAL_QUERY")
        self.assertEqual(config.output_dimensionality, 768)

    def test_malformed_embeddings_rejected(self):
        for vector in ([1.], [float("nan")]*768, [float("inf")]*768, [True]*768, [0.]*768):
            with fake_sdk(vectors=[vector]):
                with self.assertRaises(ProviderUnavailable):
                    GeminiProvider().embed(["fixture"])
        with fake_sdk(vectors=[[1.] + [0.]*767]):
            with self.assertRaises(ProviderUnavailable):
                GeminiProvider().embed(["one", "two"])

    def test_embedding_timeout_and_invalid_input(self):
        with fake_sdk() as sdk:
            sdk.models.embed_content.side_effect = TimeoutError("fixture timeout")
            with self.assertRaises(TimeoutError):
                GeminiProvider().embed(["fixture"])
        with fake_sdk() as sdk:
            for values in ([], [""], [None]):
                with self.assertRaises(ProviderUnavailable):
                    GeminiProvider().embed(values)
            sdk.models.embed_content.assert_not_called()

    def test_shared_grounding_rejects_unknown_citations_or_amounts(self):
        source = Source("service", 1, "Fixture", "Giá 300.000 VND · 60 phút")
        with fake_sdk(text='{"answer":"Giá 300.000 VND","sources":["service:1"]}'):
            self.assertIn("Nguồn: Fixture", GeminiProvider().answer("fixture", [source]))
        for body in ({"answer": "Giá 999.000 VND", "sources": ["service:1"]}, {"answer": "fixture", "sources": ["service:999"]}):
            with fake_sdk(text=json.dumps(body)):
                self.assertEqual(GeminiProvider().answer("fixture", [source]), "")


@override_settings(AI_PROVIDER="gemini", AI_GEMINI_EMBEDDING_DIMENSIONS=768, AI_RAG_INDEX_UPDATE_APPROVED=False)
class GeminiVectorTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="gemini-vector-")
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(AI_RAG_DIRECTORY=Path(self.temp.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.doc = Document("service", 1, "Massage fixture", "Massage thư giãn fixture")

    def test_namespaces_separate_provider_model_version_and_dimension(self):
        first = VectorIndex().path
        with self.settings(AI_PROVIDER="mock", AI_EMBEDDING_MODEL=EMBEDDING_MODEL):
            self.assertNotEqual(first, VectorIndex().path)
        with self.settings(AI_GEMINI_EMBEDDING_VERSION="next-review"):
            self.assertNotEqual(first, VectorIndex().path)
        with self.settings(AI_GEMINI_EMBEDDING_DIMENSIONS=1536):
            self.assertNotEqual(first, VectorIndex().path)

    def test_legacy_index_is_not_opened_or_deleted(self):
        db = settings.DATABASES["default"]
        legacy = [db["ENGINE"], str(db["NAME"]), db.get("HOST", ""), db.get("PORT", ""), "text-embedding-3-small"]
        path = Path(self.temp.name) / f"vectors-{hashlib.sha256(json.dumps(legacy).encode()).hexdigest()[:24]}.sqlite3"
        path.write_bytes(b"legacy-index-fixture")
        self.assertNotEqual(VectorIndex().path, path)
        self.assertEqual(path.read_bytes(), b"legacy-index-fixture")

    def test_new_index_requires_approval_before_embedding_or_rebuild(self):
        index, embedder = VectorIndex(), MagicMock()
        with self.assertRaises(ProviderUnavailable):
            index.sync({self.doc.key: self.doc}, embedder)
        embedder.embed.assert_not_called()
        with patch("ai_features.rag.public_documents", return_value={self.doc.key: self.doc}), patch("ai_features.rag.embedding_provider") as provider:
            self.assertEqual(RAGRetriever().retrieve("Tôi muốn nghỉ ngơi"), [])
            provider.assert_not_called()

    def test_dimension_mismatch_cannot_be_upserted(self):
        index = VectorIndex()
        embedder = MagicMock()
        embedder.embed.return_value = [[1., 0.]]
        with self.settings(AI_RAG_INDEX_UPDATE_APPROVED=True), self.assertRaises(ProviderUnavailable):
            index.sync({self.doc.key: self.doc}, embedder)
        with index.connect() as cx:
            self.assertEqual(cx.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 0)

    def test_existing_semantic_index_is_read_without_reindexing(self):
        index, embedder = VectorIndex(), MagicMock()
        embedder.embed.return_value = [[1.] + [0.]*767]
        embedder.embed_query.return_value = [1.] + [0.]*767
        with self.settings(AI_RAG_INDEX_UPDATE_APPROVED=True):
            index.sync({self.doc.key: self.doc}, embedder)
        with patch("ai_features.rag.public_documents", return_value={self.doc.key: self.doc}), patch("ai_features.rag.embedding_provider", return_value=embedder), patch.object(VectorIndex, "sync") as update:
            result = RAGRetriever().retrieve("Tôi muốn nghỉ ngơi")
        self.assertEqual(result[0].object_id, 1)
        update.assert_not_called()
        with self.assertRaises(ProviderUnavailable):
            index.search([1., 0.], {self.doc.key: self.doc}, .3)


@override_settings(AI_PROVIDER="gemini", AI_PERSONALIZATION_EXPORT_APPROVED=False, AI_REVIEW_EXPORT_APPROVED=False,
                   AI_GEMINI_REQUESTS_APPROVED=False, AI_GEMINI_FREE_TIER_CONFIRMED=False, AI_PAID_CALLS_APPROVED=False)
class GeminiBusinessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Reuse already-validated synthetic fixtures, without inheriting/repeating the old test methods.
        from .test_assistance import AssistanceTests
        AssistanceTests.setUpTestData.__func__(cls)

    def test_unapproved_exports_always_use_local_fallback(self):
        from .assistance import recommend, analyze_review
        with patch("ai_features.assistance.external_provider") as provider:
            rec = recommend(self.customer, {})
            analysis = analyze_review(self.review.pk)
            provider.assert_not_called()
        self.assertEqual(rec["mode"], "rule")
        self.assertEqual([r["id"] for r in rec["items"]], [self.service.pk])
        self.assertEqual(analysis["mode"], "rule")

    def test_gemini_recommendation_json_is_validated_with_synthetic_policy_reader(self):
        from .assistance import recommend
        provider = MagicMock()
        with patch("ai_features.assistance.enabled", return_value=True), patch("ai_features.assistance.external_provider", return_value=provider):
            provider.structured.return_value = {"items": [{"id": self.service.pk, "reason": "Đúng nhu cầu fixture."}]}
            self.assertEqual(recommend(self.customer, {})["mode"], "ai")
            for bad in (self.off.pk, self.expensive.pk, 999999):
                provider.structured.return_value = {"items": [{"id": bad, "reason": "Không hợp lệ."}]}
                self.assertEqual(recommend(self.customer, {})["mode"], "rule")
            provider.structured.side_effect = TimeoutError
            self.assertEqual(recommend(self.customer, {})["mode"], "rule")
        self.assertFalse(settings.AI_PERSONALIZATION_EXPORT_APPROVED)

    def test_gemini_review_json_is_validated_and_original_is_preserved(self):
        from .assistance import analyze_review
        from reviews.models import Review, ReviewReply
        provider = MagicMock()
        provider.name = CHAT_MODEL
        provider.structured.return_value = {"sentiment": "positive", "summary": "Khách hài lòng với không gian.",
            "themes": ["Không gian"], "priority": "low", "actions": ["Duy trì chất lượng."]}
        with patch("ai_features.assistance.enabled", return_value=True), patch("ai_features.assistance.external_provider", return_value=provider):
            self.assertEqual(analyze_review(self.review.pk)["mode"], "ai")
            provider.structured.return_value = {"sentiment": "unknown"}
            self.assertEqual(analyze_review(self.review.pk)["mode"], "rule")
            provider.structured.side_effect = TimeoutError
            self.assertEqual(analyze_review(self.review.pk)["mode"], "rule")
        self.assertEqual(Review.objects.get(pk=self.review.pk).comment, self.review.comment)
        self.assertEqual(ReviewReply.objects.count(), 0)
        self.assertFalse(settings.AI_REVIEW_EXPORT_APPROVED)

    @override_settings(AI_CHAT_ENABLED=True, AI_RAG_ENABLED=True, AI_RAG_INDEX_UPDATE_APPROVED=False)
    def test_gemini_fallback_keeps_history_private_and_resumable(self):
        client = self.client
        client.force_login(self.owner)
        response = client.post("/api/ai/chat/", {"question": self.service.name, "requestId": str(uuid4())},
                               content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"]["status"], "fallback")
        session = response.json()["session"]["id"]
        self.assertEqual(client.get("/api/ai/chat/sessions/?resume=1").json()["session"]["id"], session)
        client.force_login(self.other)
        self.assertEqual(client.get(f"/api/ai/chat/sessions/{session}/").status_code, 404)

    @override_settings(AI_CHAT_ENABLED=True)
    def test_provider_label_does_not_claim_live_ai_without_approval(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/api/ai/chat/sessions/?resume=1").json()["providerMode"], "mock")
        with patch("ai_features.views.enabled", side_effect=lambda n: n in {"AI_GEMINI_REQUESTS_APPROVED", "AI_GEMINI_FREE_TIER_CONFIRMED"}):
            self.assertEqual(self.client.get("/api/ai/chat/sessions/?resume=1").json()["providerMode"], "ai")
        self.assertFalse(settings.AI_GEMINI_REQUESTS_APPROVED)
