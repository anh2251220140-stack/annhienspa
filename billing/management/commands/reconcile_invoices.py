"""Explicit, repeatable reconciliation. Default is strictly read-only."""
import json
from pathlib import Path

from django import forms
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment
from billing.models import Invoice, InvoiceDetail


class HistoricalInvoiceForm(forms.Form):
    appointment_id = forms.IntegerField(min_value=1)
    service_name = forms.CharField(max_length=150)
    subtotal = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    discount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    promotion_code = forms.CharField(max_length=50, required=False)
    evidence = forms.CharField(min_length=10, max_length=1700)

    def clean(self):
        d = super().clean()
        if d.get('discount', 0) > d.get('subtotal', 0):
            raise ValidationError('Khoản giảm không được vượt giá dịch vụ.')
        return d


class Command(BaseCommand):
    help = 'Audit missing invoices; apply ONLY an administrator-approved historical-price plan.'

    def add_arguments(self, parser):
        parser.add_argument('--plan', help='UTF-8 JSON list with explicit historical prices and evidence.')
        parser.add_argument('--admin-id', type=int)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--acknowledge-historical-prices', action='store_true')

    def handle(self, *args, **options):
        if not options['plan']:
            if options['apply']:raise CommandError('--apply requires a reviewed --plan.')
            missing = Appointment.objects.filter(status__in=['confirmed', 'completed'], invoice__isnull=True)
            self.stdout.write(json.dumps(list(missing.values('id', 'status', 'appointment_date', 'service_id')), default=str))
            self.stdout.write('READ ONLY: historical prices must be supplied with evidence; current catalog prices are never used.')
            return
        try:
            rows = json.loads(Path(options['plan']).read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:raise CommandError('Cannot read a valid JSON plan.') from exc
        if not isinstance(rows, list) or not rows:raise CommandError('Plan must be a nonempty JSON list.')
        cleaned = []
        for row in rows:
            if not isinstance(row, dict):raise CommandError('Each plan item must be an object.')
            form = HistoricalInvoiceForm(row)
            if not form.is_valid():raise CommandError(form.errors.as_json())
            cleaned.append(form.cleaned_data)
        ids = [r['appointment_id'] for r in cleaned]
        if len(ids) != len(set(ids)):raise CommandError('Duplicate appointment IDs in plan.')
        admin = User.objects.filter(pk=options['admin_id'], role='Admin', is_active=True).first()
        if options['apply'] and (not admin or not options['acknowledge_historical_prices']):
            raise CommandError('Apply requires active --admin-id and --acknowledge-historical-prices.')
        # Validate every item first, then apply all-or-nothing. Never alter appointments.
        with transaction.atomic():
            appointments = {a.pk:a for a in Appointment.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
            for r in cleaned:
                a = appointments.get(r['appointment_id'])
                if not a or a.status not in ('confirmed', 'completed'):
                    raise CommandError(f"LH-{r['appointment_id']}: must be confirmed/completed.")
                existing = Invoice.objects.filter(appointment=a).first()
                if existing:
                    self.stdout.write(f'LH-{a.pk}: existing invoice {existing.pk}; unchanged.')
                    continue
                total = r['subtotal'] - r['discount']
                self.stdout.write(f'LH-{a.pk}: subtotal={r["subtotal"]}, discount={r["discount"]}, total={total}; unpaid.')
                if options['apply']:
                    invoice = Invoice.objects.create(appointment=a, subtotal=r['subtotal'], discount_amount=r['discount'], total_amount=total,
                        promotion_code_snapshot=r['promotion_code'], historical_basis=f'Admin {admin.pk}; {timezone.now().isoformat()}; {r["evidence"]}')
                    InvoiceDetail.objects.create(invoice=invoice, service_id=a.service_id, service_name_snapshot=r['service_name'], unit_price=r['subtotal'], line_total=r['subtotal'])
        self.stdout.write('APPLIED. No payments created.' if options['apply'] else 'DRY RUN. No data written.')
