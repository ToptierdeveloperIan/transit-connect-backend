from django.urls import path

from .views import (
    AcceptTermsView,
    CurrentLegalDocumentView,
    CurrentTermsView,
    SupportHealthView,
    TermsStatusView,
)

urlpatterns = [
    path("health/", SupportHealthView.as_view(), name="support-health"),
    # Terms of Service (friendly)
    path("terms/", CurrentTermsView.as_view(), name="support-terms-current"),
    path("terms/status/", TermsStatusView.as_view(), name="support-terms-status"),
    path("terms/accept/", AcceptTermsView.as_view(), name="support-terms-accept"),
    # Extensible legal surface (TERMS / PRIVACY / …)
    path("legal/current/", CurrentLegalDocumentView.as_view(), name="support-legal-current"),
]
