"""Pure/ORM-mocked step decoding tests: no database or provider calls."""
import json
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch
from django.test import TestCase as DjangoTestCase

from core.catalog_data import catalog, service_steps
from core.business_forms import ServiceForm
from services.models import Service, ServiceCategory


class ServiceStepsJSONTests(TestCase):
    def test_legacy_lines_keep_existing_values(self):
        raw = "Bước 1: Làm sạch.\r\n\r\n2. Dưỡng ẩm.\n"
        self.assertEqual(service_steps(raw), ["Bước 1: Làm sạch.", "2. Dưỡng ẩm."])

    def test_structured_title_description_and_order(self):
        rows = [{"title": "Tên riêng", "description": "Mô tả riêng."},
                {"title": "Hoàn thiện", "description": "Tư vấn tại nhà."}]
        self.assertEqual(service_steps(json.dumps(rows, ensure_ascii=False, indent=2)), rows)

    def test_no_step_count_cap(self):
        for count in (4, 5, 6, 8, 10, 21):
            with self.subTest(count=count):
                rows = [{"title": f"Tên {i}", "description": f"Nội dung {i}"} for i in range(count)]
                self.assertEqual(service_steps(json.dumps(rows)), rows)

    def test_empty_steps(self):
        for raw in (None, "", " \r\n ", "[]"):
            with self.subTest(raw=raw):
                self.assertEqual(service_steps(raw), [])

    def test_invalid_or_unknown_json_does_not_discard_legacy_text(self):
        for raw in ('[{bad', '{"title":"old text"}', '["old line"]',
                    '[{"title":"A","description":3}]',
                    '[{"title":"A","description":"B","extra":"C"}]'):
            with self.subTest(raw=raw):
                self.assertEqual(service_steps(raw), [raw])

    def test_admin_textfield_preserves_structured_data(self):
        raw = json.dumps([{"title": "Làm sạch", "description": "Mô tả giữ nguyên."}], ensure_ascii=False, indent=2)
        form = ServiceForm(instance=Service(steps=raw))
        self.assertEqual(form['steps'].value(), raw)
        self.assertEqual(form.fields['steps'].clean(raw), raw)

    def test_public_catalog_reads_json_and_legacy_without_mutating_models(self):
        category = ServiceCategory(id=1, name="Danh mục giả")
        structured = [{"title": "Tên bước", "description": "Mô tả bước"}]
        raw = json.dumps(structured, ensure_ascii=False)
        old = "Bước 1: Nội dung cũ.\nBước 2: Không thay đổi."
        service = Service(id=2, category=category, name="Dịch vụ giả", description="Mô tả gốc", price=Decimal(350000), duration_minutes=60, steps=raw)
        legacy = Service(id=1, category=category, name="Dịch vụ cũ", description="Giữ nguyên", price=Decimal(200000), duration_minutes=45, steps=old)
        with patch('core.catalog_data.Service.objects.filter') as services, \
             patch('core.catalog_data.CareProduct.objects.filter', return_value=[]), \
             patch('core.catalog_data.Employee.objects.filter') as staff, \
             patch('core.catalog_data.ServiceProduct.objects.filter', return_value=[]):
            services.return_value.select_related.return_value.order_by.return_value=[legacy,service]
            staff.return_value.prefetch_related.return_value=[]
            result=catalog()['services']
        services.return_value.select_related.return_value.order_by.assert_called_once_with('pk')
        services.assert_called_once_with(is_active=True,category__is_active=True)
        self.assertEqual(result[0]['steps'], old.splitlines())
        self.assertEqual(result[1]['steps'], structured)
        self.assertEqual(result[1]['description'], 'Mô tả gốc')
        self.assertEqual(service.steps, raw)
        self.assertEqual(legacy.steps, old)


class ServiceStepsAdminTests(TestCase):
    def clean_steps(self, value):
        form = ServiceForm()
        form.cleaned_data = {'steps': value}
        return form.clean_steps()

    def test_structured_steps_variable_counts(self):
        for count in (4, 5, 6, 8, 10, 21):
            rows = [{'title': f'Tên {i}', 'description': f'Mô tả {i}'} for i in range(count)]
            self.assertEqual(json.loads(self.clean_steps(json.dumps(rows))), rows)

    def test_reject_partial_malformed_and_legacy_on_write(self):
        from django.core.exceptions import ValidationError
        for raw in ('old line', '{}', '[null]', '[{"title":"A","description":""}]', '[{"title":"","description":"B"}]', '[{"title":"A","description":3}]'):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                self.clean_steps(raw)

    def test_completion_title_only_at_end(self):
        from django.core.exceptions import ValidationError
        rows = [{'title':'Hoàn thiện','description':'Kết thúc'}, {'title':'Massage','description':'Thư giãn'}]
        with self.assertRaises(ValidationError):
            self.clean_steps(json.dumps(rows))
        rows.reverse()
        self.assertEqual(json.loads(self.clean_steps(json.dumps(rows))), rows)

    def test_empty_steps_save_as_empty_array(self):
        self.assertEqual(self.clean_steps(''), '[]')


class ServiceStepsRoundTripTests(DjangoTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = ServiceCategory.objects.create(name='Danh mục giả lập')

    def test_admin_create_edit_roundtrip_and_invalid_post(self):
        from types import SimpleNamespace
        from django.test import RequestFactory
        from core.business_views import records
        from services.models import Service
        factory = RequestFactory()
        steps = [{'title': f'Tên {i}', 'description': f'Mô tả {i}'} for i in range(1, 22)]
        data = {'name':'Dịch vụ giả lập mới', 'category':self.category.pk,
                'price':'300000', 'duration_minutes':'60', 'description':'Chỉ kiểm thử',
                'steps':json.dumps(steps,ensure_ascii=False)}
        def post(pk=None):
            request = factory.post('/api/admin/services/', data)
            request.user = SimpleNamespace(is_authenticated=True,is_active=True,role='Admin')
            return records(request, 'services', pk)
        response = post()
        self.assertEqual(response.status_code,201,response.content)
        pk = json.loads(response.content)['item']['id']
        self.assertEqual(json.loads(Service.objects.get(pk=pk).steps),steps)
        steps.reverse(); data['steps']=json.dumps(steps)
        self.assertEqual(post(pk).status_code,200)
        self.assertEqual(json.loads(Service.objects.get(pk=pk).steps),steps)
        data['steps']='[{"title":"A","description":""}]'
        self.assertEqual(post(pk).status_code,400)
        self.assertEqual(json.loads(Service.objects.get(pk=pk).steps),steps)
        request = factory.post('/api/admin/services/',data)
        request.user = SimpleNamespace(is_authenticated=True,is_active=True,role='User')
        self.assertEqual(records(request,'services',pk).status_code,403)


class ServiceStepsDetailTests(TestCase):
    def render(self, raw):
        from django.template.loader import render_to_string
        from core.business_layout import groups_for
        form = ServiceForm(instance=Service(steps=raw, category_id=1))
        form.fields['category'].choices = [(1, 'Danh mục giả')]
        return render_to_string('partials/business_detail.html', {'module':'services', 'groups':groups_for(form,'services')})

    def test_json_counts_titles_descriptions_and_order(self):
        from core.business_layout import steps_for_detail
        for count in (4,5,6,8,10,21):
            rows = [{'title':f'Tên {i}', 'description':f'Mô tả {i}'} for i in range(1,count+1)]
            parsed = steps_for_detail(json.dumps(rows))
            self.assertEqual([s['number'] for s in parsed], [str(i).zfill(2) for i in range(1,count+1)])
            self.assertEqual([{k:s[k] for k in ('title','description')} for s in parsed],rows)
            html = self.render(json.dumps(rows))
            self.assertEqual(html.count('admin-service-procedure-number'),count)
            self.assertNotIn('&quot;title&quot;',html)
            self.assertNotIn('&quot;description&quot;',html)

    def test_legacy_matches_edit_and_user_prefix_handling(self):
        from core.business_layout import steps_for_detail
        raw = 'Bước 1: Làm sạch\r\n2. Massage\n\n3) 1.5% là nội dung gốc'
        self.assertEqual(steps_for_detail(raw),[
            {'number':'01','title':'Làm sạch','description':''},
            {'number':'02','title':'Massage','description':''},
            {'number':'03','title':'1.5% là nội dung gốc','description':''}])
        self.assertEqual(self.render(raw).count('admin-service-procedure-number'),3)

    def test_empty_and_invalid_json_safe_message(self):
        for raw in ('', '[]', ' \n ', '[{bad', '{"title":"Unknown schema"}'):
            html = self.render(raw)
            self.assertIn('Chưa có thông tin quy trình thực hiện.', html)
            self.assertNotIn('admin-service-procedure-number',html)
            self.assertNotIn('Unknown schema',html)

    def test_escaping_and_no_mutation(self):
        from core.business_layout import groups_for
        raw = json.dumps([{'title':'<img src=x onerror=alert(1)>','description':'<script>bad()</script>'}])
        html = self.render(raw)
        self.assertNotIn('<script>bad()',html)
        self.assertIn('&lt;script&gt;bad()',html)
        form = ServiceForm(instance=Service(steps=raw,category_id=1))
        form.fields['category'].choices=[(1,'Danh mục giả')]
        groups_for(form,'services')
        self.assertEqual(form['steps'].value(), raw)
        self.assertEqual(form.instance.steps, raw)
