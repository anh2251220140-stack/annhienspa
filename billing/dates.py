"""Local calendar boundaries without requiring MySQL timezone tables."""
from datetime import datetime, time, timedelta
from django.utils import timezone


def boundaries(start, end):
    return (timezone.make_aware(datetime.combine(start, time.min)),
            timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min)))
