"""Offline proof: all external selection is Gemini-only, including legacy flags."""
from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from .integration import OpenAIProvider, ProviderUnavailable
from .provider_factory import embedding_identity, embedding_provider, external_provider
from .providers import get_provider, Source


class ProviderLockTests(SimpleTestCase):
    @override_settings(AI_PROVIDER="openai", AI_PAID_CALLS_APPROVED=True,
                       AI_OPENAI_API_KEY="synthetic-never-used")
    def test_openai_rejected_at_all_factories_without_construction_or_http(self):
        with patch("ai_features.integration.OpenAIProvider") as retired, patch("httpx.Client") as http:
            for factory in (external_provider, embedding_provider, embedding_identity, get_provider):
                with self.subTest(factory=factory.__name__), self.assertRaises(ProviderUnavailable):
                    factory()
            retired.assert_not_called()
            http.assert_not_called()

    def test_legacy_adapter_cannot_send_even_when_constructor_bypassed(self):
        with patch("httpx.Client") as http:
            with self.assertRaises(ProviderUnavailable):
                OpenAIProvider()
            retired = object.__new__(OpenAIProvider)
            for method, args in ((retired._post, ("embeddings", {})),
                                 (retired.structured, ("fixture", {})),
                                 (retired.embed, (["fixture"],)),
                                 (retired.answer, ("fixture", []))):
                with self.subTest(method=method.__name__), self.assertRaises(ProviderUnavailable):
                    method(*args)
            http.assert_not_called()

    def test_unknown_providers_fail_closed(self):
        for name in ("OPENAI", "OpenAI", "openai ", "https://api.openai.com", "", "other"):
            with self.settings(AI_PROVIDER=name):
                for factory in (external_provider, embedding_provider, embedding_identity, get_provider):
                    with self.subTest(name=name, factory=factory.__name__), self.assertRaises(ProviderUnavailable):
                        factory()

    @override_settings(AI_PROVIDER="mock")
    def test_mock_embedding_is_local_deterministic_and_separate(self):
        with patch("ai_features.integration.OpenAIProvider") as retired, patch("httpx.Client") as http:
            embedder = embedding_provider()
            vectors = embedder.embed(["massage fixture", "massage fixture", ""])
            self.assertEqual(vectors[0], vectors[1])
            self.assertEqual(len(vectors[0]), 256)
            self.assertAlmostEqual(sum(x*x for x in vectors[0]), 1)
            self.assertEqual(sum(vectors[2]), 0)
            self.assertEqual(embedder.embed_query("massage fixture"), vectors[0])
            self.assertEqual(embedding_identity()["provider"], "mock")
            retired.assert_not_called()
            http.assert_not_called()

    @override_settings(AI_PROVIDER="openai", AI_PAID_CALLS_APPROVED=True,
                       AI_RAG_ENABLED=True, AI_RAG_INDEX_UPDATE_APPROVED=True)
    def test_index_command_rejects_before_catalog_or_vector_access(self):
        from django.core.management import call_command, CommandError
        with patch("ai_features.rag.VectorIndex") as index, patch("ai_features.rag.public_documents") as catalog:
            with self.assertRaises(CommandError):
                call_command("index_spa")
            index.assert_not_called()
            catalog.assert_not_called()

    @override_settings(AI_PROVIDER="gemini")
    def test_gemini_selected_for_both_generation_and_embedding(self):
        from .gemini import GeminiProvider
        self.assertIsInstance(external_provider(), GeminiProvider)
        self.assertIsInstance(embedding_provider(), GeminiProvider)
        self.assertEqual(embedding_identity()["provider"], "gemini")


@override_settings(AI_ASSISTANCE_ENABLED=True, AI_CHAT_ENABLED=True, AI_RAG_ENABLED=False,
                   AI_PERSONALIZATION_EXPORT_APPROVED=True, AI_REVIEW_EXPORT_APPROVED=True,
                   AI_PAID_CALLS_APPROVED=True, AI_OPENAI_API_KEY="synthetic-never-used")
class ApplicationProviderLockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from .test_assistance import AssistanceTests
        AssistanceTests.setUpTestData.__func__(cls)

    def setUp(self):
        # Import the SDK before HTTP-constructor spies; do not cache mock classes
        # inside SDK modules during lazy imports. No client or request is created.
        import google.genai
        cache.clear()
        self.client.force_login(self.owner)

    def exercise_flows(self):
        from django.contrib.auth.models import Permission
        from .models import AIRecommendation, AIReviewAnalysis, ChatSession, ChatMessage
        chat = self.client.post("/api/ai/chat/", {"question": "Chăm sóc da", "requestId": str(uuid4())},
                                content_type="application/json")
        self.assertEqual(chat.status_code, 200)
        self.assertEqual(chat.json()["answer"]["status"], "fallback")
        rec = self.client.post("/api/ai/recommendations/", {}, content_type="application/json")
        self.assertEqual(rec.status_code, 200)
        self.assertEqual(rec.json()["mode"], "rule")
        self.assertEqual(AIRecommendation.objects.count(), 1)
        session = ChatSession.objects.get(user=self.owner)
        counts = (ChatSession.objects.count(), ChatMessage.objects.count())
        self.assertEqual(self.client.get(f"/api/ai/chat/sessions/{session.pk}/").status_code, 200)
        self.assertEqual(self.client.get("/api/ai/chat/sessions/?resume=1").json()["providerMode"], "mock")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/api/ai/chat/sessions/{session.pk}/").status_code, 404)
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label="ai_features",
                                                               codename="change_aireviewanalysis"))
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label="ai_features",
                                                               codename="read_chat_history"))
        self.client.force_login(self.admin)
        result = self.client.post(f"/api/ai/reviews/{self.review.pk}/analyze/", {}, content_type="application/json")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["analysis"]["mode"], "rule")
        self.assertEqual(AIReviewAnalysis.objects.count(), 1)
        self.assertEqual(self.client.get(f"/api/ai/reviews/{self.review.pk}/analyze/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/ai/admin/chat/sessions/{session.pk}/").status_code, 200)
        self.assertEqual(counts, (ChatSession.objects.count(), ChatMessage.objects.count()))

    @override_settings(AI_PROVIDER="openai")
    def test_fr21_fr22_fr23_fr24_reject_openai_even_with_legacy_approvals(self):
        with patch("ai_features.integration.OpenAIProvider") as retired, patch("httpx.Client") as http:
            self.exercise_flows()
            retired.assert_not_called()
            http.assert_not_called()

    @override_settings(AI_PROVIDER="gemini")
    def test_gemini_failure_only_falls_back_internally(self):
        with patch("ai_features.gemini.GeminiProvider.structured", side_effect=ProviderUnavailable("fixture unavailable")) as gemini, \
             patch("ai_features.integration.OpenAIProvider") as retired, patch("httpx.Client") as http:
            # Use the real provider selection, grounder, views and persistence.
            with patch("ai_features.providers.CatalogRetriever.retrieve", return_value=[Source("service", self.service.pk, "Fixture", "Fixture")]):
                self.exercise_flows()
            self.assertEqual(gemini.call_count, 3)
            retired.assert_not_called()
            http.assert_not_called()
