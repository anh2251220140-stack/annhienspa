"""Offline FR-22 browser acceptance: real services UI/API, temporary SQLite, SDK HTTP mock."""
import argparse
from contextlib import ExitStack
from contextvars import ContextVar
from html import escape
import json
from pathlib import Path
from secrets import token_urlsafe
import signal
import sys
from tempfile import TemporaryDirectory
from threading import Event
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.modules["tools.fr22_browser_test"] = sys.modules[__name__]
SCENARIO = ContextVar("fr22_browser_scenario", default="ai")
OWNER_ID = None
PROFILES = {}
COUNTERS = {"mock_http_requests": 0}


class ScenarioMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        scenario = request.session.get("fr22_scenario", "ai")
        token = SCENARIO.set(scenario)
        try:
            response = self.get_response(request)
        finally:
            SCENARIO.reset(token)
        if request.path == "/services.html" and response.status_code == 200:
            notice = ('<aside style="padding:16px;background:#fff8f1;color:#3a2419;border:1px solid #c6a07e" role="status">'
                '<strong>FR-22 — SQLite tạm, dữ liệu giả, HTTP mock. Không gọi Gemini thật.</strong> '
                f'Chế độ: {escape(scenario)}. Hồ sơ: {escape(request.session.get("fr22_profile","KH-01"))}. '
                '<a href="/acceptance/fr22/?profile=KH-01">KH-01 · Cơ thể · 300.000đ</a> · '
                '<a href="/acceptance/fr22/?profile=KH-02">KH-02 · Da nhạy cảm · 500.000đ</a> · '
                '<a href="/acceptance/fr22/?profile=KH-03">KH-03 · Thư giãn · 700.000đ</a><br>'
                '<a href="/acceptance/fr22/?scenario=ai">AI mock</a> · '
                '<a href="/acceptance/fr22/?scenario=fallback">Timeout → dự phòng</a> · '
                '<a href="/acceptance/fr22/?scenario=quota">Quota → dự phòng</a> · '
                '<a href="/acceptance/fr22/?scenario=invalid">JSON lỗi → dự phòng</a>. '
                'Chọn chế độ rồi gửi form bên dưới; giữ khoảng cách 5 giây giữa các lượt hỏi.</aside>')
            html = response.content.decode(response.charset)
            # Do not modify the production template or app.js.
            position = html.index('>', html.index('<body')) + 1
            response.content = html[:position] + notice + html[position:]
            response.headers.pop('Content-Length', None)
        return response


def configure_preview(stack, folder):
    from tools.chat_sqlite import configure
    configure(stack, folder)  # Blocks dotenv, MySQL, sockets, real HTTP and PayOS.
    from django.conf import settings
    settings.SESSION_COOKIE_NAME = "annhien_fr22_preview_session"
    settings.CSRF_COOKIE_NAME = "annhien_fr22_preview_csrf"
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.AI_CHAT_ENABLED = False
    settings.AI_PROVIDER = "gemini"
    settings.AI_PERSONALIZATION_EXPORT_APPROVED = True  # Synthetic-only process.
    settings.AI_REVIEW_EXPORT_APPROVED = False
    settings.AI_PAID_CALLS_APPROVED = False
    settings.AI_GEMINI_API_KEY = "fake-fr22-browser-key-not-a-credential"
    settings.AI_GEMINI_REQUESTS_APPROVED = True
    settings.AI_GEMINI_FREE_TIER_CONFIRMED = True  # Mock transport only, never live.
    settings.AI_GEMINI_FREE_TIER_ONLY = True
    settings.MIDDLEWARE = [*settings.MIDDLEWARE, "tools.fr22_browser_test.ScenarioMiddleware"]
    from django.contrib.auth import login
    from django.http import JsonResponse, HttpResponseRedirect
    from django.urls import path
    from django.views.decorators.http import require_GET

    @require_GET
    def enter(request):
        from accounts.models import User
        from django.db import connection
        if request.META.get('REMOTE_ADDR') != '127.0.0.1' or connection.vendor != 'sqlite':
            return JsonResponse({'error': 'Loopback SQLite only'}, status=403)
        scenario = request.GET.get('scenario', request.session.get('fr22_scenario','ai'))
        profile = request.GET.get('profile', request.session.get('fr22_profile','KH-01'))
        if scenario not in {'ai', 'fallback', 'quota', 'invalid'} or profile not in PROFILES:
            return JsonResponse({'error': 'Unknown fixture scenario'}, status=400)
        if request.user.pk != PROFILES[profile]:
            login(request, User.objects.get(pk=PROFILES[profile]), backend=settings.AUTHENTICATION_BACKENDS[0])
        request.session['fr22_scenario'] = scenario
        request.session['fr22_profile'] = profile
        return HttpResponseRedirect('/services.html#recommendations')

    @require_GET
    def state(request):
        from ai_features.models import AIRecommendation
        from services.models import Service
        from products.models import CareProduct
        if request.user.pk not in PROFILES.values():
            return JsonResponse({'error': 'Fixture login required'}, status=403)
        latest = AIRecommendation.objects.filter(customer__user=request.user).order_by('-pk').first()
        return JsonResponse({'database': 'temporary SQLite', 'mock_only': True, **COUNTERS,
            'services': Service.objects.count(), 'products': CareProduct.objects.count(),
            'latest': json.loads(latest.reason) if latest else None})

    from config.urls import urlpatterns
    urls = ModuleType('fr22_browser_urls')
    urls.urlpatterns = [path('acceptance/fr22/', enter), path('acceptance/fr22/state/', state), *urlpatterns]
    sys.modules[urls.__name__] = urls
    settings.ROOT_URLCONF = urls.__name__

    import httpx
    def handler(request):
        if (request.url.host != 'generativelanguage.googleapis.com' or request.method != 'POST'
                or request.url.path != '/v1beta/models/gemini-3.5-flash-lite:generateContent'):
            raise RuntimeError('Unknown mock operation')
        COUNTERS['mock_http_requests'] += 1
        scenario = SCENARIO.get()
        if scenario == 'fallback':
            raise httpx.ReadTimeout('Offline fixture timeout')
        if scenario == 'quota':
            return httpx.Response(429, request=request, json={'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED'}})
        payload = json.loads(json.loads(request.content)['contents'][0]['parts'][0]['text'])
        frequencies={r['serviceId']:r['count'] for r in payload.get('serviceHistory',[])}
        ranked=sorted(payload['candidates'],key=lambda r:(frequencies.get(r['id'],0),not r.get('skinCareMatch'),float(r['price'])))
        items = [{'id': row['id'], 'reason': ('Dữ liệu giả lập: chưa xuất hiện trong phạm vi lịch sử được cung cấp; cân nhắc bổ sung theo nhu cầu và ngân sách.'
                  if not frequencies.get(row['id']) else f"Dữ liệu giả lập: đã hoàn thành {frequencies[row['id']]} lượt; không tự ưu tiên lặp lại.")}
                 for row in ranked[:3]]
        text = 'not JSON' if scenario == 'invalid' else json.dumps({'items': items})
        return httpx.Response(200, request=request, json={'candidates': [{'content': {'role': 'model', 'parts': [{'text': text}]}}]})
    transport = httpx.MockTransport(handler)
    def send(client, request, **kwargs):
        for hook in client.event_hooks.get('request', []):
            hook(request)
        return transport.handle_request(request)
    stack.enter_context(patch.object(httpx.Client, 'send', send))  # No real sender restored.


def create_fixture_schema():
    """No migration commands: build current models only in the owned empty SQLite."""
    from django.apps import apps
    from django.db import connection
    if connection.vendor != 'sqlite' or connection.introspection.table_names():
        raise RuntimeError('Requires a new, empty isolated SQLite database')
    with connection.schema_editor() as editor:
        for model in apps.get_models():
            if model._meta.managed and not model._meta.proxy:
                editor.create_model(model)


def seed_preview():
    global OWNER_ID
    from datetime import time, timedelta
    from django.utils import timezone
    from accounts.models import Customer, User
    from services.models import Service, ServiceCategory
    from products.models import CareProduct, ServiceProduct
    from employees.models import Employee, EmployeeService, EmployeeSchedule
    from appointments.models import Appointment
    category = ServiceCategory.objects.create(name='Dịch vụ nghiệm thu giả lập')
    definitions = [('Chăm sóc da cơ bản',300000,60,'face','Da thường, da khô'),
        ('Liệu trình cấp ẩm',450000,75,'face','Da khô; da nhạy cảm — cần chuyên viên xác nhận'),
        ('Chăm sóc da chuyên sâu',480000,90,'face','Da thường, da khô'),
        ('Massage đá nóng',590000,90,'relax','Người trưởng thành có nhu cầu thư giãn'),
        ('Chăm sóc cơ thể dịu nhẹ',280000,60,'body','Người trưởng thành cần chăm sóc cơ thể'),
        ('Chăm sóc tóc và da đầu',250000,45,'hair','Người trưởng thành cần chăm sóc tóc'),
        ('Chăm sóc da nhanh',180000,30,'face','Da thường'),
        ('Thư giãn cơ thể nhẹ nhàng',220000,45,'body','Người trưởng thành cần thư giãn nhẹ'),
        ('Massage thư giãn nhẹ',400000,60,'relax','Người trưởng thành muốn massage nhẹ nhàng')]
    services = [Service.objects.create(category=category,name=name+' (giả lập)',price=price,duration_minutes=minutes,
        care_group=group,description='Mô tả nghiệm thu giả lập: chăm sóc dịu nhẹ, không cam kết điều trị.',
        suitable=suitable,benefits='Đáp ứng nhu cầu '+group+' trong danh mục giả lập.',
        steps='Tiếp nhận nhu cầu; thao tác chăm sóc hoặc massage bằng tay theo nhóm dịch vụ; hướng dẫn chăm sóc.',
        note='Không áp dụng cho da nhạy cảm.' if i==2 else 'Chưa có dữ liệu chống chỉ định cụ thể; trao đổi với chuyên viên trước khi sử dụng.')
        for i,(name,price,minutes,group,suitable) in enumerate(definitions)]
    product_data=[('Sữa dưỡng thể',120000,'Không áp dụng','body',[4,7],'Nước, glycerin — công thức minh họa'),
        ('Kem dưỡng ẩm',180000,'Da khô; Da nhạy cảm','face',[0,1],'Nước, glycerin — công thức minh họa'),
        ('Dầu massage',150000,'Không áp dụng','relax',[3,8],'Dầu thực vật — công thức minh họa'),
        ('Sản phẩm chăm sóc tóc',140000,'Không áp dụng','hair',[5],'Nước, chất làm sạch dịu nhẹ — công thức minh họa'),
        ('Chăm sóc da sau liệu trình',220000,'Da thường; Da khô','face',[2],'Nước, glycerin — công thức minh họa')]
    for name,price,skin,group,indexes,ingredients in product_data:
        product=CareProduct.objects.create(name=name+' giả lập',product_type='Sản phẩm kiểm thử',
            description=f'Giá minh họa: {price:,} VND. Mô tả giả lập cho nghiệm thu; không phải công thức/giá sản phẩm thật.'.replace(',','.'),
            skin_type=skin,suitable_for=skin,care_group=group,benefits='Chăm sóc tại nhà theo dữ liệu minh họa, không có cam kết y khoa.',
            ingredients=ingredients,usage_instructions='Trao đổi với chuyên viên; làm theo hướng dẫn giả lập trên danh mục.',
            note='Thông số giả lập, không xác nhận phù hợp y khoa.')
        for i in indexes:ServiceProduct.objects.create(service=services[i],product=product)
    specs=[('KH-01','Da thường','Chăm sóc cơ thể, giảm mệt mỏi',300000,'Nhẹ nhàng, tránh tinh dầu',4,3),
           ('KH-02','Da nhạy cảm','Dưỡng ẩm, cải thiện da khô',500000,'Dịu nhẹ, cấp ẩm',0,4),
           ('KH-03','Da khô','Thư giãn, giảm căng thẳng',700000,'Massage nhẹ nhàng, thư giãn',3,3)]
    employee=Employee.objects.create(full_name='Chuyên viên giả lập FR22',specialty='Nghiệm thu dữ liệu giả')
    for profile,skin,needs,budget,preferences,index,visits in specs:
        user=User.objects.create_user(profile.lower(),'fixture-'+profile.lower()+'@example.test',token_urlsafe(24))
        customer=Customer.objects.create(user=user,full_name='Hồ sơ giả lập '+profile,phone='123',skin_type=skin,
            budget=budget,care_needs=json.dumps([needs]),preferences=preferences)
        PROFILES[profile]=user.pk
        EmployeeService.objects.create(employee=employee,service=services[index])
        for visit in range(visits):
            day=timezone.localdate()-timedelta(days=3+len(PROFILES)*10+visit*3)
            EmployeeSchedule.objects.create(employee=employee,work_date=day,start_time=time(8),end_time=time(17))
            start=time(9);minutes=services[index].duration_minutes
            end=(timezone.datetime.combine(day,start)+timedelta(minutes=minutes)).time()
            Appointment.objects.create(customer=customer,service=services[index],employee=employee,appointment_date=day,
                start_time=start,end_time=end,status='completed')
    OWNER_ID=PROFILES['KH-01']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['serve'])
    parser.parse_args()
    if Path(sys.prefix).resolve() != (ROOT/'.venv').resolve():
        raise RuntimeError('Use project .venv')
    with TemporaryDirectory(prefix='annhien-fr22-browser-') as folder, ExitStack() as stack:
        configure_preview(stack,Path(folder))
        from django.core.wsgi import get_wsgi_application
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from tools.chat_sqlite import LocalServer, LocalRequests, running_server, probe_login
        with LocalServer(('127.0.0.1',8004),LocalRequests) as server:
            create_fixture_schema()
            seed_preview()
            server.set_app(StaticFilesHandler(get_wsgi_application()))
            with running_server(server) as worker:
                status,_ = probe_login(server)
                print(f'Ready http://127.0.0.1:8004/acceptance/fr22/ | HTTP {status} | SQLite only | 9 services / 5 products / 3 profiles | NO live AI | Ctrl+C to stop',flush=True)
                wait=Event()
                while worker.is_alive():
                    wait.wait(.2)


if __name__ == '__main__':
    if hasattr(signal,'SIGBREAK'):
        signal.signal(signal.SIGBREAK,signal.default_int_handler)
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped; owned temporary SQLite/media cleaned up.',flush=True)
    except Exception:
        print('Stopped safely. No key, exception payload or database fallback is displayed.',flush=True)
        raise SystemExit(1)
