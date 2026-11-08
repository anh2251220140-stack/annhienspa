from django import forms

class BookingForm(forms.Form):
    service = forms.IntegerField(min_value=1)
    employee = forms.IntegerField(min_value=1)
    date = forms.DateField()
    time = forms.TimeField(input_formats=["%H:%M"])
    note = forms.CharField(required=False,max_length=500)

class TransitionForm(forms.Form):
    status = forms.ChoiceField(choices=[(x,x) for x in ("pending","confirmed","completed","cancelled")])
    employee = forms.IntegerField(required=False,min_value=1)
    consent = forms.BooleanField(required=False)
    reason = forms.CharField(required=False,max_length=500)
    expected_employee = forms.IntegerField(required=False, min_value=1)
    expected_updated_at = forms.DateTimeField(required=False)
    consent_method = forms.ChoiceField(required=False, choices=[("in_person", "Trực tiếp"), ("phone", "Điện thoại"), ("other", "Kênh khác")])
    consent_note = forms.CharField(required=False, max_length=500)
    consent_at = forms.DateTimeField(required=False)
    no_show = forms.BooleanField(required=False)
