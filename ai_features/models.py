from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from core.models import ValidatedModel

class AIRecommendation(ValidatedModel):
    customer = models.ForeignKey("accounts.Customer", on_delete=models.PROTECT, related_name="ai_recommendations")
    input_data = models.JSONField()
    recommended_services = models.JSONField()
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "ai_recommendations"
    def clean(self):
        if not isinstance(self.recommended_services, list) or not 1 <= len(self.recommended_services) <= 3:
            raise ValidationError({"recommended_services": "Cần từ 1 đến 3 dịch vụ đề xuất."})

class AIReviewAnalysis(ValidatedModel):
    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Tích cực"
        NEUTRAL = "neutral", "Trung tính"
        NEGATIVE = "negative", "Tiêu cực"
    review = models.OneToOneField("reviews.Review", on_delete=models.PROTECT, related_name="ai_analysis")
    sentiment = models.CharField(max_length=20, choices=Sentiment.choices)
    summary = models.TextField()
    analyzed_at = models.DateTimeField(auto_now_add=True)
    themes = models.JSONField(default=list, blank=True)
    priority = models.CharField(max_length=10, default="low", choices=[("low", "Thấp"), ("medium", "Vừa"), ("high", "Cao")])
    actions = models.JSONField(default=list, blank=True)
    mode = models.CharField(max_length=10, default="legacy", choices=[("legacy", "Chưa xác minh"), ("rule", "Theo quy tắc"), ("ai", "AI")])
    model_name = models.CharField(max_length=80, blank=True, default="")
    source_hash = models.CharField(max_length=64, blank=True, default="")
    class Meta:
        db_table = "ai_review_analysis"
        constraints = [models.CheckConstraint(condition=models.Q(sentiment__in=["positive", "neutral", "negative"]), name="analysis_valid_sentiment")]


class ChatSession(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Đang mở"
        CLOSED = "closed", "Đã kết thúc"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="chat_sessions")
    title = models.CharField(max_length=150, default="Cuộc hội thoại")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    started_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat_sessions"
        permissions = [("read_chat_history", "Can read customer chatbot history")]
        indexes = [models.Index(fields=["user", "updated_at", "id"], name="chat_session_owner_recent")]
        constraints = [models.CheckConstraint(
            condition=models.Q(status="open", ended_at__isnull=True)
            | models.Q(status="closed", ended_at__isnull=False),
            name="chat_session_valid_state",
        )]


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Khách hàng"
        ASSISTANT = "assistant", "Trợ lý"

    class Status(models.TextChoices):
        PENDING = "pending", "Đang xử lý"
        SUCCESS = "success", "Thành công"
        FALLBACK = "fallback", "Phản hồi dự phòng"
        ERROR = "error", "Lỗi"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=Status.choices)
    model_name = models.CharField(max_length=80, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    # Each accepted request is represented by one assistant attempt. A retry refers to the original question.
    request_id = models.UUIDField(null=True, blank=True)
    reply_to = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="attempts")
    retry_of = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="retries")

    class Meta:
        db_table = "chat_messages"
        indexes = [
            models.Index(fields=["session", "role", "created_at", "id"], name="chat_message_session_recent"),
            models.Index(fields=["request_id"], name="chat_message_request"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["session", "request_id"], name="chat_message_request_unique"),
            models.UniqueConstraint(fields=["retry_of"], name="chat_message_retry_unique"),
            models.CheckConstraint(
                condition=models.Q(role="user", status="success", request_id__isnull=True,
                                   reply_to__isnull=True, retry_of__isnull=True)
                | models.Q(role="assistant", status__in=["pending", "success", "fallback", "error"],
                           request_id__isnull=False, reply_to__isnull=False),
                name="chat_message_valid_state",
            ),
        ]
