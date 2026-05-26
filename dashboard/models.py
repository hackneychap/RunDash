from django.db import models

class RunActivity(models.Model):
    activity_id = models.CharField(max_length=100, unique=True, help_text="Garmin Activity ID")
    date = models.DateField(db_index=True)
    distance_km = models.FloatField()
    duration_minutes = models.FloatField()
    elevation_gain = models.FloatField(null=True, blank=True, help_text="Elevation gain in meters")
    tss = models.FloatField(null=True, blank=True, help_text="Training Stress Score")

    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Run Activities"

    def __str__(self):
        return f"Run on {self.date} - {self.distance_km}km"
