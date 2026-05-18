from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from core.emails import _send
from core.models import AdminActionLog, AssessmentResult, EmailEvent, WaitlistEntry


class PortalPermissionTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.staff = self.user_model.objects.create_user(
            username="staff1", email="staff1@example.com", password="pass1234", is_staff=True
        )
        self.regular = self.user_model.objects.create_user(
            username="regular1", email="regular1@example.com", password="pass1234", is_active=True
        )

    def test_staff_without_change_user_permission_cannot_toggle_user(self):
        self.client.login(username="staff1", password="pass1234")

        self.client.post(reverse("portal_user_toggle", kwargs={"pk": self.regular.pk}), follow=True)

        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_active)
        self.assertFalse(
            AdminActionLog.objects.filter(action="user_status_toggle", target_id=str(self.regular.pk)).exists()
        )

    def test_staff_with_change_user_permission_can_toggle_user(self):
        perm = Permission.objects.get(codename="change_user")
        self.staff.user_permissions.add(perm)
        self.client.login(username="staff1", password="pass1234")

        self.client.post(reverse("portal_user_toggle", kwargs={"pk": self.regular.pk}), follow=True)

        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_active)
        self.assertTrue(
            AdminActionLog.objects.filter(action="user_status_toggle", target_id=str(self.regular.pk)).exists()
        )


class PortalAuditAndEmailEventTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_superuser(
            username="admin1", email="admin1@example.com", password="pass1234"
        )
        self.actor = self.user_model.objects.create_user(
            username="actor1", email="actor1@example.com", password="pass1234"
        )

    def test_waitlist_toggle_creates_admin_action_log(self):
        entry = WaitlistEntry.objects.create(full_name="A User", email="auser@example.com", role="Investor")
        self.client.login(username="admin1", password="pass1234")

        self.client.post(reverse("portal_waitlist_toggle_notified", kwargs={"pk": entry.pk}), follow=True)

        entry.refresh_from_db()
        self.assertTrue(entry.notified)
        self.assertTrue(
            AdminActionLog.objects.filter(
                action="waitlist_notified_toggle",
                target_type="waitlist",
                target_id=str(entry.pk),
            ).exists()
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_creates_email_event(self):
        _send(
            subject="Test Subject",
            template="emails/welcome.html",
            context={"user": self.actor},
            to=["dest@example.com"],
        )

        event = EmailEvent.objects.first()
        self.assertIsNotNone(event)
        self.assertEqual(event.status, EmailEvent.STATUS_SENT)
        self.assertEqual(event.template_name, "emails/welcome.html")
        self.assertIn("dest@example.com", event.recipient_list)
