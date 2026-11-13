from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_remove_payment_payment_valid_status_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="invoicedetail",
            constraint=models.UniqueConstraint(fields=["invoice"], name="unique_detail_per_invoice"),
        ),
    ]
