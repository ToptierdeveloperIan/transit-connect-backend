import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paymentSystem', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('payment_id', models.CharField(db_index=True, max_length=120)),
                ('event_type', models.CharField(choices=[('PAYMENT_CREATED', 'Payment created'), ('PAYMENT_REQUESTED', 'Payment requested'), ('PROVIDER_ACCEPTED', 'Provider accepted'), ('PROVIDER_CONFIRMED_SUCCESS', 'Provider confirmed success'), ('PROVIDER_CONFIRMED_FAILURE', 'Provider confirmed failure'), ('PAYMENT_TIMEOUT_REACHED', 'Payment timeout reached'), ('RECONCILIATION_STARTED', 'Reconciliation started'), ('RECONCILIATION_RESOLVED_SUCCESS', 'Reconciliation resolved success'), ('RECONCILIATION_RESOLVED_FAILURE', 'Reconciliation resolved failure')], max_length=48)),
                ('occurred_at', models.DateTimeField()),
                ('source', models.CharField(max_length=80)),
                ('correlation_id', models.CharField(blank=True, max_length=120, null=True)),
                ('provider_reference', models.CharField(blank=True, max_length=120, null=True)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('applied_at', models.DateTimeField(blank=True, null=True)),
                ('ignored_reason', models.CharField(blank=True, default='', max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['occurred_at', 'id'],
            },
        ),
        migrations.CreateModel(
            name='PaymentProjection',
            fields=[
                ('payment_id', models.CharField(max_length=120, primary_key=True, serialize=False)),
                ('current_state', models.CharField(choices=[('NONE', 'No state'), ('CREATED', 'Created'), ('REQUESTED', 'Requested'), ('PROVIDER_PENDING', 'Provider pending'), ('SUCCEEDED', 'Succeeded'), ('FAILED', 'Failed'), ('TIMED_OUT', 'Timed out'), ('RECONCILING', 'Reconciling')], default='NONE', max_length=32)),
                ('last_event_id', models.UUIDField(blank=True, null=True)),
                ('last_event_type', models.CharField(blank=True, default='', max_length=48)),
                ('provider_reference', models.CharField(blank=True, max_length=120, null=True)),
                ('version', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='PaymentOutbox',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('outbox_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('PUBLISHED', 'Published'), ('FAILED', 'Failed')], db_index=True, default='PENDING', max_length=16)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outbox_records', to='paymentSystem.paymentevent')),
            ],
            options={
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='paymentevent',
            index=models.Index(fields=['payment_id', 'occurred_at'], name='paymentSyst_payment_d360c1_idx'),
        ),
        migrations.AddIndex(
            model_name='paymentevent',
            index=models.Index(fields=['event_type'], name='paymentSyst_event_t_e59f68_idx'),
        ),
    ]
