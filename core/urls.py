from django.urls import path

from . import views

urlpatterns = [
    # ── Homepage ────────────────────────────────────────────────────────────
    path("", views.IndexView.as_view(), name="index"),

    # ── Auth ─────────────────────────────────────────────────────────────────
    path("auth/signup/", views.signup_view, name="signup"),
    path("auth/signin/", views.signin_view, name="signin"),
    path("auth/signout/", views.signout_view, name="signout"),
    path("auth/password-reset/", views.password_reset_request, name="password_reset"),
    path("auth/password-reset/done/", views.password_reset_done, name="password_reset_done"),
    path("auth/reset/<uidb64>/<token>/", views.password_reset_confirm, name="password_reset_confirm"),
    path("auth/password-reset/complete/", views.password_reset_complete, name="password_reset_complete"),

    # ── Waitlist ─────────────────────────────────────────────────────────────
    path("waitlist/", views.waitlist_submit, name="waitlist_submit"),

    # ── User Dashboard ────────────────────────────────────────────────────────
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("dashboard/history/", views.assessment_history, name="assessment_history"),
    path("dashboard/assessment/<int:pk>/", views.assessment_detail, name="assessment_detail"),

    # ── Admin Portal ─────────────────────────────────────────────────────────
    path("portal/", views.portal_dashboard, name="portal_dashboard"),
    path("portal/users/", views.portal_users, name="portal_users"),
    path("portal/users/<int:pk>/toggle/", views.portal_user_toggle, name="portal_user_toggle"),
    path("portal/users/<int:pk>/staff/", views.portal_make_staff, name="portal_make_staff"),
    path("portal/assessments/", views.portal_assessments, name="portal_assessments"),
    path("portal/assessments/<int:pk>/delete/", views.portal_delete_assessment, name="portal_delete_assessment"),
    path("portal/waitlist/", views.portal_waitlist, name="portal_waitlist"),
    path("portal/waitlist/<int:pk>/notified/", views.portal_waitlist_toggle_notified, name="portal_waitlist_toggle_notified"),
    path("portal/logs/", views.portal_activity_logs, name="portal_activity_logs"),
    path("portal/email-events/", views.portal_email_events, name="portal_email_events"),

    # ── Assessment API ────────────────────────────────────────────────────────
    path("api/assess/", views.AssessmentView.as_view(), name="assess"),
]
