"""
URL configuration for ridehaiingbackend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('Loginandauthentication.urls')),
    path('api/', include('drivers.urls')),
    path('api/', include('ride_matching.urls')),
    path('api/sync/', include('datasync.urls')),
    path('api/', include('RedeemAndRefferalSys.urls')),
    path('api/', include('paymentSystem.urls')),
    path('api/support/', include('Support.urls')),
    path('api/settings/', include('UserSettings.urls')),
    path('api/wallet/', include('Wallet.urls')),
]
