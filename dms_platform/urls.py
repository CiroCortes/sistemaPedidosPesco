from django.http import JsonResponse
from django.urls import path


def health(request):
    return JsonResponse({"status": "ok", "app": "dms-platform"})


urlpatterns = [
    path("", health),
    path("health/", health),
]
