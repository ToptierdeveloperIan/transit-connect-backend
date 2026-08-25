from django.db import models


class ResourceVersion(models.Model):
    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=100, blank=True, default="")
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("resource_type", "resource_id")
        ordering = ("resource_type", "resource_id")

    def __str__(self):
        scope = self.resource_id or "global"
        return f"{self.resource_type}:{scope} v{self.version}"
