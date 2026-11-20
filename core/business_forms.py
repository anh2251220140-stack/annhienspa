import json
from pathlib import Path
from django.conf import settings
from django import forms
from django.core.exceptions import ValidationError
from services.models import Service, ServiceCategory
from products.models import CareProduct
from employees.models import Employee, EmployeeSchedule
from promotions.models import Promotion
from promotions.services import policy

class NamedChoices(forms.ModelMultipleChoiceField):
    def label_from_instance(self,obj):return obj.name + (" (Tạm ngừng)" if not obj.is_active else "")

LABELS={"name":"Tên", "description":"Mô tả", "category":"Danh mục", "price":"Giá (VND)","duration_minutes":"Thời lượng (phút)",
"image":"Tải ảnh đại diện", "avatar":"Tải ảnh đại diện", "gallery":"Tải ảnh chi tiết", "image_preset":"Hình minh họa", "avatar_preset":"Hình minh họa", "gallery_preset":"Ảnh chi tiết",
"product_type":"Danh mục", "skin_type":"Loại da phù hợp — mỗi dòng một giá trị", "suitable_for":"Đối tượng sử dụng — mỗi dòng một giá trị", "benefits":"Công dụng", "ingredients":"Thành phần", "usage_instructions":"Cách sử dụng",
"full_name":"Họ và tên", "email":"Email", "phone":"Số điện thoại", "specialty":"Chuyên môn", "services":"Dịch vụ liên kết",
"code":"Mã khuyến mãi", "discount_type":"Hình thức ưu đãi", "discount_value":"Giá trị ưu đãi", "min_amount":"Giá trị tối thiểu", "max_discount":"Giảm tối đa",
"start_date":"Ngày bắt đầu", "end_date":"Ngày kết thúc", "work_date":"Ngày làm việc", "start_time":"Giờ bắt đầu", "end_time":"Giờ kết thúc", "status":"Trạng thái", "note":"Lưu ý",
"introduction":"Giới thiệu", "steps":"Quy trình thực hiện", "suitable":"Đối tượng phù hợp", "care_group":"Nhóm chăm sóc (catalog)",
"detail":"Nội dung chi tiết", "conditions":"Điều kiện áp dụng — mỗi dòng một điều kiện", "badge":"Nhãn chương trình", "accent":"Màu nhấn theo catalog", "aliases":"Mã thay thế — mỗi dòng một mã", "scope_note":"Ghi chú phạm vi áp dụng"}

class BaseForm(forms.ModelForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        presets=[('', 'Chưa chọn ảnh có sẵn')]+[(p.name,p.name) for p in sorted((settings.BASE_DIR/'static/images').glob('*')) if p.suffix.lower() in ('.jpg','.jpeg','.png','.webp')]
        for name,field in list(self.fields.items()):
            if name.endswith('_preset'):
                self.fields[name]=field=forms.ChoiceField(choices=presets,required=False)
            field.label=LABELS.get(name,name)
            if isinstance(field,forms.DateField):field.widget=forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'})
            if isinstance(field,forms.TimeField):field.widget=forms.TimeInput(format='%H:%M',attrs={'type':'time'})
            if isinstance(field.widget,forms.Textarea):field.widget.attrs['rows']=3
            if isinstance(field,forms.ImageField):field.widget.attrs['accept']='image/jpeg,image/png,image/webp'
        if 'phone' in self.fields:self.fields['phone'].widget=forms.TextInput(attrs={'type':'tel'})
    def clean(self):
        data=super().clean()
        for name in ('image','avatar','gallery'):
            upload=data.get(name)
            if hasattr(upload,'content_type'):
                if upload.size>5*1024*1024 or upload.content_type not in ('image/jpeg','image/png','image/webp'):
                    self.add_error(name,'Chỉ nhận ảnh JPEG/PNG/WebP thật, tối đa 5 MB.')
                if name+'_preset' in self.fields:data[name+'_preset']=''
            elif data.get(name+'_preset') and name+'_preset' in self.changed_data:data[name]=False
        return data

class CategoryForm(BaseForm):
    class Meta:
        model=ServiceCategory;fields=['name','description']

class ServiceForm(BaseForm):
    class Meta:
        model=Service;fields=['name','category','price','duration_minutes','description','image_preset','image','introduction','benefits','steps','suitable','note','gallery_preset','gallery','care_group']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['category'].label_from_instance=lambda obj:obj.name + (" (Tạm ngưng)" if not obj.is_active else "")
        self.fields['category'].label="Danh mục dịch vụ"
        self.fields['care_group'].label="Nhóm hiển thị trên trang khách hàng"
        self.fields['name'].label='Tên dịch vụ';self.fields['benefits'].label='Lợi ích — mỗi dòng một ý'
        self.fields['price'].min_value=0;self.fields['duration_minutes'].min_value=1

    def clean_steps(self):
        raw = self.cleaned_data.get('steps', '')
        if not raw.strip():
            return '[]'
        try:
            steps = json.loads(raw)
        except (ValueError, TypeError):
            raise ValidationError('Nhập tên và mô tả riêng cho từng bước trong bộ nhập quy trình.')
        if not isinstance(steps, list):
            raise ValidationError('Quy trình phải là danh sách các bước.')
        for step in steps:
            if (not isinstance(step, dict) or set(step) != {'title', 'description'}
                    or any(not isinstance(step[k], str) or not step[k].strip()
                           for k in ('title', 'description'))):
                raise ValidationError('Mỗi bước phải có tên và mô tả không để trống.')
        if any(step['title'].strip().casefold() == 'hoàn thiện' for step in steps[:-1]):
            raise ValidationError('Chỉ bước cuối cùng được mang tên Hoàn thiện.')
        return json.dumps(steps, ensure_ascii=False)

class ProductForm(BaseForm):
    services=NamedChoices(queryset=Service.objects.all(),required=False,widget=forms.CheckboxSelectMultiple)
    class Meta:
        model=CareProduct;fields=['name','product_type','image_preset','image','care_group','description','ingredients','usage_instructions','note','skin_type','suitable_for','benefits','services']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.fields['name'].label='Tên sản phẩm';self.fields['description'].label='Mô tả ngắn'
        self.fields['care_group'].label='Nhóm hiển thị trên trang khách hàng'

class EmployeeForm(BaseForm):
    services=NamedChoices(queryset=Service.objects.all(),required=False,widget=forms.CheckboxSelectMultiple)
    class Meta:
        model=Employee;fields=['full_name','avatar_preset','avatar','email','phone','specialty','services','description']
    def clean_phone(self):
        import re
        value=self.cleaned_data['phone']
        if value and not re.fullmatch(r'\+?[\d ()-]{8,20}',value):raise ValidationError('Số điện thoại không hợp lệ.')
        return value

class PromotionForm(BaseForm):
    services=NamedChoices(queryset=Service.objects.all(),required=False,widget=forms.CheckboxSelectMultiple)
    class Meta:
        model=Promotion;fields=['name','code','discount_type','discount_value','start_date','end_date','description','detail','conditions','note','note_is_informational','badge','accent','aliases','min_amount','max_discount','per_customer_limit','scope_note','services']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = 'Tên chương trình'
        self.fields['description'].label = 'Mô tả ngắn'
        self.fields['accent'].required = False
        self.fields['per_customer_limit'].label = 'Giới hạn lượt mỗi khách (tùy chọn)'
        self.fields['per_customer_limit'].min_value = 1
        self.fields['note_is_informational'].label = 'Lưu ý chỉ dùng để hướng dẫn khách hàng'
        self.fields['note_is_informational'].widget.attrs['aria-describedby'] = 'promotion-note-policy-help'
        if self.instance._state.adding:
            self.initial.setdefault('note_is_informational', True)
    def clean(self):
        data=super().clean()
        import re
        if (self.instance.pk and not self.instance.note_is_informational
                and data.get('note_is_informational') and 'per_customer_limit' in data):
            previous_limit, _ = policy(self.instance)
            next_limit, _ = policy(Promotion(conditions=data.get('conditions', ''),
                                             per_customer_limit=data['per_customer_limit']))
            if previous_limit is not None and (next_limit is None or next_limit > previous_limit):
                self.add_error('per_customer_limit', 'Khi chuyển Lưu ý sang hướng dẫn, hãy giữ giới hạn lượt hiện hành trong ô này.')
        code=data.get('code','').upper();aliases=[v.strip().upper() for v in data.get('aliases','').splitlines() if v.strip()]
        codes=[code]+aliases
        if any(not re.fullmatch(r'[A-Z0-9_-]{2,50}',v) for v in codes):raise ValidationError('Mã chính/thay thế gồm 2–50 ký tự chữ, số, gạch ngang hoặc gạch dưới.')
        if len(set(codes))!=len(codes):raise ValidationError('Mã chính/thay thế bị trùng.')
        for other in Promotion.objects.exclude(pk=self.instance.pk):
            if set(codes)&{other.code.upper(),*[v.strip().upper() for v in other.aliases.splitlines()]}:raise ValidationError('Mã chính/thay thế đã được chương trình khác sử dụng.')
        data['code']=code;data['aliases']='\n'.join(aliases);data['accent']=data.get('accent') or self.instance.accent
        return data

class ScheduleForm(BaseForm):
    class Meta:
        model=EmployeeSchedule;fields=['work_date','start_time','end_time','status','note']

REGISTRY={'categories':CategoryForm,'services':ServiceForm,'products':ProductForm,'employees':EmployeeForm,'promotions':PromotionForm}
