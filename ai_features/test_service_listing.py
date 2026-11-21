"""Q01 regression: real ORM/chat orchestration, no index or external calls."""
import json
from contextlib import ExitStack
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, SimpleTestCase, override_settings

from accounts.models import User
from products.models import CareProduct
from services.models import Service, ServiceCategory
from .chat import FALLBACK, send_question
from .integration import GroundedProvider
from .providers import CatalogRetriever, Source
from .rag import Document, RAGRetriever
from .test_gemini import fake_sdk

QUESTION = "Spa có những dịch vụ nào?"


class GrounderServiceListingTests(SimpleTestCase):
    def test_q01_filters_non_service_and_exposes_entity_kind(self):
        sources = [Source(kind, i, kind, "Dữ liệu giả") for i, kind in enumerate(
            ("category", "service", "product", "promotion"), 1)]
        provider = GroundedProvider()
        with patch.object(provider, "structured", create=True,
                          return_value={"answer": "service", "sources": ["service:2"]}) as structured:
            self.assertTrue(provider.answer(QUESTION, sources))
        self.assertEqual(structured.call_args.args[1]["sources"], [
            {"id": "service:2", "kind": "service", "name": "service", "text": "Dữ liệu giả"}])
        self.assertIn("category", structured.call_args.args[0])

    def test_category_only_stops_before_generation(self):
        provider = GroundedProvider()
        with patch.object(provider, "structured", create=True) as structured:
            self.assertEqual(provider.answer(QUESTION, [Source("category", 1, "Thư giãn", "Thư giãn")]), "")
            structured.assert_not_called()

    def test_q01_rejects_category_citation_even_when_gemini_returns_it(self):
        provider = GroundedProvider()
        with patch.object(provider, "structured", create=True,
                          return_value={"answer": "Thư giãn", "sources": ["category:1"]}):
            self.assertEqual(provider.answer(QUESTION, [Source("category", 1, "Thư giãn", "Thư giãn"),
                                                       Source("service", 2, "Massage", "Massage")]), "")

    def test_other_questions_keep_all_entity_types_explicit(self):
        sources = [Source(kind, i, kind, "Dữ liệu giả") for i, kind in enumerate(
            ("category", "service", "product", "promotion"), 1)]
        provider = GroundedProvider()
        with patch.object(provider, "structured", create=True,
                          return_value={"answer": "Thông tin", "sources": ["product:3"]}) as structured:
            self.assertTrue(provider.answer("Sản phẩm và khuyến mãi có gì?", sources))
        self.assertEqual([s["kind"] for s in structured.call_args.args[1]["sources"]],
                         ["category", "service", "product", "promotion"])


@override_settings(AI_CHAT_ENABLED=True, AI_RAG_ENABLED=True, AI_PROVIDER="gemini",
                   AI_RAG_INDEX_UPDATE_APPROVED=False, AI_CHAT_SPA_INFORMATION="")
class ServiceListingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("q01_fixture", "q01@example.test", password=None)
        self.category = ServiceCategory.objects.create(name="Danh mục thư giãn")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.index = self.stack.enter_context(patch("ai_features.rag.VectorIndex", side_effect=AssertionError("Index forbidden")))
        self.embed = self.stack.enter_context(patch("ai_features.rag.embedding_provider", side_effect=AssertionError("Embedding forbidden")))

    def service(self):
        return Service.objects.create(category=self.category, name="Massage thử", description="Dịch vụ giả lập", price=200000, duration_minutes=60)

    def test_q01_rag_returns_only_active_service_records_without_index_access(self):
        item = self.service()
        Service.objects.create(category=self.category, name="Đã ẩn", description="Dịch vụ giả lập", price=200000, duration_minutes=60, is_active=False)
        hidden = ServiceCategory.objects.create(name="Danh mục ẩn", is_active=False)
        Service.objects.create(category=hidden, name="Không công khai", description="Dịch vụ giả lập", price=200000, duration_minutes=60)
        CareProduct.objects.create(name=QUESTION, product_type="Giả lập", description="Sản phẩm không phải dịch vụ")
        for question in (QUESTION, "Kể tên các liệu trình tại spa.", "Tôi muốn xem danh sách dịch vụ."):
            with self.subTest(question=question):
                rows = RAGRetriever().retrieve(question)
                self.assertEqual([(r.kind, r.object_id) for r in rows], [("service", item.pk)])
                self.assertTrue(rows[0].fingerprint)
        self.index.assert_not_called()
        self.embed.assert_not_called()

    def test_service_request_matches_all_intent_terms_without_unrelated_services(self):
        def add(name):
            return Service.objects.create(
                category=self.category, name=name,
                description="Dịch vụ kiểm thử",
                price=200000, duration_minutes=60,
            )

        basic = add("Chăm sóc da mặt cơ bản")
        deep = add("Chăm sóc da mặt chuyên sâu cấp ẩm")
        add("Chăm sóc bàn chân thư giãn")
        add("Chăm sóc da tay và dưỡng móng cơ bản")
        add("Massage đá nóng thư giãn toàn thân")

        cases = [
            ("Tôi muốn tìm hiểu dịch vụ chăm sóc da mặt tại An Nhiên Spa.",
             [basic.pk, deep.pk]),
            ("Tôi muốn chăm sóc da mặt.", [basic.pk, deep.pk]),
            ("Tôi muốn cấp ẩm da mặt.", [deep.pk]),
        ]

        for question, expected_ids in cases:
            with self.subTest(question=question):
                rows = RAGRetriever().retrieve(question, limit=5)
                self.assertEqual(
                    [(r.kind, r.object_id) for r in rows],
                    [("service", pk) for pk in expected_ids],
                )

        self.index.assert_not_called()
        self.embed.assert_not_called()


    def test_category_only_rag_returns_no_services(self):
        self.assertEqual(RAGRetriever().retrieve(QUESTION), [])
        self.index.assert_not_called()
        self.embed.assert_not_called()

    def test_q01_lexical_does_not_mix_products_into_service_list(self):
        item = self.service()
        CareProduct.objects.create(name=QUESTION, product_type="Giả lập", description="Không phải dịch vụ")
        self.assertEqual([(r.kind, r.object_id) for r in CatalogRetriever().retrieve(QUESTION)], [("service", item.pk)])

    def test_q01_chat_gemini_mock_receives_service_only_and_persists_answer(self):
        item = self.service()
        output = {"answer": "Massage thử: 200.000 VND · 60 phút.", "sources": [f"service:{item.pk}"]}
        with fake_sdk(text=json.dumps(output)) as sdk:
            answer = send_question(self.owner.pk, None, QUESTION, None, uuid4())
        self.assertEqual(answer.status, "success")
        self.assertNotIn(self.category.name, answer.content)
        answer.refresh_from_db()
        self.assertIn("Nguồn: Massage thử", answer.content)
        sdk.models.generate_content.assert_called_once()
        sdk.models.embed_content.assert_not_called()
        payload = json.loads(sdk.models.generate_content.call_args.kwargs["contents"])
        self.assertEqual([r["kind"] for r in payload["sources"]], ["service"])

    def test_category_only_chat_falls_back_without_provider(self):
        with patch("ai_features.chat.get_provider") as provider:
            answer = send_question(self.owner.pk, None, QUESTION, None, uuid4())
        self.assertEqual(answer.status, "fallback")
        self.assertEqual(answer.content, FALLBACK)
        provider.assert_not_called()

    def test_non_listing_rag_can_still_retrieve_category(self):
        self.index.side_effect = None
        self.index.return_value.ready.return_value = True
        document = Document("category", self.category.pk, self.category.name, "Thông tin danh mục")
        self.index.return_value.search.return_value = [(1.0, document, document.text)]
        self.embed.side_effect = None
        self.embed.return_value.embed_query.return_value = [1.0]
        with patch("ai_features.rag.public_documents", return_value={document.key: document}):
            rows = RAGRetriever().retrieve("Giới thiệu nhóm thư giãn")
        self.assertEqual([r.kind for r in rows], ["category"])
        self.index.return_value.sync.assert_not_called()
