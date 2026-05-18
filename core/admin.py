from django.contrib import admin

from .models import AssessmentResult


@admin.register(AssessmentResult)
class AssessmentResultAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "state",
        "grade",
        "composite_score",
        "latitude",
        "longitude",
        "property_type",
    ]
    list_filter = ["grade", "state"]
    search_fields = ["state", "property_type"]
    readonly_fields = ["created_at", "data_retrieved_at"]
