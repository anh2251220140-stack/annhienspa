from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ai_features", "0002_chat_history")]
    operations = [
        migrations.AddField("aireviewanalysis", "themes", models.JSONField(default=list, blank=True)),
        migrations.AddField("aireviewanalysis", "priority", models.CharField(max_length=10, default="low", choices=[("low", "Thấp"), ("medium", "Vừa"), ("high", "Cao")])),
        migrations.AddField("aireviewanalysis", "actions", models.JSONField(default=list, blank=True)),
        migrations.AddField("aireviewanalysis", "mode", models.CharField(max_length=10, default="legacy", choices=[("legacy", "Chưa xác minh"), ("rule", "Theo quy tắc"), ("ai", "AI")])),
        migrations.AddField("aireviewanalysis", "model_name", models.CharField(max_length=80, blank=True, default="")),
        migrations.AddField("aireviewanalysis", "source_hash", models.CharField(max_length=64, blank=True, default="")),
    ]
