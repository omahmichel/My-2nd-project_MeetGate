from django.urls import path

from .views import (
    MeetingDetailView,
    MeetingListCreateView,
    MeetingParticipantDetailView,
    MeetingParticipantListCreateView,
)


urlpatterns = [
    path("", MeetingListCreateView.as_view(), name="meeting-list-create"),
    path("<int:pk>/", MeetingDetailView.as_view(), name="meeting-detail"),
    path(
        "<int:meeting_id>/participants/",
        MeetingParticipantListCreateView.as_view(),
        name="meeting-participant-list-create",
    ),
    path(
        "<int:meeting_id>/participants/<int:pk>/",
        MeetingParticipantDetailView.as_view(),
        name="meeting-participant-detail",
    ),
]