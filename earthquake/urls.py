# earthquake/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('nearest_hospital/', views.nearest_hospital, name='nearest_hospital'),
    
    # Matches JS: fetch(`/get_nearest_history/?lat=...`)
    path('get_nearest_history/', views.get_nearest_history, name='get_nearest_history'),
    
    # Matches JS: form.action = '/report/';
    path('report/', views.report, name='report'), 
    
    # 🚨 FIX: Changed to match JS fetch(`/get_weather_proxy/?lat=...`)
    path('get_weather_proxy/', views.get_weather_proxy, name='weather_proxy'),
]

# # earthquake/urls.py
# from django.urls import path
# from . import views

# urlpatterns = [
#     path('', views.index, name='index'),
#     path('nearest_hospital/', views.nearest_hospital, name='nearest_hospital'),
#     path('get_nearest_history/', views.get_nearest_history, name='get_nearest_history'),
#     # FIX: Ensure the trailing slash is here as well
#     path('report/', views.report, name='report'), 
#     path('get_weather/', views.get_weather_proxy, name='weather_proxy'),
# ]