"""
URL configuration for support project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from django.conf import settings
from django.conf.urls.static import static
from tcikets import authentication



urlpatterns = [
     path("ckeditor5/", include('django_ckeditor_5.urls')),


   #path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    #path("api/auth/logout/", logout_view, name="logout"),
    #path("api/auth/password/reset/", password_reset_request, name="password_reset_request"),
   # path("api/auth/password/reset/confirm/", password_reset_confirm, name="password_reset_confirm"),
    #path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    #path("api/auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    #path('api/auth/me/', me_view, name='user-profile'),
    #path('api/auth/register-client/', register_client, name='register_client'),
   #path('api/auth/register-technician/', register_technician, name='register_technician'),"""
   
    path('api/auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('api/auth/logout/', authentication.LogoutView.as_view(), name='logout'),
    path('api/auth/password/change/', authentication.PasswordChangeView.as_view(), name='password-change'),
    path('api/auth/password/reset/', authentication.PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('api/auth/password/reset/confirm/', authentication.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('api/auth/register/', authentication.RegisterClientView.as_view(), name='register-client'),
    #path('api/auth/register/technician/', authentication.RegisterTechnicianView.as_view(), name='register-technician'),
    path('api/auth/csrf/', authentication.CSRFTokenView.as_view(), name='csrf-token'),
    path('api/auth/refresh/', authentication.RefreshTokenView.as_view(), name='token-refresh'),
    path('api/auth/me/', authentication.MeView.as_view(), name='me'),
    path("api/auth/verify/", TokenVerifyView.as_view(), name="token_verify"),


    path('api/', include('tcikets.urls')),
        path("admin/", admin.site.urls),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
