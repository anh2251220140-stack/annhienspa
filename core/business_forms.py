from django import forms
from django.core.exceptions import ValidationError
from services.models import Service, ServiceCategory
from products.models import CareProduct
from employees.models import Employee, EmployeeSchedule
from promotions.models import Promotion

class NamedChoices(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj): return obj.name

class BaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {"name":"Tên", "description":"Mô tả", "is_active":"Hoạt động", "category":"Danh mục", "price":"Giá (VND)",
            "duration_minutes":"Thời lượng (phút)", "image":"Ảnh", "avatar":"Ảnh chuyên viên", "product_type":"Loại sản phẩm",
            "skin_type":"Loại da phù hợp", "suitable_for":"Đối tượng phù hợp", "benefits":"Công dụng", "ingredients":"Thành phần", "usage_instructions":"Cách sử dụng",
            "full_name":"Họ tên", "phone":"Số điện thoại", "specialty":"Chuyên môn", "services":"Dịch vụ liên kết",
            "code":"Mã khuyến mãi", "discount_type":"Hình thức giảm", "discount_value":"Giá trị giảm", "min_amount":"Giá trị tối thiểu", "max_discount":"Giảm tối đa",
            "start_date":"Ngày bắt đầu", "end_date":"Ngày kết thúc", "work_date":"Ngày làm việc", "start_time":"Giờ bắt đầu", "end_time":"Giờ kết thúc", "status":"Trạng thái", "note":"Ghi chú"}
        for name, field in self.fields.items():
            field.label = labels.get(name, name)
            if isinstance(field, forms.DateField): field.widget = forms.DateInput(format="%Y-%m-%d", attrs={"type":"date"})
            if isinstance(field, forms.TimeField): field.widget = forms.TimeInput(format="%H:%M", attrs={"type":"time"})
            if isinstance(field.widget, forms.Textarea): field.widget.attrs["rows"] = 3
            if isinstance(field, forms.ImageField): field.widget.attrs["accept"] = "image/jpeg,image/png,image/webp"
    def clean(self):
        data = super().clean()
        for name in ("image", "avatar"):
            image = data.get(name)
            if hasattr(image, "content_type") and (image.size > 5*1024*1024 or image.content_type not in ("image/jpeg","image/png","image/webp")):
                self.add_error(name, "Chỉ nhận JPEG/PNG/WebP tối đa 5 MB.")
        return data

class CategoryForm(BaseForm):
    class Meta:
        model = ServiceCategory
        fields = ["name","description","is_active"]

class ServiceForm(BaseForm):
    class Meta:
        model = Service
        fields = ["name","category","description","price","duration_minutes","image","is_active"]
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields["category"].label_from_instance = lambda obj: obj.name

class ProductForm(BaseForm):
    services = NamedChoices(queryset=Service.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)
    class Meta:
        model = CareProduct
        fields = ["name","product_type","description","skin_type","suitable_for","benefits","ingredients","usage_instructions","image","is_active","services"]

class EmployeeForm(BaseForm):
    services = NamedChoices(queryset=Service.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)
    class Meta:
        model = Employee
        fields = ["full_name","phone","specialty","description","avatar","is_active","services"]

class PromotionForm(BaseForm):
    services = NamedChoices(queryset=Service.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)
    class Meta:
        model = Promotion
        fields = ["code","name","description","discount_type","discount_value","min_amount","max_discount","start_date","end_date","is_active","services"]

class ScheduleForm(BaseForm):
    class Meta:
        model = EmployeeSchedule
        fields = ["work_date","start_time","end_time","status","note"]

REGISTRY = {"categories":CategoryForm, "services":ServiceForm, "products":ProductForm, "employees":EmployeeForm, "promotions":PromotionForm}
