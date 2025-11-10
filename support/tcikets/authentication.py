from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status, generics, permissions
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer, UserUpdateSerializer, ClientCreateSerializer,TechnicianCreateSerializer
from django.contrib.auth import get_user_model
from .models import Client, Technician
import uuid
from rest_framework.permissions import AllowAny

User = get_user_model()
token_generator = PasswordResetTokenGenerator()

# Serializer pour la connexion
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

# Vue générique pour la connexion
class LoginView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                
                user_type = getattr(user, 'userType', 'unknown')

                return Response({
                    'message': 'Login successful',
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'email': user.email,
                        'userType': user_type
                    },
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh)
                    }
                })
            else:
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Vue générique pour la déconnexion
class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        logout(request)
        return Response({'message': 'Logout successful'})

# Vue générique pour changer le mot de passe
class PasswordChangeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.Serializer
    
    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not user.check_password(old_password):
            return Response({"error": "Ancien mot de passe incorrect"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Mot de passe modifié ✅"}, status=status.HTTP_200_OK)

# Vue générique pour demander une réinitialisation de mot de passe
class PasswordResetRequestView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = serializers.Serializer
    
    def post(self, request):
        email = request.data.get("email")
        try:
            user = User.objects.get(email=email)
            # Utilisation de l'UUID au lieu de l'ID numérique
            uid = urlsafe_base64_encode(force_bytes(str(user.pk)))
            token = token_generator.make_token(user)
            reset_link = f"http://localhost:5173/reset-password/{uid}/{token}"

            # 🔹 envoie email
            send_mail(
                "Réinitialisation de mot de passe",
                f"Bonjour, cliquez ici pour réinitialiser : {reset_link}",
                "noreply@support.com",
                [email],
                fail_silently=False,
            )
            return Response({"message": "Email envoyé ✅"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "Utilisateur non trouvé"}, status=status.HTTP_404_NOT_FOUND)

# Vue générique pour confirmer la réinitialisation du mot de passe
class PasswordResetConfirmView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = serializers.Serializer
    
    def post(self, request):
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            # Recherche par UUID au lieu d'ID numérique
            user = User.objects.get(pk=uuid.UUID(uid))

            if token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()
                return Response({"message": "Mot de passe changé ✅"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Token invalide"}, status=status.HTTP_400_BAD_REQUEST)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({"error": "Lien invalide"}, status=status.HTTP_400_BAD_REQUEST)

class RegisterClientView(generics.CreateAPIView):  # Changez de ListCreateAPIView à CreateAPIView
    serializer_class = ClientCreateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Le sérialiseur crée déjà le client et l'utilisateur associé
        client = serializer.save()
        
        # Générer tokens JWT pour l'utilisateur créé
        refresh = RefreshToken.for_user(client.user)

        return Response({
            "user": {
                "id": client.user.id,
                "username": client.user.username,
                "email": client.user.email,
                "first_name": client.user.first_name,
                "last_name": client.user.last_name,
                "userType": "client"
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }, status=status.HTTP_201_CREATED)

class RegisterTechnicianView(generics.CreateAPIView):  # Changez de ListCreateAPIView à CreateAPIView
    serializer_class = TechnicianCreateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Le sérialiseur crée déjà le technicien et l'utilisateur associé
        technician = serializer.save()
        
        # Générer tokens JWT pour l'utilisateur créé
        refresh = RefreshToken.for_user(technician.user)

        return Response({
            "user": {
                "id": technician.user.id,
                "username": technician.user.username,
                "email": technician.user.email,
                "first_name": technician.user.first_name,
                "last_name": technician.user.last_name,
                "userType": "technician"
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }, status=status.HTTP_201_CREATED)
# Vue générique pour le jeton CSRF
class CSRFTokenView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response({'csrfToken': get_token(request)})

# Vue générique pour rafraîchir le jeton JWT
class RefreshTokenView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)
            return Response({'access': access_token})
        except Exception as e:
            return Response({'error': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)

# Vue générique pour le profil utilisateur
class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserUpdateSerializer
    
    def get_object(self):
        return self.request.user