from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, first_name, second_name, email=None, extra_fields=None):
        if not phone_number:
            raise ValueError('Phone number must be set')
        email = self.normalize_email(email)
        phone_number = phone_number.strip()
        if extra_fields is None:
            extra_fields = {}
        user = self.model(
            email=email,
            first_name=first_name,
            second_name=second_name,
            phone_number=phone_number,


            **extra_fields
        )
        user.set_password(extra_fields.get("password"))  # optional if you plan to use password
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, first_name, second_name, email=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_staff', True)
        return self.create_user(phone_number=phone_number, first_name=first_name, second_name=second_name, email=email, extra_fields=extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True, null=False)
    first_name = models.CharField(max_length=50, null=False)
    second_name = models.CharField(max_length=50, null=False)
    profile_photo_url = models.URLField(blank=True, null=True)
    payment_methods = models.JSONField(default=dict, blank=True)
    rating = models.DecimalField(decimal_places=2, max_digits=3, default=0)
    current_location = models.CharField(blank=True, null=True, max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_driver = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'second_name', 'email']

    def __str__(self):
        return self.phone_number


class ToBeNotified_Email(models.Model):
    email = models.EmailField(unique=True)