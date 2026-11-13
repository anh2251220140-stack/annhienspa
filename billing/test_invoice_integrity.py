import json
from datetime import time
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase

from appointments.models import Appointment
from appointments.services import book, transition
from core.test_phase3 import Fixtures

from .models import Invoice, InvoiceDetail, Payment
from .services import cash, ensure_invoice
from .test_phase4 import at_appointment_start
from .views import invoice_row


class InvoiceIntegrityTests(Fixtures, TestCase):
    def setUp(self):
        self.seed()
        self.appointment = book(self.user, self.service.pk, self.employee.pk, self.day, time(10))

    def confirm(self):
        transition(self.admin, self.appointment.pk, "confirmed")
        return Invoice.objects.get(appointment=self.appointment)

    def legacy_without_detail(self):
        Appointment.objects.filter(pk=self.appointment.pk).update(status="confirmed")
        self.appointment.refresh_from_db()
        return Invoice.objects.create(appointment=self.appointment, subtotal=420000, total_amount=420000)

    def historical_row(self, appointment):
        return {
            "appointment_id": appointment.pk,
            "service_name": "Tên trên chứng từ",
            "subtotal": "410000",
            "discount": "10000",
            "promotion_code": "LEGACY",
            "evidence": "Chứng từ thử đã được kiểm tra",
        }

    def reconcile(self, *appointments, apply=False):
        with TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text(json.dumps([self.historical_row(a) for a in appointments]), encoding="utf-8")
            options = {"apply": True, "admin_id": self.admin.pk, "acknowledge_historical_prices": True} if apply else {}
            return call_command("reconcile_invoices", plan=str(plan), stdout=StringIO(), **options)

    def test_repeat_confirmation_preserves_one_snapshot_and_existing_payment(self):
        invoice = self.confirm()
        detail = invoice.details.get()
        with at_appointment_start(self.appointment):
            cash(self.admin, invoice.pk, Decimal("500000"))
        self.service.name = "Dịch vụ đã đổi tên"
        self.service.price = Decimal("620000")
        self.service.save()
        self.assertEqual(self.confirm().pk, invoice.pk)

        invoice.refresh_from_db()
        self.assertEqual(Invoice.objects.filter(appointment=self.appointment).count(), 1)
        self.assertEqual(invoice.details.count(), 1)
        self.assertEqual(invoice.details.get().pk, detail.pk)
        self.assertEqual(invoice.payment_status, "paid")
        self.assertEqual(invoice.total_amount, Decimal("500000"))
        self.assertEqual(invoice.payments.get().amount, invoice.total_amount)
        self.assertEqual(invoice.details.get().unit_price, Decimal("500000"))
        self.assertEqual(invoice_row(invoice)["service"], detail.service_name_snapshot)

    def test_database_rejects_second_detail_when_bulk_create_bypasses_validation(self):
        invoice = self.confirm()
        duplicate = InvoiceDetail(
            invoice=invoice,
            service=self.service,
            service_name_snapshot=self.service.name,
            unit_price=invoice.subtotal,
            line_total=invoice.subtotal,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            InvoiceDetail.objects.bulk_create([duplicate])
        self.assertEqual(invoice.details.count(), 1)

    def test_detail_insert_failure_rolls_back_confirmation_and_invoice(self):
        original_updated_at = self.appointment.updated_at
        with patch("billing.services.InvoiceDetail.objects.create", side_effect=IntegrityError("insert failed")):
            with self.assertRaisesMessage(IntegrityError, "insert failed"):
                self.confirm()
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "pending")
        self.assertEqual(self.appointment.updated_at, original_updated_at)
        self.assertFalse(Invoice.objects.filter(appointment=self.appointment).exists())
        self.assertFalse(InvoiceDetail.objects.exists())

    def test_missing_detail_blocks_reconfirmation_and_finance_operations(self):
        invoice = self.legacy_without_detail()
        with self.assertRaisesMessage(ValidationError, "thiếu dòng chi tiết"):
            ensure_invoice(self.appointment)
        with self.assertRaisesMessage(ValidationError, "thiếu dòng chi tiết"):
            self.confirm()

        self.client.force_login(self.user)
        for path in ("", "promotions/"):
            with self.subTest(path=path):
                result = self.client.get(f"/api/billing/{invoice.pk}/{path}")
                self.assertEqual(result.status_code, 400)
                self.assertIn("thiếu dòng chi tiết", result.json()["error"])

        self.client.force_login(self.admin)
        result = self.client.post(f"/api/billing/{invoice.pk}/cash/", {"amount": "420000"})
        self.assertEqual(result.status_code, 400)
        self.assertIn("thiếu dòng chi tiết", result.json()["error"])
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_status, "unpaid")
        self.assertEqual(invoice.total_amount, Decimal("420000"))
        self.assertFalse(invoice.details.exists())
        self.assertFalse(Payment.objects.filter(invoice=invoice).exists())

    def test_invoice_api_reports_multiple_details_instead_of_using_first_snapshot(self):
        invoice = self.confirm()
        detail = invoice.details.get()
        duplicate = InvoiceDetail(invoice=invoice, service=self.service, service_name_snapshot="Dòng khác")
        # Simulate the relation returned by a database that has not applied 0006.
        manager_type = type(invoice.details)
        with patch.object(manager_type, "all", return_value=[detail, duplicate]):
            self.client.force_login(self.user)
            result = self.client.get(f"/api/billing/{invoice.pk}/")
        self.assertEqual(result.status_code, 400)
        self.assertIn("có nhiều dòng chi tiết", result.json()["error"])

    def test_missing_detail_preserves_appointment_and_pending_payment_for_reconciliation(self):
        invoice = self.confirm()
        payment = Payment.objects.create(
            invoice=invoice, payment_method="online", amount=invoice.total_amount, order_code=1234567,
        )
        invoice.details.all().delete()
        with patch("billing.services.gateway.get") as get_payment:
            with self.assertRaisesMessage(ValidationError, "thiếu dòng chi tiết"):
                transition(self.admin, self.appointment.pk, "cancelled", reason="Khách đề nghị hủy")
            get_payment.assert_not_called()

        webhook_data = SimpleNamespace(
            order_code=payment.order_code, amount=payment.amount, currency="VND",
            payment_link_id="", code="00",
        )
        with patch("billing.views.gateway.verify", return_value=webhook_data):
            response = self.client.post("/api/billing/webhook/payos/", "{}", content_type="application/json")
        self.assertEqual(response.status_code, 503)
        self.assertIn("reconciliation", response.json()["error"])

        self.appointment.refresh_from_db()
        invoice.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(self.appointment.status, "confirmed")
        self.assertEqual(invoice.payment_status, "unpaid")
        self.assertEqual(payment.status, "pending")
        self.assertIsNone(payment.paid_at)
        self.assertFalse(invoice.details.exists())

    def test_reconcile_reports_missing_detail_and_rolls_back_earlier_plan_rows(self):
        invoice = self.legacy_without_detail()
        with self.assertRaisesMessage(CommandError, "thiếu hoặc có nhiều dòng chi tiết"):
            call_command("reconcile_invoices", stdout=StringIO())
        with self.assertRaisesMessage(CommandError, "thiếu dòng chi tiết"):
            self.reconcile(self.appointment)

        other = book(self.user, self.service.pk, self.employee.pk, self.day, time(13))
        Appointment.objects.filter(pk=other.pk).update(status="confirmed")
        with self.assertRaisesMessage(CommandError, "thiếu dòng chi tiết"):
            self.reconcile(other, self.appointment, apply=True)
        self.assertFalse(Invoice.objects.filter(appointment=other).exists())
        self.assertFalse(invoice.details.exists())
