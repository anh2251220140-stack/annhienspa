from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('promotions', '0003_promotion_per_customer_limit_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='promotion',
            name='note_is_informational',
            field=models.BooleanField(default=False),
        ),
    ]
