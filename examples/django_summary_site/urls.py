from django.urls import path
from summarydemo.views import index

urlpatterns = [path('', index, name='summary')]
