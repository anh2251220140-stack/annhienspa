from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from products.models import CareProduct
from promotions.models import Promotion
from services.models import Service, ServiceCategory

from .config import time_budget
from .integration import GroundedProvider, ProviderUnavailable
from .providers import Source
from .rag import Document, RAGRetriever, VectorIndex, chunks, cosine, public_documents
from .rag import sources_current, vector_index


class Embeddings:
    """Deliberately synthetic concept vectors; NOT a quality measurement of a real model."""
    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(texts)
        return [[1., 0.] + [0.] * 254 if any(x in t.lower() for x in ("massage", "thư giãn", "mệt")) else [0., 1.] + [0.] * 254 for t in texts]


@override_settings(AI_RAG_STORAGE="mysql", AI_PROVIDER="mock", AI_RAG_INDEX_UPDATE_APPROVED=True)
class DatabaseVectorTests(TestCase):
    def setUp(self):
        self.document = Document("service", 1, "Massage đá nóng", "Massage thư giãn")
        self.documents = {self.document.key: self.document}
        self.embedder = Embeddings()

    def test_retrieves_saved_vectors_in_a_new_instance_without_reindexing(self):
        self.assertEqual(vector_index().sync(self.documents, self.embedder), 1)
        self.assertEqual(vector_index().sync(self.documents, self.embedder), 0)
        new_instance = vector_index()
        self.assertTrue(new_instance.ready(self.documents))
        with self.settings(AI_RAG_INDEX_UPDATE_APPROVED=False):
            with patch("ai_features.rag.public_documents", return_value=self.documents), patch(
                "ai_features.rag.embedding_provider", return_value=self.embedder
            ):
                sources = RAGRetriever().retrieve("Ngồi cả ngày, tôi mệt và muốn thư giãn")
        self.assertEqual([source.name for source in sources], [self.document.name])
        self.assertEqual(len(self.embedder.calls), 2)  # One indexing call and one query.

    def test_stale_documents_are_hidden_and_failed_refresh_can_be_retried(self):
        index = vector_index()
        self.assertEqual(index.sync(self.documents, self.embedder), 1)
        changed = Document("service", 1, self.document.name, "Massage thư giãn vùng vai")
        current = {changed.key: changed}
        query = self.embedder.embed(["thư giãn"])[0]
        self.assertFalse(index.ready(current))
        self.assertEqual(index.search(query, current, .5), [])
        with patch.object(self.embedder, "embed", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                index.sync(current, self.embedder)
        self.assertTrue(index.ready(self.documents))
        self.assertEqual(index.sync(current, self.embedder), 1)
        self.assertEqual(index.search(query, current, .5)[0][2], changed.text)
        self.assertEqual(index.sync({}, self.embedder), 0)
        self.assertFalse(index.ready(current))

    def test_update_approval_and_embedding_namespace_remain_separate(self):
        with self.settings(AI_RAG_INDEX_UPDATE_APPROVED=False):
            with self.assertRaises(ProviderUnavailable):
                vector_index().sync(self.documents, self.embedder)
        self.assertEqual(self.embedder.calls, [])
        vector_index().sync(self.documents, self.embedder)
        with self.settings(AI_PROVIDER="gemini"):
            self.assertFalse(vector_index().ready(self.documents))
        self.assertTrue(vector_index().ready(self.documents))

    def test_invalidation_and_invalid_vectors(self):
        index = vector_index()
        with patch.object(self.embedder, "embed", return_value=[[1.0]]):
            with self.assertRaises(ProviderUnavailable):
                index.sync(self.documents, self.embedder)
        self.assertFalse(index.ready(self.documents))
        index.sync(self.documents, self.embedder)
        index.invalidate([self.document.key])
        self.assertFalse(index.ready(self.documents))


class VectorTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="spa-vector-test-")
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(AI_RAG_DIRECTORY=Path(self.temp.name), AI_RAG_INDEX_UPDATE_APPROVED=True)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_chunk_overlap_and_limits(self):
        text = " ".join(f"{i:04x}" for i in range(1000))
        parts = list(chunks(text))
        self.assertEqual([len(s.split()) for s in parts], [400, 400, 300])
        self.assertEqual(parts[0].split()[-50:], parts[1].split()[:50])
        self.assertEqual(list(chunks("")), [])

    def test_cosine(self):
        self.assertAlmostEqual(cosine([1, 1], [1, 1]), 1)
        self.assertEqual(cosine([1, 0], [0, 1]), 0)
        self.assertEqual(cosine([0, 0], [1, 1]), 0)
        self.assertEqual(cosine([1], [1, 2]), 0)

    def test_incremental_upsert_delete_and_metadata(self):
        index, embedder = VectorIndex(), Embeddings()
        doc = Document("service", 1, "Massage", "Massage thư giãn", "3")
        self.assertEqual(index.sync({doc.key: doc}, embedder), 1)
        self.assertEqual(index.sync({doc.key: doc}, embedder), 0)
        self.assertEqual(len(embedder.calls), 1)
        rows = index.search([1., 0.] + [0.] * 254, {doc.key: doc}, .5)
        self.assertEqual(rows[0][1], doc)
        with index.connect() as cx:
            meta, updated = cx.execute("SELECT metadata,updated_at FROM documents").fetchone()
        self.assertEqual(json.loads(meta)["status"], "active")
        self.assertTrue(updated)
        changed = Document("service", 1, "Massage", "Massage giá mới", "3")
        self.assertEqual(index.search([1., 0.] + [0.] * 254, {doc.key: changed}, .5), [])
        self.assertEqual(index.sync({doc.key: changed}, embedder), 1)
        index.sync({}, embedder)
        self.assertEqual(index.search([1., 0.] + [0.] * 254, {doc.key: doc}, .5), [])

    def test_metadata_filter_happens_before_cosine(self):
        index, embedder = VectorIndex(), Embeddings()
        doc = Document("service", 2, "Massage", "Massage")
        index.sync({doc.key: doc}, embedder)
        with patch("ai_features.rag.cosine") as scorer:
            self.assertEqual(index.search([1., 0.] + [0.] * 254, {}, 0), [])
            scorer.assert_not_called()

    def test_failed_embedding_does_not_publish_new_digest(self):
        index = VectorIndex()
        d = Document("service", 1, "Massage", "Massage")
        with patch.object(Embeddings, "embed", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                index.sync({d.key: d}, Embeddings())
        with index.connect() as cx:
            self.assertEqual(cx.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 0)

    def test_semantic_synonym_and_dedup(self):
        d = Document("service", 1, "Massage", "Massage thư giãn")
        with patch("ai_features.rag.public_documents", return_value={d.key: d}), patch("ai_features.rag.embedding_provider", Embeddings):
            result = RAGRetriever().retrieve("Tôi mệt, muốn thư giãn")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].object_id, 1)

    def test_final_source_fingerprints_reject_changed_or_hidden_catalog(self):
        d = Document("service", 1, "Massage", "Massage 300.000 VND")
        source = Source("service", 1, d.name, d.text, d.digest)
        with patch("ai_features.rag.public_documents", return_value={d.key: d}):
            self.assertTrue(sources_current([source]))
        changed = Document("service", 1, "Massage", "Massage 400.000 VND")
        with patch("ai_features.rag.public_documents", return_value={d.key: changed}):
            self.assertFalse(sources_current([source]))
        with patch("ai_features.rag.public_documents", return_value={}):
            self.assertFalse(sources_current([source]))

    def test_catalog_changed_during_embedding_does_not_return_old_price(self):
        old = Document("service", 1, "Massage", "Massage 300.000 VND")
        new = Document("service", 1, "Massage", "Massage 400.000 VND")
        with patch("ai_features.rag.public_documents", side_effect=[{old.key: old}, {new.key: new}]), patch("ai_features.rag.embedding_provider", Embeddings):
            results = RAGRetriever().retrieve("Tôi mệt, muốn thư giãn")
        self.assertFalse(results)

    def test_no_data_does_not_call_provider(self):
        with patch("ai_features.rag.public_documents", return_value={}), patch("ai_features.rag.embedding_provider") as provider:
            self.assertEqual(RAGRetriever().retrieve("Spa có những dịch vụ nào?"), [])
            provider.assert_not_called()

    def test_unsupported_actions_do_not_call_retrieval(self):
        with patch("ai_features.rag.public_documents") as fetch:
            for text in ("Đặt lịch giúp tôi", "Hủy lịch", "Chẩn đoán bệnh", "Thanh toán"):
                self.assertEqual(RAGRetriever().retrieve(text), [])
            fetch.assert_not_called()


@override_settings(AI_RAG_ENABLED=False, AI_CHAT_SPA_INFORMATION="Giờ mở cửa 09:00–21:00.")
class PublicCatalogTests(TestCase):
    def setUp(self):
        self.cat = ServiceCategory.objects.create(name="Công khai")
        self.service = Service.objects.create(category=self.cat, name="Massage", description="Thư giãn", price=300000, duration_minutes=60)

    def test_catalog_contains_only_public_active_fields(self):
        CareProduct.objects.create(name="Kem", product_type="Dưỡng", description="Sản phẩm công khai")
        docs = public_documents()
        self.assertIn(f"service:{self.service.pk}", docs)
        self.assertIn("300.000 VND", docs[f"service:{self.service.pk}"].text)
        self.assertEqual({d.source_type for d in docs.values()}, {"category", "service", "product", "spa"})
        self.cat.is_active = False
        self.cat.save()
        self.assertNotIn(f"service:{self.service.pk}", public_documents())

    def test_expired_and_inactive_promotions_never_indexed(self):
        today = timezone.localdate()
        common = dict(name="Ưu đãi", discount_type="percent", discount_value=10, start_date=today-timedelta(days=3))
        valid = Promotion.objects.create(code="NOW", end_date=today, **common)
        old = Promotion.objects.create(code="OLD", end_date=today-timedelta(days=1), **common)
        off = Promotion.objects.create(code="OFF", end_date=today, is_active=False, **common)
        docs = public_documents()
        self.assertIn(f"promotion:{valid.pk}", docs)
        self.assertNotIn(f"promotion:{old.pk}", docs)
        self.assertNotIn(f"promotion:{off.pk}", docs)

    @override_settings(AI_RAG_ENABLED=True)
    def test_invalidation_only_after_commit_no_paid_calls(self):
        with patch("ai_features.rag.VectorIndex") as index, patch("ai_features.gemini.GeminiProvider._client") as paid:
            with self.captureOnCommitCallbacks(execute=True):
                self.service.name = "Tên mới"
                self.service.save()
                index.assert_not_called()
            index.return_value.invalidate.assert_called_once_with([f"service:{self.service.pk}"])
            paid.assert_not_called()


@override_settings(AI_CHAT_ENABLED=True, AI_RAG_ENABLED=True, AI_CHAT_SPA_INFORMATION="",
                   AI_CHAT_DAILY_LIMIT=30, AI_CHAT_COOLDOWN_SECONDS=5, AI_RAG_INDEX_UPDATE_APPROVED=True)
class RAGChatIntegrationTests(TestCase):
    def setUp(self):
        from accounts.models import User
        self.owner = User.objects.create_user("rag_chat", "rag-chat@example.test", "test-only")
        self.temp = TemporaryDirectory(prefix="rag-chat-")
        self.addCleanup(self.temp.cleanup)
        self.settings_override = override_settings(AI_RAG_DIRECTORY=Path(self.temp.name), AI_RAG_INDEX_UPDATE_APPROVED=True)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        category = ServiceCategory.objects.create(name="Thư giãn")
        self.service = Service.objects.create(category=category, name="Massage", description="Thư giãn", price=300000, duration_minutes=60)

    def send(self):
        from .chat import send_question
        return send_question(self.owner.pk, None, "Massage", None, uuid4())

    def test_rag_chat_persists_grounded_sources(self):
        provider = MagicMock(name="provider")
        provider.name = "synthetic-provider"
        provider.answer.return_value = "Massage: 300.000 VND. Nguồn: Massage"
        with patch("ai_features.rag.embedding_provider", Embeddings), patch("ai_features.chat.get_provider", return_value=provider):
            result = self.send()
        self.assertEqual(result.status, "success")
        self.assertIn("Nguồn: Massage", result.content)
        result.refresh_from_db()
        self.assertIn("300.000 VND", result.content)
        self.assertTrue(all(s.fingerprint for s in provider.answer.call_args.args[1]))

    def test_admin_change_during_answer_discards_stale_facts(self):
        def changed(*args):
            Service.objects.filter(pk=self.service.pk).update(price=400000)
            return "Massage: 300.000 VND."
        provider = MagicMock()
        provider.name = "synthetic-provider"
        provider.answer.side_effect = changed
        with patch("ai_features.rag.embedding_provider", Embeddings), patch("ai_features.chat.get_provider", return_value=provider):
            result = self.send()
        self.assertEqual(result.status, "fallback")
        self.assertNotIn("300.000", result.content)

    def test_cooldown_blocks_embeddings_and_generation(self):
        from .chat import ChatError
        with patch("ai_features.rag.embedding_provider", Embeddings):
            self.send()
        with patch("ai_features.rag.embedding_provider") as embeddings, patch("ai_features.chat.get_provider") as provider:
            with self.assertRaises(ChatError) as error:
                self.send()
            self.assertEqual(error.exception.status, 429)
            embeddings.assert_not_called()
            provider.assert_not_called()

    @override_settings(AI_RAG_ENABLED=False, AI_PROVIDER="openai", AI_PAID_CALLS_APPROVED=False)
    def test_unapproved_provider_returns_safe_fallback_without_network(self):
        with patch("httpx.Client") as http:
            result = self.send()
        self.assertEqual(result.status, "fallback")
        http.assert_not_called()


class ProviderTests(SimpleTestCase):
    def test_citations_and_ungrounded_numbers(self):
        source = Source("service", 1, "Massage", "Massage: 300.000 VND · 60 phút.")
        provider = GroundedProvider()
        with patch.object(provider, "structured", create=True, return_value={"answer": "Giá 300.000 VND", "sources": ["service:1"]}):
            self.assertIn("Nguồn: Massage", provider.answer("Giá?", [source]))
        for output in ({"answer": "Giá 900.000 VND", "sources": ["service:1"]},
                       {"answer": "Dịch vụ", "sources": ["service:999"]}, {"answer": "Dịch vụ", "sources": []}):
            with patch.object(provider, "structured", create=True, return_value=output):
                self.assertEqual(provider.answer("Giá?", [source]), "")

    def test_rejects_empty_answer_and_numbers_copied_from_uncited_sources(self):
        service = Source("service", 1, "Massage", "Giá 300.000 VND")
        other = Source("service", 2, "Gội đầu", "Giá 100.000 VND")
        provider = GroundedProvider()
        for answer in (" ", "Massage giá 100.000 VND"):
            with self.subTest(answer=answer), patch.object(
                provider, "structured", create=True, return_value={"answer": answer, "sources": ["service:1"]}
            ):
                self.assertEqual(provider.answer("Massage giá bao nhiêu?", [service, other]), "")

    def test_timeout_budget(self):
        with time_budget(), patch("ai_features.config.monotonic", return_value=10**20):
            with self.assertRaises(TimeoutError):
                from .config import remaining
                remaining()
