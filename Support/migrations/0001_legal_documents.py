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
            name="LegalDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_type", models.CharField(choices=[("TERMS", "Terms of Service"), ("PRIVACY", "Privacy Policy")], db_index=True, max_length=32)),
                ("version", models.CharField(db_index=True, max_length=32)),
                ("locale", models.CharField(choices=[("en", "English"), ("sw", "Kiswahili")], db_index=True, default="en", max_length=8)),
                ("title", models.CharField(max_length=255)),
                ("body", models.TextField()),
                ("body_format", models.CharField(choices=[("plain", "Plain text"), ("markdown", "Markdown"), ("html", "HTML")], default="plain", max_length=16)),
                ("effective_at", models.DateTimeField()),
                ("is_published", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-effective_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="LegalAcceptance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_type", models.CharField(choices=[("TERMS", "Terms of Service"), ("PRIVACY", "Privacy Policy")], db_index=True, max_length=32)),
                ("version", models.CharField(db_index=True, max_length=32)),
                ("locale", models.CharField(choices=[("en", "English"), ("sw", "Kiswahili")], help_text="Locale the user was viewing when they accepted.", max_length=8)),
                ("accepted_at", models.DateTimeField(auto_now_add=True)),
                ("platform", models.CharField(blank=True, default="", max_length=32)),
                ("app_version", models.CharField(blank=True, default="", max_length=32)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="legal_acceptances", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-accepted_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="legaldocument",
            constraint=models.UniqueConstraint(fields=("document_type", "version", "locale"), name="uniq_legal_doc_type_version_locale"),
        ),
        migrations.AddIndex(
            model_name="legaldocument",
            index=models.Index(fields=["document_type", "is_published", "locale"], name="Support_leg_documen_7a2b1c_idx"),
        ),
        migrations.AddConstraint(
            model_name="legalacceptance",
            constraint=models.UniqueConstraint(fields=("user", "document_type", "version"), name="uniq_legal_accept_user_type_version"),
        ),
    ]
