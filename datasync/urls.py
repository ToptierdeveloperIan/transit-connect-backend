from django.urls import path

from .views import BookingsSyncView, ProfileSyncView, RoutesSyncView, SyncManifestView


urlpatterns = [
    path("manifest/", SyncManifestView.as_view(), name="sync-manifest"),
    path("profile/", ProfileSyncView.as_view(), name="sync-profile"),
    path("routes/", RoutesSyncView.as_view(), name="sync-routes"),
    path("bookings/", BookingsSyncView.as_view(), name="sync-bookings"),
]
