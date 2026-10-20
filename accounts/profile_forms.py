from django import forms
from django.core.validators import RegexValidator
from .models import Customer, User
from core.business_forms import BaseForm

class CustomerProfileForm(BaseForm):
    class Meta:
        model=Customer;fields=['full_name','phone','avatar','skin_type','care_needs','preferences','budget']
    def clean_phone(self):
        value=self.cleaned_data['phone'];RegexValidator(r'^\+?[\d ()-]{8,20}$','Số điện thoại không hợp lệ.')(value);return value

class IdentityForm(forms.ModelForm):
    class Meta:
        model=User;fields=['username','email']
    def clean_email(self):
        value=self.cleaned_data['email'].lower().strip()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=value).exists():raise forms.ValidationError('Email đã được sử dụng.')
        return value
