from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer, UserUpdateSerializer

from django.contrib.auth import get_user_model
User = get_user_model()
from .models import Client, Technician

token_generator = PasswordResetTokenGenerator()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def password_change(request):
    user = request.user
    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")

    if not user.check_password(old_password):
        return Response({"error": "Ancien mot de passe incorrect"}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()
    return Response({"message": "Mot de passe modifié ✅"}, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    email = request.data.get("email")
    try:
        user = User.objects.get(email=email)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
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

@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    uidb64 = request.data.get("uid")
    token = request.data.get("token")
    new_password = request.data.get("new_password")

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)

        if token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            return Response({"message": "Mot de passe changé ✅"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Token invalide"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        return Response({"error": "Lien invalide"}, status=status.HTTP_400_BAD_REQUEST)
    
    
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

class RegisterClientSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()

    
    class Meta:
        model = Client
        fields = ['username', 'password', 'first_name', 'last_name', 'email', 'phone', 'company']
    
    def create(self, validated_data):
        user_data = {
            'username': validated_data.pop('username'),
            'password': validated_data.pop('password'),
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'email': validated_data.pop('email'),
        }
       # user = User.objects.create_user(**user_data)
        user = User.objects.create_user(**user_data, userType='client')

        client = Client.objects.create(user=user, **validated_data)
        return client

class RegisterTechnicianSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    
    class Meta:
        model = Technician
        fields = ['username', 'password', 'first_name', 'last_name', 'email', 'phone', 'specialty']
    
    def create(self, validated_data):
        user_data = {
            'username': validated_data.pop('username'),
            'password': validated_data.pop('password'),
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'email': validated_data.pop('email'),
        }
        #user = User.objects.create_user(**user_data)
        user = User.objects.create_user(**user_data, userType='technician')

        technician = Technician.objects.create(user=user, **validated_data)
        return technician

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({'message': 'Logout successful'})

@api_view(['POST'])
@permission_classes([AllowAny])
def register_client(request):
    serializer = RegisterClientSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Client registered successfully'}, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def register_technician(request):
    serializer = RegisterTechnicianSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Technician registered successfully'}, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_csrf_token(request):
    return Response({'csrfToken': get_token(request)})

@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)
        return Response({'access': access_token})
    except Exception as e:
        return Response({'error': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)
    


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def me_view(request):
    user = request.user

    if request.method == 'GET':
        serializer = UserUpdateSerializer(user)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)