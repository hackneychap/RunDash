from django.db import models


class ARace(models.Model):
    """A Race — the main goal event for a training block."""
    name = models.CharField(max_length=200, help_text="e.g. 'London Marathon 2026'")
    date = models.DateField()
    goal_time = models.CharField(max_length=20, blank=True, help_text="Optional target time")
    feeling = models.TextField(blank=True, help_text="Post-race reflection")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return self.name


class TrainingBlock(models.Model):
    """A Training Block — a period of structured training leading up to an A Race."""
    a_race = models.OneToOneField(ARace, on_delete=models.CASCADE, related_name='training_block')
    name = models.CharField(max_length=200, help_text="Auto-generated or custom name")
    start_date = models.DateField()
    end_date = models.DateField(help_text="Typically the A race date")

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        return self.name


class TrainingBlockSection(models.Model):
    """A section within a training block (Base, Race Specific, Taper, etc.)."""
    training_block = models.ForeignKey(TrainingBlock, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=100, help_text="e.g. 'Base', 'Race Specific', 'Taper'")
    order = models.IntegerField(help_text="Sorting order: 0=Base, 1=Race Specific, 2=Taper")
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.training_block.name} — {self.name}"


class BRace(models.Model):
    """B Race — a secondary event within a training block."""
    name = models.CharField(max_length=200, help_text="e.g. 'Hackney Half'")
    date = models.DateField()
    training_block = models.ForeignKey(TrainingBlock, on_delete=models.CASCADE, related_name='b_races')
    distance_km = models.FloatField()
    feeling = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return self.name


class RunActivity(models.Model):
    activity_id = models.CharField(max_length=100, unique=True, help_text="Garmin Activity ID")
    date = models.DateField(db_index=True)
    distance_km = models.FloatField()
    duration_minutes = models.FloatField()
    elevation_gain = models.FloatField(null=True, blank=True, help_text="Elevation gain in meters")
    tss = models.FloatField(null=True, blank=True, help_text="Training Stress Score")
    training_block = models.ForeignKey(
        TrainingBlock,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='activities',
    )

    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Run Activities"

    def __str__(self):
        return f"Run on {self.date} - {self.distance_km}km"
