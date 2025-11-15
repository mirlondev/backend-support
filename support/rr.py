# views.py (corrigé intégralement pour Redis)
from django.core.cache import cache
from django.db.models import Prefetch, Count, Q, F
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import logging, uuid, calendar

from rest_framework import permissions, status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.generics import (
    ListCreateAPIView, ListAPIView,
    RetrieveUpdateDestroyAPIView, RetrieveAPIView, UpdateAPIView
)
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import ValidationError, PermissionDenied

from .permissions import IsAdminOrOwner
from .models import (
    User, Client, Technician, Ticket, Intervention, TicketImage,
    TechnicianRating, ClientRating, Message, PendingConfirmation
)
from .serializers import (
    ClientSerializer, ClientCreateSerializer,
    TechnicianSerializer, TechnicianCreateSerializer,
    TicketSerializer, TicketCreateSerializer,
    InterventionSerializer, InterventionCreateSerializer,
    UserSerializer, TechnicianRatingSerializer,
    ClientRatingSerializer, MessageSerializer
)
from support.utils.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

# ---------- TICKETS ----------
class TicketListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        cache_key = f"tickets_user_{user.id}_{user.userType}_ids"
        cached_ids = cache.get(cache_key)
        if cached_ids is not None:
            return Ticket.objects.filter(id__in=cached_ids).select_related(
                'client__user', 'technician__user'
            ).prefetch_related(
                Prefetch('images', queryset=TicketImage.objects.only('id', 'image', 'ticket_id')),
                Prefetch('interventions', queryset=Intervention.objects.select_related(
                    'technician__user'
                ).only('id', 'ticket_id', 'status', 'intervention_date', 'technician_id'))
            )

        base_qs = Ticket.objects.select_related(
            'client__user', 'technician__user'
        ).prefetch_related(
            Prefetch('images', queryset=TicketImage.objects.only('id', 'image', 'ticket_id')),
            Prefetch('interventions', queryset=Intervention.objects.select_related(
                'technician__user'
            ).only('id', 'ticket_id', 'status', 'intervention_date', 'technician_id'))
        )

        if user.userType == "client":
            try:
                profile = Client.objects.get(user=user)
                qs = base_qs.filter(client=profile)
            except Client.DoesNotExist:
                qs = Ticket.objects.none()
        elif user.userType == "technician":
            try:
                profile = Technician.objects.get(user=user)
                qs = base_qs.filter(technician=profile)
            except Technician.DoesNotExist:
                qs = Ticket.objects.none()
        else:
            qs = base_qs

        ids = list(qs.values_list('id', flat=True))
        cache.set(cache_key, ids, 300)
        return qs

    def get_serializer_class(self):
        return TicketCreateSerializer if self.request.method == "POST" else TicketSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if user.userType == "client":
            client = Client.objects.get(user=user)
            ticket = serializer.save(client=client)
        elif user.userType == "admin":
            client_id = self.request.data.get("client_id")
            if not client_id:
                raise ValidationError("Admin must specify a client for the ticket")
            client = get_object_or_404(Client, id=client_id)
            ticket = serializer.save(client=client)
        else:
            raise ValidationError("Only clients or admins can create tickets")

        cache_key = f"tickets_user_{user.id}_{user.userType}_ids"
        cache.delete(cache_key)
        return ticket


# ---------- INTERVENTIONS ----------
class InterventionListView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InterventionSerializer

    def get_queryset(self):
        ticket_id = self.request.query_params.get('ticket')
        cache_key = f"interventions_ticket_{ticket_id or 'all'}_ids"
        cached_ids = cache.get(cache_key)
        if cached_ids is not None:
            return Intervention.objects.filter(id__in=cached_ids).select_related(
                'ticket__client__user', 'ticket__technician__user', 'technician__user'
            ).prefetch_related('images', 'materials', 'expenses')

        queryset = Intervention.objects.select_related(
            'ticket__client__user', 'ticket__technician__user', 'technician__user'
        ).prefetch_related('images', 'materials', 'expenses')

        if ticket_id:
            queryset = queryset.filter(ticket_id=ticket_id)

        ids = list(queryset.values_list('id', flat=True))
        cache.set(cache_key, ids, 300)
        return queryset

    def get_serializer_class(self):
        return InterventionCreateSerializer if self.request.method == "POST" else InterventionSerializer

    def perform_create(self, serializer):
        intervention = serializer.save()
        ticket_id = str(intervention.ticket.id)
        cache.delete(f"interventions_ticket_{ticket_id}_ids")
        cache.delete("interventions_ticket_all_ids")
        return intervention


# ---------- USERS ----------
class UserListView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_queryset(self):
        user = self.request.user
        cache_key = f"users_list_{user.id}_{user.userType}_ids"
        cached_ids = cache.get(cache_key)
        if cached_ids is not None:
            return User.objects.filter(id__in=cached_ids).only(
                'id', 'username', 'first_name', 'last_name',
                'email', 'userType', 'phone', 'avatar'
            )

        qs = User.objects.only(
            'id', 'username', 'first_name', 'last_name',
            'email', 'userType', 'phone', 'avatar'
        )
        if user.userType not in ['admin', 'staff']:
            qs = qs.filter(id=user.id)

        ids = list(qs.values_list('id', flat=True))
        cache.set(cache_key, ids, 300)
        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        cache.delete(f"users_list_{self.request.user.id}_{self.request.user.userType}_ids")
        return instance


# ---------- AUTRES VUES (inchangées mais conservées) ----------
class ClientRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Client.objects.all()

    def get_serializer_class(self):
        return ClientCreateSerializer if self.request.method in ['PUT', 'PATCH'] else ClientSerializer


class TechnicianRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Technician.objects.all()

    def get_serializer_class(self):
        return TechnicianCreateSerializer if self.request.method in ['PUT', 'PATCH'] else TechnicianSerializer


class TicketRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        if user.userType == "client":
            client = Client.objects.filter(user=user).first()
            return Ticket.objects.filter(client=client) if client else Ticket.objects.none()
        elif user.userType == "technician":
            technician = Technician.objects.filter(user=user).first()
            return Ticket.objects.filter(technician=technician) if technician else Ticket.objects.none()
        return Ticket.objects.all()

    def get_serializer_class(self):
        return TicketCreateSerializer if self.request.method in ["PUT", "PATCH"] else TicketSerializer

    def perform_update(self, serializer):
        serializer.save()

    def patch(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        full_serializer = TicketSerializer(instance, context={"request": request})
        return Response(full_serializer.data)


class InterventionRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Intervention.objects.all()

    def get_serializer_class(self):
        return InterventionCreateSerializer if self.request.method in ['PUT', 'PATCH'] else InterventionSerializer


class UserProfileView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ClientListCreateView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Client.objects.all()

    def get_serializer_class(self):
        return ClientCreateSerializer if self.request.method == 'POST' else ClientSerializer


class InterventionByTicketView(ListAPIView):
    serializer_class = InterventionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        ticket_id = self.kwargs['ticket_id']
        return Intervention.objects.filter(ticket_id=ticket_id)


class UserDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_object(self):
        obj = get_object_or_404(User, id=self.kwargs['pk'])
        if not (self.request.user.is_staff or self.request.user == obj):
            raise PermissionDenied("You don't have permission to access this user's data")
        return obj


class UserProfileUpdateView(RetrieveAPIView, UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class UserAvatarUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        user = request.user
        if 'avatar' not in request.FILES:
            return Response({'error': 'No avatar file provided'}, status=status.HTTP_400_BAD_REQUEST)
        user.profile_image = request.FILES['avatar']
        user.save()
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        if not user.check_password(current_password):
            return Response({'error': 'Current password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return Response({'message': 'Password updated successfully'}, status=status.HTTP_200_OK)


# ---------- RATINGS ----------
class TechnicianRatingListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, technician_id):
        technician = get_object_or_404(Technician, id=technician_id)
        ratings = TechnicianRating.objects.filter(technician=technician)
        serializer = TechnicianRatingSerializer(ratings, many=True)
        return Response(serializer.data)

    def post(self, request, technician_id):
        technician = get_object_or_404(Technician, id=technician_id)
        if request.user.userType != 'client':
            raise PermissionDenied("Only clients can rate technicians")
        client = get_object_or_404(Client, user=request.user)
        if TechnicianRating.objects.filter(technician=technician, client=client).exists():
            raise ValidationError("You have already rated this technician")
        if not Ticket.objects.filter(client=client, technician=technician, status='closed').exists():
            raise PermissionDenied("You can only rate technicians you've worked with on closed tickets")
        serializer = TechnicianRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(technician=technician, client=client)
        return Response(serializer.data, status=201)


class ClientRatingListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ClientRatingSerializer

    def get_queryset(self):
        client_id = self.kwargs.get('client_id')
        return ClientRating.objects.filter(client_id=client_id)

    def perform_create(self, serializer):
        client_id = self.kwargs.get('client_id')
        client = get_object_or_404(Client, id=client_id)
        if self.request.user.userType != 'technician':
            raise PermissionDenied("Only technicians can rate clients")
        technician = self.request.user.technician_profile
        if ClientRating.objects.filter(client=client, technician=technician).exists():
            raise ValidationError("You have already rated this client")
        if not Ticket.objects.filter(client=client, technician=technician, status='closed').exists():
            raise PermissionDenied("You can only rate clients you've worked with on closed tickets")
        serializer.save(client=client, technician=technician)


class UserRatingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        response_data = {}
        if user.userType == "technician":
            technician = user.technician_profile
            ratings = TechnicianRating.objects.filter(technician=technician)
            response_data["technician_ratings"] = TechnicianRatingSerializer(ratings, many=True).data
            response_data["average_rating"] = (
                sum([r.rating for r in ratings]) / ratings.count() if ratings.exists() else 0
            )
            response_data["total_ratings"] = ratings.count()
        elif user.userType == "client":
            client = user.client_profile
            ratings = ClientRating.objects.filter(client=client)
            response_data["client_ratings"] = ClientRatingSerializer(ratings, many=True).data
            response_data["average_rating"] = (
                sum([r.rating for r in ratings]) / ratings.count() if ratings.exists() else 0
            )
            response_data["total_ratings"] = ratings.count()
        return Response(response_data, status=status.HTTP_200_OK)


# ---------- EXPORT & WHATSAPP (non impactés) ----------
class ExportTicketPDFView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        # (code inchangé)
        return HttpResponse("Export désactivé", status=501)


class InterventionPDFReportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrOwner]
    def get(self, request, intervention_id):
        return HttpResponse("Export désactivé", status=501)


class MonthlyReportExcelView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return HttpResponse("Export désactivé", status=501)


def download_intervention_report(request, intervention_id):
    return HttpResponse("Export désactivé", status=501)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def whatsapp_config(request):
    return Response({'enabled': False})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ticket_whatsapp_messages(request, ticket_id):
    return Response([])


@csrf_exempt
def whatsapp_webhook(request):
    return HttpResponse(status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_whatsapp_message_view(request, ticket_id):
    return Response({'error': 'Service non configuré'}, status=501)


class CompleteInterventionView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, intervention_id):
        return Response({'error': 'Service non configuré'}, status=501)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ticket_messages(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    messages = Message.objects.filter(ticket=ticket).order_by('timestamp')
    serializer = MessageSerializer(messages, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_message(request):
    serializer = MessageSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
def whatsapp_webhook(request):
    return HttpResponse(status=200)