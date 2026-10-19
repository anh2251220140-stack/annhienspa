from django.core.exceptions import ValidationError
from django.db import models
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
    class Meta:
        db_table = "ai_review_analysis"
        constraints = [models.CheckConstraint(condition=models.Q(sentiment__in=["positive", "neutral", "negative"]), name="analysis_valid_sentiment")]
