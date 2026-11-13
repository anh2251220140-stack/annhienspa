"""Apply dated schedules without deleting historical shift rows."""
from datetime import date, time, timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Employee, EmployeeSchedule
from appointments.models import Appointment


def spans(raw):
    result=[]
    try:
        for row in raw:
            a,b=[time.fromisoformat(v) for v in row]
            if a >= b or a.second or b.second: raise ValueError
            result.append((a,b))
    except (TypeError,ValueError): raise ValidationError("Ca phải có giờ bắt đầu < giờ kết thúc, theo phút, trong cùng ngày.")
    result.sort()
    if any(a[1]>b[0] for a,b in zip(result,result[1:])):raise ValidationError("Các khoảng giờ bị chồng chéo.")
    return result


def build_segments(work,breaks):
    work=spans(work);breaks=spans(breaks)
    if not work:raise ValidationError("Cần ít nhất một ca làm.")
    for a,b in breaks:
        if not any(s<=a<b<=e for s,e in work):raise ValidationError("Khoảng nghỉ phải nằm trọn trong một ca làm.")
    result=[]
    for a,b in work:
        cursor=a
        for s,e in breaks:
            if a<=s<e<=b:
                if cursor<s:result.append((cursor,s,"working"))
                result.append((s,e,"off"));cursor=e
        if cursor<b:result.append((cursor,b,"working"))
    return result


@transaction.atomic
def apply_plan(employee_id,data):
    employee=Employee.objects.select_for_update().get(pk=employee_id)
    try:
        start=date.fromisoformat(data['start_date']);end=date.fromisoformat(data['end_date'])
        mode=data['mode'];weekdays={int(v) for v in data.get('weekdays',[])}
    except (ValueError,KeyError,TypeError):raise ValidationError("Ngày hoặc thứ trong tuần không hợp lệ.")
    if start<timezone.localdate() or end<start or (end-start).days>365:raise ValidationError("Chọn khoảng ngày từ hôm nay, tối đa 366 ngày mỗi lần áp dụng.")
    if mode not in ('weekly','day','leave'):raise ValidationError("Kiểu lịch không hợp lệ.")
    if mode=='day' and start!=end:raise ValidationError("Ca ngoại lệ chỉ áp dụng một ngày.")
    if mode=='weekly' and (not weekdays or not weekdays<={0,1,2,3,4,5,6}):raise ValidationError("Chọn thứ Hai đến Chủ Nhật cần áp dụng.")
    segments=[(time.min,time(23,59,59),'off')] if mode=='leave' else build_segments(data.get('work',[]),data.get('breaks',[]))
    days=[start+timedelta(days=i) for i in range((end-start).days+1) if mode!='weekly' or (start+timedelta(days=i)).weekday() in weekdays]
    if not days:raise ValidationError("Không có ngày phù hợp trong khoảng đã chọn.")
    affected=[]
    for a in Appointment.objects.filter(employee=employee,appointment_date__in=days).exclude(status='cancelled').select_related('customer'):
        if not any(s<=a.start_time<a.end_time<=e and state=='working' for s,e,state in segments):
            affected.append(f"LH-{a.pk:06d}: {a.appointment_date:%d/%m/%Y} {a.start_time:%H:%M}–{a.end_time:%H:%M}, {a.customer.full_name}")
    if affected:raise ValidationError(["Chưa áp dụng. Ca/ngày nghỉ ảnh hưởng các lịch sau; cần xử lý với khách trước:"]+affected)
    note=str(data.get('note','')).strip()
    if len(note)>1000:raise ValidationError("Ghi chú tối đa 1000 ký tự.")
    # Preserve old rows for historical inspection; only active rows govern booking.
    EmployeeSchedule.objects.filter(employee=employee,work_date__in=days,is_active=True).update(is_active=False)
    for day in days:
        for a,b,status in segments:
            EmployeeSchedule.objects.create(employee=employee,work_date=day,start_time=a,end_time=b,status=status,note=note)
    return {'days':len(days),'shifts':len(days)*len(segments)}
