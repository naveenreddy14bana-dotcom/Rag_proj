from django.urls import path
from .views import ChatAPIView, DocumentUploadAPIView, DocumentListAPIView, DocumentDeleteAPIView

urlpatterns = [
    path("upload/", DocumentUploadAPIView.as_view(), name="upload"),
    path("documents/", DocumentListAPIView.as_view(), name="documents"),
    path("documents/<int:id>/", DocumentDeleteAPIView.as_view(), name="document-delete"),
    path("chat/", ChatAPIView.as_view(), name="chat"),
]
