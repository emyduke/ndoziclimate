from django.conf import settings
from django.db import models


class WaitlistEntry(models.Model):
    """Stores waitlist sign-ups from the homepage."""

    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Waitlist Entry"
        verbose_name_plural = "Waitlist Entries"

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"


class AssessmentResult(models.Model):
    """Stores every completed assessment for auditing and caching."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessments",
    )
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


class AdminActionLog(models.Model):
    """Tracks sensitive actions taken in the custom admin portal."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_actions",
    )
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=50, blank=True)
    summary = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} by {self.actor_id} at {self.created_at:%Y-%m-%d %H:%M:%S}"


class EmailEvent(models.Model):
    """Tracks email delivery attempts for operational visibility."""

    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    recipient_list = models.TextField()
    subject = models.CharField(max_length=255)
    template_name = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.subject} -> {self.recipient_list} ({self.status})"
