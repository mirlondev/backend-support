from rest_framework import permissions, status
from adrf.decorators import api_view
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView,ListAPIView, RetrieveUpdateDestroyAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from support.utils.export_utils import export_ticket_pdf, export_tickets_excel
from .models import User, Client, Technician, Ticket, Intervention, TicketImage,TechnicianRating,ClientRating
from .serializers import (
    ClientSerializer, ClientCreateSerializer,
    TechnicianSerializer, TechnicianCreateSerializer,
    TicketSerializer, TicketCreateSerializer,
    InterventionSerializer, InterventionCreateSerializer,
    UserSerializer,
    TechnicianRatingSerializer,
    ClientRatingSerializer, MessageSerializer
    
)
import io
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from support.utils.report_utils import export_intervention_pdf, export_monthly_report_excel
from .permissions import IsAdminOrOwner
from support.utils.pdf_utils import intervention_to_pdf_buffer
from weasyprint import HTML
import calendar
import uuid
from support.utils.whatsapp_service import WhatsAppService, notify_ticket_created, notify_ticket_assigned
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .models import PendingConfirmation, Intervention
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from .models import Ticket, Client, Message, Technician
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
whatsapp_service = WhatsAppService()
 
 
 

class ClientRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Client.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ClientCreateSerializer
        return ClientSerializer


class TechnicianRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Technician.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return TechnicianCreateSerializer
        return TechnicianSerializer
    

    
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

        # admin → tout voir
        return Ticket.objects.all()


    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return TicketCreateSerializer
        return TicketSerializer

    def perform_update(self, serializer):
        serializer.save()

    def patch(self, request, *args, **kwargs):
        """PATCH pour renvoyer le ticket complet avec relations"""
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        full_serializer = TicketSerializer(instance, context={"request": request})
        return Response(full_serializer.data)

# Vue pour les actions personnalisées sur les tickets

#Tickets


class TicketActionsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk, action):
        try:
            ticket = Ticket.objects.get(pk=pk)
            
            if not check_ticket_permission(request.user, ticket):
                return Response(
                    {'error': 'You do not have permission to perform this action'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if action == 'assign':
                return self._assign_technician(ticket, request)
            elif action == 'start_diagnostic':
                return self._start_diagnostic(ticket)
            else:
                return Response(
                    {'error': 'Invalid action'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    def _assign_technician(self, ticket, request):
        """Assign technician to ticket"""
        technician_id = request.data.get('technician_id')
        if not technician_id:
            return Response({'error': 'technician_id is required'}, status=400)
        
        try:
            technician_uuid = uuid.UUID(str(technician_id).strip())
            technician = Technician.objects.get(id=technician_uuid)
            
            if ticket.technician == technician:
                return Response({'status': 'technician already assigned'})
            
            ticket.technician = technician
            ticket.status = 'in_progress'
            ticket.save()
            
            # 🔥 NOTIFICATION ASSIGNATION TICKET
            try:
                notify_ticket_assigned(ticket)
            except Exception as e:
                logger.error(f"Erreur notification assignation ticket {ticket.id}: {str(e)}")
            
            return Response({'status': 'technician assigned'})
            
        except (ValueError, uuid.UUID) as e:
            return Response({'error': 'Invalid technician UUID'}, status=400)
        except Technician.DoesNotExist:
            return Response({'error': 'Technician not found'}, status=404)

    def _start_diagnostic(self, ticket):
        """Start diagnostic process"""
        ticket.status = 'in_progress'
        ticket.save()
        return Response({'status': 'diagnostic started'})











class InterventionListView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InterventionSerializer

    def get_queryset(self):
        queryset = Intervention.objects.all()
        ticket_id = self.request.query_params.get('ticket')
        if ticket_id:
            queryset = queryset.filter(ticket_id=ticket_id)
        return queryset

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return InterventionCreateSerializer
        return InterventionSerializer

    '''def perform_create(self, serializer):
        user = self.request.user
        if user.userType == 'technician':
            intervention=serializer.save(technician=user.technician)
        else:
            serializer.save()'''
            
    def perform_create(self, serializer):
        intervention = serializer.save()
        
        # Notification de création d'intervention
       
        
        return intervention


class InterventionRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Intervention.objects.all()
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return InterventionCreateSerializer
        return InterventionSerializer


# Vue pour le profil utilisateur
class UserProfileView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    
    def get_object(self):
        return self.request.user


# Vue générique pour les clients
class ClientListCreateView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Client.objects.all()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ClientCreateSerializer
        return ClientSerializer

class InterventionByTicketView(ListAPIView):
    serializer_class = InterventionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        ticket_id = self.kwargs['ticket_id']
        return Intervention.objects.filter(ticket_id=ticket_id)


class UserListView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        user = self.request.user

        # Si l'utilisateur est admin OU staff → il voit tout
        if user.userType == 'admin' or user.is_staff:
            return User.objects.all()

        # Sinon, il ne voit que lui-même
        return User.objects.filter(id=user.id)

    def post(self, request, *args, **kwargs):
        user = request.user

        # Seul admin ou staff peut créer un utilisateur
        if user.userType != 'admin' and not user.is_staff:
            return Response(
                {'error': 'Not allowed to create a user'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        return super().post(request, *args, **kwargs)

class UserDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_object(self):
        obj = get_object_or_404(User, id=self.kwargs['pk'])
        # Only allow staff users or the user themselves to access the detail
        if not (self.request.user.is_staff or self.request.user == obj):
            raise PermissionDenied("You don't have permission to access this user's data")
        return obj
    
    
    
class UserProfileView(RetrieveAPIView, UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    
    def get_object(self):
        return self.request.user
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            # You might want to create a UserUpdateSerializer for updates
            return UserSerializer
        return UserSerializer

class UserAvatarUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, *args, **kwargs):
        user = request.user
        if 'avatar' not in request.FILES:
            return Response(
                {'error': 'No avatar file provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
            return Response(
                {'error': 'Current password is incorrect'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()
        
        return Response(
            {'message': 'Password updated successfully'}, 
            status=status.HTTP_200_OK
        )

class TechnicianRatingListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, technician_id):
        technician = get_object_or_404(Technician, id=technician_id)
        ratings = TechnicianRating.objects.filter(technician=technician)
        serializer = TechnicianRatingSerializer(ratings, many=True)
        return Response(serializer.data)

    def post(self, request, technician_id):
        technician = get_object_or_404(Technician, id=technician_id)

        # Vérifie que l'utilisateur est un client
        if request.user.userType != 'client':
            raise PermissionDenied("Only clients can rate technicians")

        # Récupère le profil client
        try:
            client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            raise PermissionDenied("Client profile not found")

        # Vérifie si le client a déjà noté ce technicien
        if TechnicianRating.objects.filter(technician=technician, client=client).exists():
            raise ValidationError("You have already rated this technician")

        # Vérifie si le client a travaillé avec ce technicien sur un ticket fermé
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
        
        # Check if user is a technician
        if self.request.user.userType != 'technician':
            raise PermissionDenied("Only technicians can rate clients")
        
        technician = self.request.user.technician_profile
        
        # Check if technician has already rated this client
        if ClientRating.objects.filter(client=client, technician=technician).exists():
            raise ValidationError("You have already rated this client")
        
        # Check if technician has worked with this client on a closed ticket
        has_closed_ticket = Ticket.objects.filter(
            client=client,
            technician=technician,
            status='closed'
        ).exists()
        
        if not has_closed_ticket:
            raise PermissionDenied("You can only rate clients you've worked with on closed tickets")
        
        serializer.save(client=client, technician=technician)
        
# In your views.py, update the UserRatingsView
class UserRatingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        response_data = {}

        if user.userType == "technician":
            technician = user.technician_profile
            ratings = TechnicianRating.objects.filter(technician=technician)

            response_data["technician_ratings"] = TechnicianRatingSerializer(
                ratings, many=True
            ).data
            response_data["average_rating"] = (
                sum([r.rating for r in ratings]) / ratings.count()
                if ratings.exists()
                else 0
            )
            response_data["total_ratings"] = ratings.count()

        elif user.userType == "client":
            client = user.client_profile
            ratings = ClientRating.objects.filter(client=client)

            response_data["client_ratings"] = ClientRatingSerializer(
                ratings, many=True
            ).data
            response_data["average_rating"] = (
                sum([r.rating for r in ratings]) / ratings.count()
                if ratings.exists()
                else 0
            )
            response_data["total_ratings"] = ratings.count()

        return Response(response_data, status=status.HTTP_200_OK)
    
    
class CanRateTechnicianView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, technician_id):
        technician = get_object_or_404(Technician, id=technician_id)

        # Vérifier que l'utilisateur est un client
        if request.user.userType != 'client':
            return Response({'can_rate': False, 'reason': 'Only clients can rate technicians'})

        client = getattr(request.user, "client", None)
        if not client:
            return Response({'can_rate': False, 'reason': 'No client profile found'})

        # Vérifier si le client a déjà noté ce technicien
        if TechnicianRating.objects.filter(client=client, technician=technician).exists():
            return Response({'can_rate': False, 'reason': 'Already rated this technician'})

        # Vérifier si le client a eu un ticket fermé avec ce technicien
        has_worked_together = Ticket.objects.filter(
            client=client,
            technician=technician,
            status='closed'
        ).exists()

        return Response({'can_rate': has_worked_together, 'reason': ''})
    
class CanRateClientView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, client_id):
        client = get_object_or_404(Client, id=client_id)
        
        # Check if user is a technician
        if request.user.userType != 'technician':
            return Response({'can_rate': False, 'reason': 'Only technicians can rate clients'})
        
        technician = request.user.technician_profile
        
        # Check if technician has already rated this client
        if ClientRating.objects.filter(client=client, technician=technician).exists():
            return Response({'can_rate': False, 'reason': 'Already rated this client'})
        
        # Check if technician has worked with this client
        has_worked_together = Ticket.objects.filter(
            client=client, 
            technician=technician, 
            status='closed'
        ).exists()
        
        return Response({'can_rate': has_worked_together, 'reason': ''})
    
    
class ExportTicketPDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        ticket_id = request.GET.get('ticket_id')  # facultatif : pour un ticket précis
        file_format = request.GET.get('format', 'pdf').lower()  # 'pdf' par défaut

        # Filtrer les tickets
        if ticket_id:
            tickets = Ticket.objects.filter(id=ticket_id, client__user=user)
        else:
            tickets = Ticket.objects.filter(client__user=user)

        if not tickets.exists():
            return HttpResponse("No tickets found", status=404)

        # PDF détaillé pour un seul ticket
        if file_format == 'pdf':
            ticket = tickets.first()
            buffer = export_ticket_pdf(ticket)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="ticket_{ticket.id}.pdf"'
            return response

        # PDF résumé pour tous les tickets
        elif file_format in ["xls", "xlsx", "excel"]:
            buffer = export_tickets_excel(tickets)
            response = HttpResponse(
                buffer,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="tickets_report.xlsx"'
            return response

        else:
            return HttpResponse("Invalid file format", status=400)
        
        
class InterventionPDFReportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrOwner]

    def get(self, request, intervention_id):
        intervention = get_object_or_404(
            Intervention.objects.select_related('technician__user', 'ticket'),
            id=intervention_id
        )

        # Vérifie les permissions
        self.check_object_permissions(request, intervention)

        buffer = export_intervention_pdf(intervention)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="intervention_report_{intervention.id}.pdf"'
        return response


class MonthlyReportExcelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get month and year from query parameters (default to current month)
        current_date = timezone.now()
        month = request.GET.get('month', current_date.month)
        year = request.GET.get('year', current_date.year)
        
        try:
            month = int(month)
            year = int(year)
            
            if month < 1 or month > 12:
                return Response(
                    {'error': 'Month must be between 1 and 12'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if year < 2000 or year > current_date.year + 1:
                return Response(
                    {'error': f'Year must be between 2000 and {current_date.year + 1}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except ValueError:
            return Response(
                {'error': 'Month and year must be valid integers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier que seul l'admin peut accéder
        user = request.user
        if user.userType != "admin":
            return Response(
                {'error': 'You do not have permission to access this report'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Récupérer les interventions
        interventions = Intervention.objects.filter(
            intervention_date__year=year,
            intervention_date__month=month
        ).select_related(
            'ticket', 
            'ticket__client', 
            'technician', 
            'technician__user'
        ).order_by('intervention_date', 'start_time')
        
        if not interventions.exists():
            return Response(
                {'error': 'No interventions found for the specified period'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            buffer = export_monthly_report_excel(interventions, month, year)
        except Exception as e:
            return Response(
                {'error': f'Error generating Excel report: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        month_name = calendar.month_name[month]
        filename = f"monthly_intervention_report_{month_name}_{year}.xlsx"
        
        response = HttpResponse(
            buffer.getvalue(), 
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response

    

def download_intervention_report(request, intervention_id):
    intervention = get_object_or_404(Intervention, id=intervention_id)
    
    # Generate PDF
    pdf_buffer = intervention_to_pdf_buffer(intervention)
    
    # Create response
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="intervention_report_{intervention_id}.pdf"'
    
    return response


#whatsapp responses
# views.py
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def whatsapp_config(request):
    """Vérifie si WhatsApp est configuré"""
    try:
        config = {
            'enabled': bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN),
            'whatsapp_number': settings.TWILIO_WHATSAPP_NUMBER if hasattr(settings, 'TWILIO_WHATSAPP_NUMBER') else None,
            'status': 'configured' if all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN]) else 'not_configured'
        }
        return Response(config)
    except Exception as e:
        logger.error(f"Erreur dans whatsapp_config: {str(e)}")
        return Response(
            {'error': 'Erreur lors de la récupération de la configuration WhatsApp'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
# views.py
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ticket_whatsapp_messages(request, ticket_id):
    """Récupère l'historique des messages WhatsApp pour un ticket"""
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
        # Vérifier les permissions
        user = request.user
        has_permission = False
        
        if user.userType == 'admin':
            has_permission = True
        elif user.userType == 'client':
            # Vérifier si l'utilisateur est le client du ticket
            try:
                client_profile = Client.objects.get(user=user)
                has_permission = (client_profile == ticket.client)
            except Client.DoesNotExist:
                has_permission = False
        elif user.userType == 'technician':
            # Vérifier si l'utilisateur est le technicien assigné au ticket
            try:
                technician_profile = Technician.objects.get(user=user)
                has_permission = (technician_profile == ticket.technician)
            except Technician.DoesNotExist:
                has_permission = False
        
        if not has_permission:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Récupérer les messages WhatsApp liés à ce ticket
        messages = Message.objects.filter(ticket=ticket, is_whatsapp=True).order_by('timestamp')
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        
        return Response(serializer.data)
        
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)

@csrf_exempt
def whatsapp_webhook(request):
    """
    Webhook pour recevoir et traiter les réponses WhatsApp
    """
    if request.method == 'POST':
        from_number = request.POST.get('From', '').replace('whatsapp:', '')
        message_body = request.POST.get('Body', '').strip().lower()
        
        logger.info(f"Message reçu de {from_number}: {message_body}")
        
        # Chercher une confirmation en attente pour ce numéro
        try:
            confirmation = PendingConfirmation.objects.filter(
                phone_number=from_number,
                expires_at__gt=timezone.now()
            ).latest('created_at')
            
            intervention = confirmation.intervention
            
            if message_body in ['oui', 'yes', 'ok']:
                # Confirmation positive - poursuivre l'intervention
                intervention.status = 'in_progress'
                intervention.save()
                
                # Envoyer confirmation
                whatsapp_service = WhatsAppService()
                whatsapp_service.send_message(
                    from_number, 
                    "✅ Votre confirmation a été enregistrée. L'intervention va commencer."
                )
                
            elif message_body in ['non', 'no', 'cancel']:
                # Confirmation négative - annuler l'intervention
                intervention.status = 'cancelled'
                intervention.save()
                
                # Envoyer confirmation d'annulation
                whatsapp_service = WhatsAppService()
                whatsapp_service.send_message(
                    from_number, 
                    "❌ L'intervention a été annulée comme demandé."
                )
            
            # Supprimer la confirmation traitée
            confirmation.delete()
            
        except PendingConfirmation.DoesNotExist:
            # Aucune confirmation en attente pour ce numéro
            logger.info(f"Aucune confirmation en attente pour {from_number}")
            
            # Optionnel: réponse par défaut
            whatsapp_service = WhatsAppService()
            whatsapp_service.send_message(
                from_number, 
                "Désolé, je n'ai pas de demande en attente de confirmation. Contactez le support pour toute question."
            )
        
        return HttpResponse(status=200)
    
    return HttpResponse(status=405)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_whatsapp_message_view(request, ticket_id):
    """
    Envoie un message WhatsApp lié à un ticket
    """
    try:
        # Récupérer le ticket
        ticket = Ticket.objects.get(id=ticket_id)
        content = request.data.get('content', '').strip()
        
        # Vérifier les permissions
        user = request.user
        if user.userType not in ['admin', 'technician']:
            return Response(
                {'error': 'Seuls les administrateurs et techniciens peuvent envoyer des messages WhatsApp'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Vérifier que le message n'est pas vide
        if not content:
            return Response(
                {'error': 'Le message ne peut pas être vide'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier que le client a un numéro de téléphone
        if not ticket.client.phone:
            return Response(
                {'error': 'Le client n\'a pas de numéro de téléphone enregistré'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Initialiser le service WhatsApp
        try:
            whatsapp_service = WhatsAppService()
        except Exception as e:
            logger.error(f"Erreur d'initialisation WhatsAppService: {str(e)}")
            return Response(
                {'error': 'Service WhatsApp non configuré'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Envoyer le message via WhatsApp
        message_sid = whatsapp_service.send_message(ticket.client.phone, content)
        
        # Vérifier explicitement si l'envoi a réussi
        if message_sid is None:
            return Response(
                {'error': 'Échec de l\'envoi du message WhatsApp. Vérifiez la configuration Twilio.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Créer l'entrée dans la base de données
        message = Message.objects.create(
            ticket=ticket,
            user=user,
            content=content,
            whatsapp_status='sent',
            whatsapp_sid=message_sid,
            is_whatsapp=True
        )
        
        # Sérialiser la réponse avec le contexte de la requête
        serializer = MessageSerializer(message, context={'request': request})
        
        return Response({
            'status': 'success',
            'message': 'Message WhatsApp envoyé avec succès',
            'data': serializer.data,
            'whatsapp_sid': message_sid
        }, status=status.HTTP_200_OK)
        
    except Ticket.DoesNotExist:
        return Response(
            {'error': 'Ticket non trouvé'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Erreur dans send_whatsapp_message_view: {str(e)}")
        return Response(
            {'error': f'Erreur serveur: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
        
class CompleteInterventionView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, intervention_id):
        try:
            intervention = Intervention.objects.get(id=intervention_id)
            
            # Vérifier que l'utilisateur est le technicien assigné ou un admin
            user = request.user
            if not (user.userType == 'admin' or 
                   (user.userType == 'technician' and user.technician_profile == intervention.technician)):
                return Response(
                    {'error': 'Vous n\'êtes pas autorisé à finaliser cette intervention'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Finaliser l'intervention
            intervention.status = 'completed'
            intervention.save()
            
            # Générer le PDF
            pdf_url = generate_intervention_pdf(intervention)
            
            # Envoyer les notifications
            whatsapp_service = WhatsAppService()
            whatsapp_service.send_intervention_completed_notification(intervention, pdf_url)
            
            return Response({
                'status': 'intervention completed',
                'pdf_url': pdf_url
            })
            
        except Intervention.DoesNotExist:
            return Response(
                {'error': 'Intervention non trouvée'}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
   # views.py
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ticket_messages(request, ticket_id):
    """Récupère tous les messages d'un ticket (normaux + WhatsApp)"""
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
        # Vérifier les permissions
        user = request.user
        has_permission = False
        
        if user.userType == 'admin':
            has_permission = True
        elif user.userType == 'client':
            try:
                client_profile = Client.objects.get(user=user)
                has_permission = (client_profile == ticket.client)
            except Client.DoesNotExist:
                has_permission = False
        elif user.userType == 'technician':
            try:
                technician_profile = Technician.objects.get(user=user)
                has_permission = (technician_profile == ticket.technician)
            except Technician.DoesNotExist:
                has_permission = False
        
        if not has_permission:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Récupérer tous les messages du ticket
        messages = Message.objects.filter(ticket=ticket).order_by('timestamp')
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        
        return Response(serializer.data)
        
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_message(request):
    """Crée un nouveau message (normal, pas WhatsApp)"""
    try:
        serializer = MessageSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur dans create_message: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    

def _send_whatsapp(ticket, content, recipient, user, request, send_func, recipient_label):
    # Vérifier que le message n'est pas vide
    if not content:
        return Response(
            {'error': 'Le message ne peut pas être vide'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Vérifier qu'il y a un numéro de téléphone
    if not recipient or not recipient.phone:
        return Response(
            {'error': f"Aucun {recipient_label} avec un numéro de téléphone"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Initialiser le service
    try:
        whatsapp_service = WhatsAppService()
    except Exception as e:
        logger.error(f"Erreur d'initialisation WhatsAppService: {str(e)}")
        return Response(
            {'error': 'Service WhatsApp non configuré'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    # Envoyer le message
    try:
        message_sid = send_func(whatsapp_service, ticket, content, user)
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi WhatsApp: {str(e)}")
        return Response(
            {'error': f'Erreur lors de l\'envoi: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    if not message_sid:
        return Response(
            {'error': f'Échec de l\'envoi du message WhatsApp au {recipient_label}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Récupérer le message créé
    try:
        message = Message.objects.get(whatsapp_sid=message_sid)
        serializer = MessageSerializer(message, context={'request': request})
        return Response({
            'status': 'success',
            'message': f'Message envoyé au {recipient_label} avec succès',
            'data': serializer.data,
            'whatsapp_sid': message_sid
        }, status=status.HTTP_200_OK)
    except Message.DoesNotExist:
        return Response({
            'status': 'success',
            'message': f'Message envoyé au {recipient_label} avec succès',
            'whatsapp_sid': message_sid,
            'warning': 'Le message n\'a pas été trouvé dans la base de données'
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_to_client(request, ticket_id):
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        user = request.user

        if user.userType not in ['admin', 'technician']:
            return Response(
                {'error': 'Seuls les administrateurs et techniciens peuvent envoyer des messages'},
                status=status.HTTP_403_FORBIDDEN
            )

        content = request.data.get('content', '').strip()
        return _send_whatsapp(
            ticket=ticket,
            content=content,
            recipient=ticket.client,
            user=user,
            request=request,
            send_func=lambda service, t, c, u: service.send_to_client(ticket=t, message_body=c, user=u),
            recipient_label="client"
        )
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket non trouvé'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_to_technician(request, ticket_id):
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        user = request.user

        if user.userType not in ['admin', 'technician']:
            return Response(
                {'error': 'Seuls les administrateurs et techniciens peuvent envoyer des messages'},
                status=status.HTTP_403_FORBIDDEN
            )

        content = request.data.get('content', '').strip()
        return _send_whatsapp(
            ticket=ticket,
            content=content,
            recipient=ticket.technician,
            user=user,
            request=request,
            send_func=lambda service, t, c, u: service.send_to_technician(ticket=t, message_body=c, user=u),
            recipient_label="technicien"
        )
    except Ticket.DoesNotExist:
        return Response({'error': 'Ticket non trouvé'}, status=status.HTTP_404_NOT_FOUND)
    
    

        
def assign_technician(ticket, technician_id, user, request):
    try:
        technician_uuid = uuid.UUID(str(technician_id).strip())
        technician = Technician.objects.get(id=technician_uuid)
    except ValueError:
        return Response({'error': 'Invalid technician UUID'}, status=400)
    except Technician.DoesNotExist:
        return Response({'error': 'Technician not found'}, status=404)

    # Vérifier si déjà assigné
    if ticket.technician == technician:
        return Response({'status': 'technician already assigned'}, status=200)

    # Assigner
    ticket.technician = technician
    ticket.status = 'in_progress'
    ticket.save()

    # Notifier via WhatsApp
    return notify_technician(ticket, user, "Un nouveau ticket vous a été assigné", request)