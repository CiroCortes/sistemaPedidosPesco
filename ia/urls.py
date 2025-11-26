from django.urls import path
from . import views

urlpatterns = [
    path("chat/", views.ia_chat, name="ia_chat"),
]


