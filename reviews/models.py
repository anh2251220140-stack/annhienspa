from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from core.models import TimestampedModel, ValidatedModel

class Review(TimestampedModel):
    appointment = models.OneToOneField("appointments.Appointment", on_delete=models.PROTECT, related_name="review")
    customer = models.ForeignKey("accounts.Customer", on_delete=models.PROTECT, related_name="reviews")
    service = models.ForeignKey("services.Service", on_delete=models.PROTECT, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.CharField(max_length=2000, blank=True, null=True)
    class Meta:
        db_table = "reviews"
        constraints = [models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="review_rating_range")]
    def clean(self):
        if self.appointment_id:
            appointment = self.appointment
            if appointment.status != "completed":
                raise ValidationError("Chỉ đánh giá lịch hẹn đã hoàn thành.")
            if self.customer_id != appointment.customer_id or self.service_id != appointment.service_id:
                raise ValidationError("Khách hàng và dịch vụ phải khớp lịch hẹn.")

class ReviewReply(ValidatedModel):
    review = models.ForeignKey(Review, on_delete=models.PROTECT, related_name="replies")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="review_replies")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "review_replies"
