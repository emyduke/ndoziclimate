from django.contrib import admin

from .models import AdminActionLog, AssessmentResult, EmailEvent, WaitlistEntry


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


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ["created_at", "full_name", "email", "role", "notified"]
    list_filter = ["notified", "role"]
    search_fields = ["full_name", "email", "role"]


@admin.register(AdminActionLog)
class AdminActionLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "target_type", "target_id", "ip_address"]
    list_filter = ["action", "target_type", "created_at"]
    search_fields = ["summary", "actor__email", "target_id"]
    readonly_fields = [
        "actor",
        "action",
        "target_type",
        "target_id",
        "summary",
        "metadata",
        "ip_address",
        "created_at",
    ]


@admin.register(EmailEvent)
class EmailEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "status", "recipient_list", "subject", "template_name", "sent_at"]
    list_filter = ["status", "template_name", "created_at"]
    search_fields = ["recipient_list", "subject", "template_name", "error_message"]
    readonly_fields = [
        "recipient_list",
        "subject",
        "template_name",
        "status",
        "error_message",
        "metadata",
        "created_at",
        "sent_at",
    ]
