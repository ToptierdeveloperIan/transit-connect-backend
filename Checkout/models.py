from django.db import models


#CHECKOUT STATE
class Checkout(models.Model):
    class Status(models.TextChoices):
        active = 'active', 'Active'
        inactive = 'inactive', 'Inactive'