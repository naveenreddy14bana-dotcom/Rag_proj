from django.urls import path
from .views import DocumentUploadAPIView, DocumentListAPIView,DocumentDeleteAPIView

urlpatterns = [
    path("upload/", DocumentUploadAPIView.as_view(), name="upload"),
    path("documents/", DocumentListAPIView.as_view(), name="documents"),
     path("documents/<int:id>/", DocumentDeleteAPIView.as_view(),name="documents/<int:id"),
]