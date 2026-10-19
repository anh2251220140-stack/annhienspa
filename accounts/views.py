from django.contrib.auth import login, logout
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.debug import sensitive_post_parameters
from .forms import LoginForm, RegistrationForm


def landing(user):
    return "core:admin-dashboard" if user.role == "Admin" else "core:home"

@sensitive_post_parameters("password", "confirmPassword")
@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(landing(request.user))
    form = LoginForm(request.POST if request.method == "POST" else None, request=request)
    if request.method == "POST" and form.is_valid():
        login(request, form.user)
        return redirect(landing(form.user))
    return render(request, "pages/login.html", {"form": form})

@sensitive_post_parameters("password", "confirmPassword")
@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect(landing(request.user))
    form = RegistrationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            form.add_error(None, "Email hoặc tên đăng nhập đã được sử dụng. Vui lòng kiểm tra lại.")
        else:
            return redirect("/login.html?registered=success")
    return render(request, "pages/register.html", {"form": form})

@never_cache
@csrf_protect
@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:index")
