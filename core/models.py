from django.db import models


class AssessmentResult(models.Model):
    """Stores every completed assessment for auditing and caching."""

    created_at = models.DateTimeField(auto_now_add=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    state = models.CharField(max_length=50)
    property_type = models.CharField(max_length=80)
    notes = models.TextField(blank=True)

    composite_score = models.IntegerField()
    flood_score = models.IntegerField()
    rainfall_score = models.IntegerField()
    heat_score = models.IntegerField()
    coastal_score = models.IntegerField()

    grade = models.CharField(max_length=1)
    grade_label = models.CharField(max_length=60)

    exposure_summary = models.TextField()
    cost_low = models.CharField(max_length=30)
    cost_high = models.CharField(max_length=30)
    recommendations = models.TextField()

    data_sources_used = models.JSONField(default=list)
    data_retrieved_at = models.DateTimeField(auto_now_add=True)
    data_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["state"]),
        ]

    def __str__(self) -> str:
        return f"Grade {self.grade} | {self.state} | {self.latitude},{self.longitude}"
