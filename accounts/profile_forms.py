from django import forms
from django.db import models
from .models import Customer, User
from .forms import CustomerPhoneField
from core.business_forms import BaseForm

class CustomerProfileForm(BaseForm):
    phone = CustomerPhoneField()

    class Meta:
        model=Customer;fields=['full_name','phone','avatar','skin_type','care_needs','preferences','budget']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound and self.instance.pk is not None:
            submitted = self.data.get(self.add_prefix("phone"))
            if submitted is None or submitted.strip() == self.instance.phone.strip():
                self.fields.pop("phone")

    def save(self, commit=True):
        if not commit or "phone" in self.fields:
            return super().save(commit=commit)

        customer = super().save(commit=False)
        # ModelForm validated the edited fields. Leave a legacy phone outside this write.
        models.Model.save(customer, update_fields=self.fields)
        self.save_m2m()
        return customer

class IdentityForm(forms.ModelForm):
    class Meta:
        model=User;fields=['username','email']
    def clean_email(self):
        value=self.cleaned_data['email'].lower().strip()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=value).exists():raise forms.ValidationError('Email đã được sử dụng.')
        return value
