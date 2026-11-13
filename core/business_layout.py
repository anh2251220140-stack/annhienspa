from django.templatetags.static import static
# Explicit Figma field layout; adding a model field never silently changes the UI.
LAYOUTS={
'categories': [('Thông tin danh mục','folder','name description',False)],
'services': [('Thông tin dịch vụ','leaf','name category price duration_minutes description image_preset image',False),('Nội dung chi tiết liệu trình','note','introduction benefits steps suitable note gallery_preset gallery care_group',True)],
'products': [('Thông tin sản phẩm','droplet','name product_type image_preset image care_group description',False),('Thông tin chăm sóc','leaf','ingredients usage_instructions note skin_type suitable_for benefits services',False)],
'employees': [('Hồ sơ & liên hệ','heart','full_name avatar_preset avatar email phone',False),('Chuyên môn & dịch vụ','leaf','specialty services description',False)],
'promotions': [('Thông tin chương trình','star','name code discount_type discount_value start_date end_date',False),('Nội dung & điều kiện','note','description detail conditions note note_is_informational badge accent aliases min_amount max_discount per_customer_limit',False),('Phạm vi dịch vụ áp dụng','leaf','scope_note services',False)],
'schedules': [('Ca làm việc','calendar','work_date start_time end_time status note',False)]}

def groups_for(form,module):
    result=[]
    for title,icon,names,accordion in LAYOUTS[module]:
        fields=[]
        for name in names.split():
            field=form[name]
            value=field.value()
            if name=='services':value=', '.join(str(o.name) for o in form.instance.services.all()) if form.instance.pk else ''
            elif name=='note_is_informational':value='Chỉ hướng dẫn khách hàng' if value else 'Kiểm tra cùng Điều kiện áp dụng'
            elif getattr(field.field,'choices',None):value=dict(field.field.choices).get(value,value)
            preview=static('images/'+str(field.value())) if name.endswith('_preset') and field.value() else ''
            fields.append({'preview':preview,'bound':field,'name':name,'value':value,'multiline':field.field.widget.__class__.__name__=='Textarea','file':field.field.widget.input_type=='file' if hasattr(field.field.widget,'input_type') else False})
        result.append({'title':title,'icon':icon,'fields':fields,'accordion':accordion})
    return result
