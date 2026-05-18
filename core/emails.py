"""Email sending helpers for Ndozi Climate."""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _send(subject: str, template: str, context: dict, to: list[str]) -> None:
    """Render an HTML email template and send it, falling back to plain text."""
    from .models import EmailEvent

    context.setdefault("site_name", settings.SITE_NAME)
    context.setdefault("site_url", settings.SITE_URL)

    event = EmailEvent.objects.create(
        recipient_list=", ".join(to),
        subject=subject,
        template_name=template,
        status=EmailEvent.STATUS_QUEUED,
    )

    html_body = render_to_string(template, context)
    text_body = strip_tags(html_body)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    msg.attach_alternative(html_body, "text/html")
    try:
        msg.send(fail_silently=False)
        event.status = EmailEvent.STATUS_SENT
        event.sent_at = timezone.now()
        event.save(update_fields=["status", "sent_at"])
    except Exception as exc:  # noqa: BLE001
        logger.error("Email send failed to %s: %s", to, exc)
        event.status = EmailEvent.STATUS_FAILED
        event.error_message = str(exc)
        event.save(update_fields=["status", "error_message"])


def _async(subject, template, context, to):
    t = threading.Thread(target=_send, args=(subject, template, context, to), daemon=True)
    t.start()


# ── Public helpers ───────────────────────────────────────────────────────────

def send_welcome_email(user) -> None:
    _async(
        subject=f"Welcome to {settings.SITE_NAME} — Know Before You Buy",
        template="emails/welcome.html",
        context={"user": user},
        to=[user.email],
    )


def send_password_reset_email(user, reset_url: str) -> None:
    _async(
        subject=f"{settings.SITE_NAME} — Reset your password",
        template="emails/password_reset.html",
        context={"user": user, "reset_url": reset_url},
        to=[user.email],
    )


def send_password_changed_email(user) -> None:
    _async(
        subject=f"{settings.SITE_NAME} — Your password was changed",
        template="emails/password_changed.html",
        context={"user": user},
        to=[user.email],
    )


def send_assessment_report_email(user, result: dict) -> None:
    _async(
        subject=f"{settings.SITE_NAME} — Your Climate Risk Report is Ready",
        template="emails/assessment_report.html",
        context={"user": user, "result": result},
        to=[user.email],
    )


def send_admin_assessment_report_email(user, result: dict) -> None:
    admin_email = getattr(settings, "ADMIN_EMAIL", None)
    if not admin_email:
        return
    _async(
        subject=f"[{settings.SITE_NAME}] Assessment completed: {result.get('state', 'Unknown')} ({result.get('grade', '-')})",
        template="emails/admin_assessment_report.html",
        context={"user": user, "result": result},
        to=[admin_email],
    )


def send_waitlist_confirmation_email(entry) -> None:
    _async(
        subject=f"You're on the {settings.SITE_NAME} waitlist! 🎉",
        template="emails/waitlist_confirm.html",
        context={"entry": entry},
        to=[entry.email],
    )


def send_admin_new_signup_email(user) -> None:
    admin_email = getattr(settings, "ADMIN_EMAIL", None)
    if not admin_email:
        return
    _async(
        subject=f"[{settings.SITE_NAME}] New user signed up: {user.email}",
        template="emails/admin_new_signup.html",
        context={"user": user},
        to=[admin_email],
    )


def send_admin_new_waitlist_email(entry) -> None:
    admin_email = getattr(settings, "ADMIN_EMAIL", None)
    if not admin_email:
        return
    _async(
        subject=f"[{settings.SITE_NAME}] New waitlist entry: {entry.email}",
        template="emails/admin_new_waitlist.html",
        context={"entry": entry},
        to=[admin_email],
    )
