from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('drivers', '0003_bus_destination'),
    ]

    operations = [
        migrations.AddField(
            model_name='driver',
            name='datetime',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='driver',
            name='rating_score',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='driver',
            name='total_score',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='driver',
            name='total_trips',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='driver',
            name='last_rating',
            field=models.IntegerField(default=0),
        ),
    ]
