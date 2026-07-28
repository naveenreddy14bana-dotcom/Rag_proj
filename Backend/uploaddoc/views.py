from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import os
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Document
from .rag import answer_question
from .serializers import DocumentSerializer


@method_decorator(csrf_exempt, name="dispatch")
class DocumentUploadAPIView(APIView):

    def post(self, request):

        serializer = DocumentSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Document uploaded successfully",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DocumentListAPIView(APIView):

    def get(self, request):

        documents = Document.objects.all().order_by("-uploaded_at")

        serializer = DocumentSerializer(documents, many=True)

        return Response(
            {
                "count": documents.count(),
                "data": serializer.data
            }
        )



class DocumentDeleteAPIView(APIView):

    def delete(self, request, id):
        try:
            document = Document.objects.get(id=id)

            # Delete file from media folder
            if document.file and os.path.isfile(document.file.path):
                os.remove(document.file.path)

            # Delete database record
            document.delete()

            return Response(
                {
                    "success": True,
                    "message": "Document deleted successfully."
                },
                status=status.HTTP_200_OK
            )

        except Document.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Document not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )


@method_decorator(csrf_exempt, name="dispatch")
class ChatAPIView(APIView):

    def post(self, request):
        question = str(request.data.get("question", "")).strip()

        if not question:
            return Response(
                {"message": "Question is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = answer_question(question)
        return Response(result, status=status.HTTP_200_OK)
