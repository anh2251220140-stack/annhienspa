from django.db import models

class ValidatedModel(models.Model):
    """Validate ordinary ORM saves. bulk/update bypass this; use services for transactions."""
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

class TimestampedModel(ValidatedModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True
