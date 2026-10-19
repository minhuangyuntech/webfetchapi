from django.urls import path
from searchdemo.views import index

urlpatterns = [path('', index, name='search')]
