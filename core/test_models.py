from datetime import date, time
from decimal import Decimal
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction, connection
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from accounts.models import User, Customer
from services.models import Service, ServiceCategory
from employees.models import Employee, EmployeeService, EmployeeSchedule
from appointments.models import Appointment
from promotions.models import Promotion, PromotionService
from products.models import CareProduct, ServiceProduct
from billing.models import Invoice, InvoiceDetail, Payment
from reviews.models import Review, ReviewReply
from ai_features.models import AIRecommendation, AIReviewAnalysis

class ModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("modeluser", "model@example.com", "StrongTest!9372")
        cls.customer = Customer.objects.create(user=cls.user, full_name="Khách", phone="0901234567")
        cls.category = ServiceCategory.objects.create(name="Chăm sóc")
        cls.service = Service.objects.create(category=cls.category, name="Dịch vụ", description="Mô tả", price=500000, duration_minutes=60)
        cls.employee = Employee.objects.create(full_name="Chuyên viên", specialty="Spa")
        EmployeeService.objects.create(employee=cls.employee, service=cls.service)
        EmployeeSchedule.objects.create(employee=cls.employee, work_date=date(2030,1,1), start_time=time(9), end_time=time(18))

    def appointment(self, **kwargs):
        data = dict(customer=self.customer, service=self.service, employee=self.employee,
                    appointment_date=date(2030,1,1), start_time=time(10), end_time=time(11))
        data.update(kwargs)
        return Appointment.objects.create(**data)

    def test_exact_20_business_tables_and_no_auth_user(self):
        names = "users customers service_categories services employees employee_services employee_schedules appointments appointment_reassignments promotions promotion_services invoices invoice_details payments reviews review_replies ai_recommendations ai_review_analysis care_products service_products".split()
        models = [m for m in apps.get_models() if m._meta.app_label in "accounts services products employees appointments promotions billing reviews ai_features".split()]
        self.assertEqual(set(m._meta.db_table for m in models), set(names))
        self.assertNotIn("auth_user", connection.introspection.table_names())
        self.assertTrue(set(names).issubset(connection.introspection.table_names()))

    def test_database_checks_even_when_validation_bypassed(self):
        for field, value in [("price", -1), ("duration_minutes", 0)]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                Service.objects.filter(pk=self.service.pk).update(**{field: value})
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.user.pk).update(role="Other")

    def test_link_unique_and_protected_foreign_keys(self):
        with self.assertRaises(ValidationError):
            EmployeeService.objects.create(employee=self.employee, service=self.service)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeeService.objects.bulk_create([EmployeeService(employee=self.employee, service=self.service)])
        with self.assertRaises(ProtectedError):
            self.service.delete()

    def test_schedule_overlap_and_appointment_conflicts(self):
        with self.assertRaises(ValidationError):
            EmployeeSchedule.objects.create(employee=self.employee, work_date=date(2030,1,1), start_time=time(10), end_time=time(12))
        self.appointment()
        with self.assertRaises(ValidationError):
            self.appointment(start_time=time(10,30), end_time=time(11,30))
        self.appointment(start_time=time(11), end_time=time(12))
        with self.assertRaises(ValidationError):
            self.appointment(start_time=time(8), end_time=time(9))

    def test_one_invoice_and_money_snapshot(self):
        appointment = self.appointment()
        with self.assertRaises(ValidationError):
            Invoice.objects.create(appointment=appointment, subtotal=500000, total_amount=500000)
        appointment.status = "confirmed"; appointment.save()
        invoice = Invoice.objects.create(appointment=appointment, subtotal=500000, total_amount=500000)
        detail = InvoiceDetail.objects.create(invoice=invoice, service=self.service, service_name_snapshot=self.service.name, unit_price=500000, line_total=500000)
        with self.assertRaises(ValidationError):
            Invoice.objects.create(appointment=appointment, subtotal=500000, total_amount=500000)
        self.service.price = 600000; self.service.save()
        detail.refresh_from_db(); self.assertEqual(detail.unit_price, Decimal(500000))
        invoice.payment_status = "paid"; invoice.save()
        invoice.total_amount = 600000; invoice.subtotal = 600000
        with self.assertRaises(ValidationError): invoice.save()

    def test_review_requires_completed_owner_and_single_review(self):
        appointment = self.appointment()
        data = dict(appointment=appointment, customer=self.customer, service=self.service, rating=5)
        with self.assertRaises(ValidationError): Review.objects.create(**data)
        appointment.status = "completed"; appointment.save()
        review = Review.objects.create(**data)
        with self.assertRaises(ValidationError): Review.objects.create(**data)
        review.rating = 6
        with self.assertRaises(ValidationError): review.save()
        review.rating = 4; review.comment = "x"*2001
        with self.assertRaises(ValidationError): review.save()
        ReviewReply.objects.create(review=review, user=self.user, content="Cảm ơn")
        AIReviewAnalysis.objects.create(review=review, sentiment="positive", summary="Hài lòng")
        with self.assertRaises(ValidationError):
            AIReviewAnalysis.objects.create(review=review, sentiment="neutral", summary="Khác")

    def test_promotion_product_links_payment_and_ai(self):
        promotion = Promotion.objects.create(code="NEW", name="Ưu đãi", discount_type="percent", discount_value=10, start_date=date(2030,1,1), end_date=date(2030,2,1))
        PromotionService.objects.create(promotion=promotion, service=self.service)
        with self.assertRaises(ValidationError): PromotionService.objects.create(promotion=promotion, service=self.service)
        promotion.discount_value = 101
        with self.assertRaises(ValidationError): promotion.save()
        product = CareProduct.objects.create(name="Sản phẩm", product_type="Serum", description="Mô tả")
        ServiceProduct.objects.create(service=self.service, product=product)
        with self.assertRaises(ValidationError): ServiceProduct.objects.create(service=self.service, product=product)
        invoice = Invoice.objects.create(appointment=self.appointment(status="confirmed"), subtotal=500000, total_amount=500000)
        Payment.objects.create(invoice=invoice, amount=500000, payment_method="spa")
        Payment.objects.create(invoice=invoice, amount=500000, payment_method="online", transaction_code="unique")
        with self.assertRaises(ValidationError): Payment.objects.create(invoice=invoice, amount=500000, payment_method="online", transaction_code="unique")
        AIRecommendation.objects.create(customer=self.customer, input_data={"budget":500000}, recommended_services=[self.service.pk], reason="Phù hợp")
        with self.assertRaises(ValidationError):
            AIRecommendation.objects.create(customer=self.customer, input_data={"budget":500000}, recommended_services=[1,2,3,4], reason="Sai số lượng")

    def test_cross_customer_review_rejected(self):
        appointment = self.appointment(status="completed")
        other = User.objects.create_user("other", "other@example.com", "StrongTest!9372")
        customer = Customer.objects.create(user=other, full_name="Khác", phone="0911111111")
        with self.assertRaises(ValidationError):
            Review.objects.create(appointment=appointment, customer=customer, service=self.service, rating=4)

    def test_online_payment_after_start_rejected(self):
        EmployeeSchedule.objects.create(employee=self.employee, work_date=date(2020,1,1), start_time=time(9), end_time=time(18))
        invoice = Invoice.objects.create(appointment=self.appointment(status="confirmed", appointment_date=date(2020,1,1)), subtotal=500000, total_amount=500000)
        with self.assertRaises(ValidationError):
            Payment.objects.create(invoice=invoice, amount=500000, payment_method="online")
        Payment.objects.create(invoice=invoice, amount=500000, payment_method="spa")
