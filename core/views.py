import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.tokens import default_token_generator
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .ai_layer import generate_narrative
from .cache import cache_get, cache_set
from .emails import (
    send_admin_assessment_report_email,
    send_admin_new_signup_email,
    send_admin_new_waitlist_email,
    send_assessment_report_email,
    send_password_changed_email,
    send_password_reset_email,
    send_waitlist_confirmation_email,
    send_welcome_email,
)
from .models import AdminActionLog, AssessmentResult, EmailEvent, WaitlistEntry
from .pipeline import (
    climate_proj,
    coastal,
    elevation,
    flood_history,
    infrastructure,
    land_cover,
    rainfall,
)
from .pipeline.scorer import (
    WEIGHTS,
    assemble_result,
    compute_coastal_score,
    compute_flood_score,
    compute_grade,
    compute_heat_score,
    compute_rainfall_score,
)
from .serializers import AssessmentInputSerializer, NIGERIAN_STATES, PROPERTY_TYPES

logger = logging.getLogger(__name__)
User = get_user_model()


def _is_portal_admin(user):
    return user.is_active and (user.is_staff or user.is_superuser)


portal_admin_required = user_passes_test(_is_portal_admin, login_url="/auth/signin/")


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _log_admin_action(request, action, summary, target_type="", target_id="", metadata=None):
    AdminActionLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        summary=summary,
        metadata=metadata or {},
        ip_address=_client_ip(request),
    )


def _has_perm(user, perm_codename):
    return user.is_superuser or user.has_perm(perm_codename)


class IndexView(TemplateView):
    template_name = "index.html"


# ── Auth ─────────────────────────────────────────────────────────────────────

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = request.POST.get("email", "").strip()
            user.first_name = request.POST.get("first_name", "").strip()
            user.last_name = request.POST.get("last_name", "").strip()
            user.save()
            login(request, user)
            send_welcome_email(user)
            send_admin_new_signup_email(user)
            messages.success(request, "Welcome to Ndozi Climate!")
            return redirect("dashboard")
        return render(request, "auth/signup.html", {"form": form})
    return render(request, "auth/signup.html", {"form": UserCreationForm()})


def signin_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get("next") or "dashboard"
            return redirect(next_url)
        return render(request, "auth/signin.html", {"form": form})
    return render(request, "auth/signin.html", {"form": AuthenticationForm()})


def signout_view(request):
    logout(request)
    return redirect("index")


def password_reset_request(request):
    if request.method == "POST":
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            users = User.objects.filter(email__iexact=email, is_active=True)
            for user in users:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_url = request.build_absolute_uri(
                    f"/auth/reset/{uid}/{token}/"
                )
                send_password_reset_email(user, reset_url)
            return redirect("password_reset_done")
    else:
        form = PasswordResetForm()
    return render(request, "auth/password_reset.html", {"form": form})


def password_reset_done(request):
    return render(request, "auth/password_reset_done.html")


def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    valid = user is not None and default_token_generator.check_token(user, token)
    if not valid:
        return render(request, "auth/password_reset_invalid.html")

    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            send_password_changed_email(user)
            return redirect("password_reset_complete")
        return render(request, "auth/password_reset_confirm.html", {"form": form, "valid": True})
    return render(
        request,
        "auth/password_reset_confirm.html",
        {"form": SetPasswordForm(user), "valid": True, "uidb64": uidb64, "token": token},
    )


def password_reset_complete(request):
    return render(request, "auth/password_reset_complete.html")


# ── Waitlist ──────────────────────────────────────────────────────────────────

def waitlist_submit(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        role = request.POST.get("role", "").strip()
        if not full_name or not email or not role:
            return JsonResponse({"error": "All fields are required."}, status=400)
        entry, created = WaitlistEntry.objects.get_or_create(
            email=email,
            defaults={"full_name": full_name, "role": role},
        )
        if created:
            send_waitlist_confirmation_email(entry)
            send_admin_new_waitlist_email(entry)
        return JsonResponse({"success": True, "created": created})
    return JsonResponse({"error": "Method not allowed."}, status=405)


# ── Assessment Dashboard ──────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    recent = AssessmentResult.objects.filter(user=request.user).order_by("-created_at")[:5]
    total = AssessmentResult.objects.filter(user=request.user).count()
    return render(
        request,
        "dashboard/home.html",
        {
            "recent": recent,
            "total": total,
            "states": NIGERIAN_STATES,
            "property_types": PROPERTY_TYPES,
        },
    )


@login_required
def assessment_history(request):
    qs = AssessmentResult.objects.filter(user=request.user).order_by("-created_at")
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "dashboard/history.html", {"page_obj": page_obj})


@login_required
def assessment_detail(request, pk):
    result = get_object_or_404(AssessmentResult, pk=pk, user=request.user)
    return render(request, "dashboard/assessment_detail.html", {"result": result})


# ── Custom Admin Portal ───────────────────────────────────────────────────────

@portal_admin_required
def portal_dashboard(request):
    ctx = {
        "total_users": User.objects.count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "total_assessments": AssessmentResult.objects.count(),
        "total_waitlist": WaitlistEntry.objects.count(),
        "total_admin_actions": AdminActionLog.objects.count(),
        "recent_assessments": AssessmentResult.objects.select_related("user").order_by("-created_at")[:8],
        "recent_users": User.objects.order_by("-date_joined")[:8],
        "recent_admin_actions": AdminActionLog.objects.select_related("actor")[:8],
        "recent_email_events": EmailEvent.objects.all()[:8],
        "grade_stats": AssessmentResult.objects.values("grade").annotate(count=Count("id")).order_by("grade"),
        "avg_score": AssessmentResult.objects.aggregate(avg=Avg("composite_score"))["avg"],
    }
    return render(request, "portal/dashboard.html", ctx)


@portal_admin_required
def portal_users(request):
    search = request.GET.get("q", "").strip()
    qs = User.objects.annotate(assessment_count=Count("assessments")).order_by("-date_joined")
    if search:
        qs = qs.filter(username__icontains=search) | qs.filter(email__icontains=search)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "portal/users.html", {"page_obj": page_obj, "search": search})


@portal_admin_required
@require_POST
def portal_user_toggle(request, pk):
    if not _has_perm(request.user, "auth.change_user"):
        messages.error(request, "You do not have permission to activate/deactivate users.")
        return redirect("portal_users")

    user = get_object_or_404(User, pk=pk)

    if user == request.user and user.is_active:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("portal_users")

    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, "Only superusers can modify another superuser.")
        return redirect("portal_users")

    previous_state = user.is_active
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    action = "activated" if user.is_active else "deactivated"
    _log_admin_action(
        request,
        action="user_status_toggle",
        summary=f"{request.user.email} {action} {user.email}",
        target_type="user",
        target_id=user.pk,
        metadata={"from": previous_state, "to": user.is_active},
    )
    messages.success(request, f"User {user.email} {action}.")
    return redirect("portal_users")


@portal_admin_required
def portal_assessments(request):
    search = request.GET.get("q", "").strip()
    grade = request.GET.get("grade", "").strip()
    qs = AssessmentResult.objects.select_related("user").order_by("-created_at")
    if search:
        qs = qs.filter(state__icontains=search) | qs.filter(user__email__icontains=search)
    if grade:
        qs = qs.filter(grade=grade.upper())
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "portal/assessments.html", {
        "page_obj": page_obj, "search": search, "grade_filter": grade,
        "grades": ["A", "B", "C", "D"],
    })


@portal_admin_required
def portal_waitlist(request):
    qs = WaitlistEntry.objects.order_by("-created_at")
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "portal/waitlist.html", {"page_obj": page_obj})


@portal_admin_required
@require_POST
def portal_make_staff(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can grant or revoke staff access.")
        return redirect("portal_users")

    user = get_object_or_404(User, pk=pk)

    if user == request.user and user.is_staff:
        messages.error(request, "You cannot remove your own staff access.")
        return redirect("portal_users")

    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, "Only superusers can modify another superuser.")
        return redirect("portal_users")

    previous_state = user.is_staff
    user.is_staff = not user.is_staff
    user.save(update_fields=["is_staff"])
    action = "granted" if user.is_staff else "revoked"
    _log_admin_action(
        request,
        action="staff_access_toggle",
        summary=f"{request.user.email} {action} staff access for {user.email}",
        target_type="user",
        target_id=user.pk,
        metadata={"from": previous_state, "to": user.is_staff},
    )
    messages.success(request, f"Staff access {action} for {user.email}.")
    return redirect("portal_users")


@portal_admin_required
@require_POST
def portal_delete_assessment(request, pk):
    if not _has_perm(request.user, "core.delete_assessmentresult"):
        messages.error(request, "You do not have permission to delete assessments.")
        return redirect("portal_assessments")

    assessment = get_object_or_404(AssessmentResult, pk=pk)
    summary = f"{request.user.email} deleted assessment #{assessment.pk}"
    metadata = {
        "user_email": assessment.user.email if assessment.user else None,
        "state": assessment.state,
        "grade": assessment.grade,
        "composite_score": assessment.composite_score,
    }
    assessment.delete()
    _log_admin_action(
        request,
        action="assessment_delete",
        summary=summary,
        target_type="assessment",
        target_id=pk,
        metadata=metadata,
    )
    messages.success(request, f"Assessment #{pk} deleted.")
    return redirect("portal_assessments")


@portal_admin_required
@require_POST
def portal_waitlist_toggle_notified(request, pk):
    if not _has_perm(request.user, "core.change_waitlistentry"):
        messages.error(request, "You do not have permission to update waitlist entries.")
        return redirect("portal_waitlist")

    entry = get_object_or_404(WaitlistEntry, pk=pk)
    previous_state = entry.notified
    entry.notified = not entry.notified
    entry.save(update_fields=["notified"])

    action = "marked as notified" if entry.notified else "marked as pending"
    _log_admin_action(
        request,
        action="waitlist_notified_toggle",
        summary=f"{request.user.email} {action} for {entry.email}",
        target_type="waitlist",
        target_id=entry.pk,
        metadata={"from": previous_state, "to": entry.notified},
    )
    messages.success(request, f"Waitlist entry for {entry.email} {action}.")
    return redirect("portal_waitlist")


@portal_admin_required
def portal_activity_logs(request):
    if not _has_perm(request.user, "core.view_adminactionlog"):
        messages.error(request, "You do not have permission to view activity logs.")
        return redirect("portal_dashboard")

    action_filter = request.GET.get("action", "").strip()
    actor_filter = request.GET.get("actor", "").strip()

    qs = AdminActionLog.objects.select_related("actor").order_by("-created_at")
    if action_filter:
        qs = qs.filter(action__icontains=action_filter)
    if actor_filter:
        qs = qs.filter(actor__email__icontains=actor_filter)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "portal/logs.html",
        {
            "page_obj": page_obj,
            "action_filter": action_filter,
            "actor_filter": actor_filter,
        },
    )


@portal_admin_required
def portal_email_events(request):
    if not _has_perm(request.user, "core.view_emailevent"):
        messages.error(request, "You do not have permission to view email delivery logs.")
        return redirect("portal_dashboard")

    status_filter = request.GET.get("status", "").strip().lower()
    query = request.GET.get("q", "").strip()

    qs = EmailEvent.objects.order_by("-created_at")
    if status_filter in {EmailEvent.STATUS_QUEUED, EmailEvent.STATUS_SENT, EmailEvent.STATUS_FAILED}:
        qs = qs.filter(status=status_filter)
    if query:
        qs = qs.filter(recipient_list__icontains=query) | qs.filter(subject__icontains=query)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "portal/email_events.html",
        {
            "page_obj": page_obj,
            "status_filter": status_filter,
            "query": query,
        },
    )


# ── Live Assessment API ───────────────────────────────────────────────────────

class AssessmentView(APIView):
    @method_decorator(login_required(login_url="/auth/signin/"))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        serializer = AssessmentInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        lat = data["lat"]
        lng = data["lng"]
        state = data["state"]
        property_type = data["property_type"]
        notes = data.get("notes", "")

        cache_key = hashlib.md5(
            f"{round(lat,3)},{round(lng,3)},{state},{property_type}".encode()
        ).hexdigest()

        cached = cache_get(cache_key)
        if cached:
            logger.info("Cache hit: %s", cache_key)
            return Response(cached)

        try:
            with ThreadPoolExecutor(max_workers=7) as pool:
                futures = {
                    "elevation": pool.submit(elevation.get_elevation_data, lat, lng),
                    "rainfall": pool.submit(rainfall.get_rainfall_data, lat, lng),
                    "flood_history": pool.submit(flood_history.get_flood_history, lat, lng),
                    "land_cover": pool.submit(land_cover.get_land_cover, lat, lng),
                    "infrastructure": pool.submit(
                        infrastructure.get_infrastructure_data, lat, lng
                    ),
                    "coastal": pool.submit(coastal.get_coastal_risk, lat, lng),
                    "projections": pool.submit(
                        climate_proj.get_climate_projections, lat, lng, state
                    ),
                }
                pipeline_results = {name: f.result() for name, f in futures.items()}

            elev_data = pipeline_results["elevation"]
            rain_data = pipeline_results["rainfall"]
            flood_data = pipeline_results["flood_history"]
            cover_data = pipeline_results["land_cover"]
            infra_data = pipeline_results["infrastructure"]
            coast_data = pipeline_results["coastal"]
            proj_data = pipeline_results["projections"]

            flood_score = compute_flood_score(elev_data, flood_data, cover_data, infra_data)
            rain_score = compute_rainfall_score(rain_data)
            heat_score = compute_heat_score(lat, state, proj_data)
            coast_score = compute_coastal_score(coast_data, elev_data)

            composite = int(
                flood_score * WEIGHTS["flood"]
                + rain_score * WEIGHTS["rainfall"]
                + heat_score * WEIGHTS["heat"]
                + coast_score * WEIGHTS["coastal"]
            )
            grade, grade_label = compute_grade(composite)

            data_notes = " | ".join(
                [
                    pipeline_results[k].get("data_notes", "")
                    for k in [
                        "elevation",
                        "rainfall",
                        "flood_history",
                        "land_cover",
                        "infrastructure",
                        "coastal",
                        "projections",
                    ]
                    if pipeline_results[k].get("data_notes")
                ]
            )

            pipeline_context = {
                "elevation_m": elev_data.get("elevation_m"),
                "slope_deg": elev_data.get("slope_deg"),
                "distance_to_coast_km": coast_data.get("distance_to_coast_km"),
                "cover_class": cover_data.get("cover_class"),
                "flood_recurrence": flood_data.get("flood_recurrence"),
                "flood_occurrence_pct": flood_data.get("occurrence_pct"),
                "annual_mean_mm": rain_data.get("annual_mean_mm"),
                "max_3day_event_mm": rain_data.get("max_3day_event_mm"),
                "projected_rainfall_change_pct": proj_data.get(
                    "projected_rainfall_change_pct"
                ),
                "projected_temp_increase_c": proj_data.get("projected_temp_increase_c"),
                "heat_stress_days_increase": proj_data.get("heat_stress_days_increase"),
                "drainage_density": infra_data.get("drainage_density"),
                "data_notes": data_notes,
            }

            ai_narrative = generate_narrative(
                lat,
                lng,
                state,
                property_type,
                flood_score,
                rain_score,
                heat_score,
                coast_score,
                composite,
                grade,
                pipeline_context,
            )

            result = assemble_result(
                {
                    **pipeline_results,
                    "lat": lat,
                    "lng": lng,
                    "state": state,
                    "property_type": property_type,
                    "data_notes": data_notes,
                },
                ai_narrative,
            )

            AssessmentResult.objects.create(
                user=request.user if request.user.is_authenticated else None,
                latitude=lat,
                longitude=lng,
                state=state,
                property_type=property_type,
                notes=notes,
                composite_score=composite,
                flood_score=flood_score,
                rainfall_score=rain_score,
                heat_score=heat_score,
                coastal_score=coast_score,
                grade=grade,
                grade_label=grade_label,
                exposure_summary=ai_narrative["summary"],
                cost_low=result["costLow"],
                cost_high=result["costHigh"],
                recommendations=ai_narrative["recommendations"],
                data_sources_used=result["dataSources"],
                data_notes=data_notes,
            )

            cache_set(cache_key, result)
            if request.user.is_authenticated:
                send_assessment_report_email(request.user, result)
                send_admin_assessment_report_email(request.user, result)
            return Response(result)
        except Exception as exc:
            logger.exception("Assessment pipeline error: %s", exc)
            return Response(
                {"error": "Assessment failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
