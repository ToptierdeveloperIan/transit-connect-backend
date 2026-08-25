import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WalletAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("currency", models.CharField(default="KES", max_length=3)),
                ("available_balance", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("held_balance", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wallet_account",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="WalletIntent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("DEPOSIT", "Deposit into wallet"),
                            ("SPEND", "Spend from wallet (e.g. pay fare)"),
                            ("REFUND_TO_WALLET", "Credit wallet after refund path"),
                            ("ADJUSTMENT", "Ops adjustment (audited)"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("PENDING_PROVIDER", "Pending provider"),
                            ("PROVIDER_ACCEPTED", "Provider accepted"),
                            ("SUCCEEDED", "Succeeded"),
                            ("FAILED", "Failed"),
                            ("EXPIRED", "Expired"),
                            ("CANCELLED", "Cancelled"),
                            ("REVERSED", "Reversed"),
                        ],
                        db_index=True,
                        default="CREATED",
                        max_length=32,
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[
                            ("MPESA", "M-Pesa"),
                            ("AIRTEL", "Airtel Money"),
                            ("INTERNAL", "Internal (ledger-only / adjustment)"),
                            ("WALLET", "Wallet balance (spend from available)"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("currency", models.CharField(default="KES", max_length=3)),
                ("idempotency_key", models.CharField(db_index=True, max_length=64, unique=True)),
                ("provider_reference", models.CharField(blank=True, db_index=True, max_length=120, null=True)),
                ("provider_payload", models.JSONField(blank=True, default=dict)),
                ("fare_quote_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("booking_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("description", models.CharField(blank=True, default="", max_length=255)),
                ("failure_reason", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("succeeded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "wallet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="intents",
                        to="Wallet.walletaccount",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "entry_type",
                    models.CharField(
                        choices=[
                            ("CREDIT_DEPOSIT", "Deposit credit"),
                            ("DEBIT_SPEND", "Spend debit"),
                            ("CREDIT_REVERSAL", "Reversal credit (undo debit)"),
                            ("DEBIT_REVERSAL", "Reversal debit (undo credit)"),
                            ("CREDIT_ADJUSTMENT", "Adjustment credit"),
                            ("DEBIT_ADJUSTMENT", "Adjustment debit"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("currency", models.CharField(default="KES", max_length=3)),
                (
                    "channel",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("MPESA", "M-Pesa"),
                            ("AIRTEL", "Airtel Money"),
                            ("INTERNAL", "Internal (ledger-only / adjustment)"),
                            ("WALLET", "Wallet balance (spend from available)"),
                        ],
                        default="",
                        max_length=16,
                    ),
                ),
                ("provider_reference", models.CharField(blank=True, default="", max_length=120)),
                ("description", models.CharField(blank=True, default="", max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("balance_after", models.DecimalField(decimal_places=2, max_digits=14)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "intent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ledger_entries",
                        to="Wallet.walletintent",
                    ),
                ),
                (
                    "related_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="compensations",
                        to="Wallet.ledgerentry",
                    ),
                ),
                (
                    "wallet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ledger_entries",
                        to="Wallet.walletaccount",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="walletaccount",
            index=models.Index(fields=["user"], name="Wallet_wall_user_id_0f2a8e_idx"),
        ),
        migrations.AddIndex(
            model_name="walletintent",
            index=models.Index(fields=["wallet", "status", "kind"], name="Wallet_wall_wallet__b8c1d2_idx"),
        ),
        migrations.AddIndex(
            model_name="walletintent",
            index=models.Index(fields=["channel", "provider_reference"], name="Wallet_wall_channel_a1b2c3_idx"),
        ),
        migrations.AddConstraint(
            model_name="walletintent",
            constraint=models.UniqueConstraint(
                condition=models.Q(("provider_reference__isnull", False))
                & ~models.Q(("provider_reference", "")),
                fields=("channel", "provider_reference"),
                name="uniq_wallet_intent_channel_provider_ref",
            ),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["wallet", "created_at"], name="Wallet_ledg_wallet__d4e5f6_idx"),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["intent"], name="Wallet_ledg_intent__g7h8i9_idx"),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["provider_reference"], name="Wallet_ledg_provide_j0k1l2_idx"),
        ),
        migrations.AddConstraint(
            model_name="ledgerentry",
            constraint=models.CheckConstraint(
                check=models.Q(("amount__gt", 0)),
                name="ledger_amount_positive",
            ),
        ),
    ]
