from django.urls import path

from .views import (
    CancelBookingView,
    UpdateBookingStatus,
    GetActiveBooking,
    CreateBooking,
    CheckoutView,
)

urlpatterns = [

    path("booking/<int:booking_id>/update-status", UpdateBookingStatus.as_view()),
    path("bookings/checkout/", CheckoutView.as_view(), name="bookings-checkout"),
    path("bookings/create/", CreateBooking.as_view(), name="bookings-create"),
    path("api/bookings/active/", GetActiveBooking.as_view()),
    path("api/bookings/cancel/", CancelBookingView.as_view(), name="cancel-booking"),

]
