from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ai_features", "0003_review_analysis_details")]

    operations = [
        migrations.CreateModel(
            name="RagDocumentIndex",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namespace", models.CharField(max_length=64)),
                ("document_key", models.CharField(max_length=64)),
                ("digest", models.CharField(max_length=64)),
                ("chunks", models.JSONField()),
            ],
            options={
                "db_table": "rag_document_index",
                "constraints": [
                    models.UniqueConstraint(
                        fields=["namespace", "document_key"], name="rag_namespace_document_unique"
                    ),
                ],
            },
        ),
    ]
