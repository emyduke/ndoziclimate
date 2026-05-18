from django.urls import path

from .views import AssessmentView, IndexView

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("api/assess/", AssessmentView.as_view(), name="assess"),
]
