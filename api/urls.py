from django.urls import path
from . import views

urlpatterns = [
    path('credit-bureau-risk-assessment', views.Process.as_view(), name='credit-bureau-risk-assessment'),
]