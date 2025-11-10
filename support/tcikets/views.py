
import logging
import uuid
import calendar
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

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

from support.utils.whatsapp_service import WhatsAppService, notify_ticket_created, notify_ticket_assigned
from support.utils.export_utils import export_ticket_pdf, export_tickets_excel
from support.utils.report_utils import export_intervention_pdf, export_monthly_report_excel
from support.utils.pdf_utils import intervention_to_pdf_buffer
from .permissions import IsAdminOrOwner
from .models import (
    User, Client, Technician, Ticket, Intervention, TicketImage, TechnicianRating, ClientRating,
    Message, PendingConfirmation
)
from .serializers import (
    ClientSerializer, ClientCreateSerializer,
    TechnicianSerializer, TechnicianCreateSerializer,
    TicketSerializer, TicketCreateSerializer,
    InterventionSerializer, InterventionCreateSerializer,
    UserSerializer, TechnicianRatingSerializer,
    ClientRatingSerializer, MessageSerializer
)

logger = logging.getLogger(__name__)
whatsapp_service = WhatsAppService()

# Fonctions helper manquantes
def get_user_profile(user):
    """Get the appropriate profile based on user type"""
    if user.userType == "client":
        return getattr(user, "client_profile", None)
    elif user.userType == "technician":
        return getattr(user, "technician_profile", None)
    return None

def check_ticket_permission(user, ticket):
    """Check if user has permission to access ticket"""
    if user.userType == "admin" or user.is_staff:
        return True
    elif user.userType == "client":
        return ticket.client.user == user
    elif user.userType == "technician":
        return ticket.technician and ticket.technician.user == user
    return False

def generate_intervention_pdf(intervention):
    """Generate PDF for intervention - placeholder function"""
    # Cette fonction doit être implémentée dans vos utils
    try:
        from support.utils.pdf_utils import intervention_to_pdf_buffer
        buffer = intervention_to_pdf_buffer(intervention)
        # Retourner l'URL ou le chemin du PDF généré
        return f"/media/interventions/{intervention.id}.pdf"
    except Exception as e:
        logger.error(f"Erreur génération PDF intervention: {str(e)}")
        return None

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

class TicketListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.userType == "client":
            try:
                profile = Client.objects.get(user=user)
                return Ticket.objects.filter(client=profile)
            except Client.DoesNotExist:
                return Ticket.objects.none()
        elif user.userType == "technician":
            try:
                profile = Technician.objects.get(user=user)
                return Ticket.objects.filter(technician=profile)
            except Technician.DoesNotExist:
                return Ticket.objects.none()
        return Ticket.objects.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TicketCreateSerializer
        return TicketSerializer
    
    def perform_create(self, serializer):
        user = self.request.user

        if user.userType == "client":
            try:
                client = Client.objects.get(user=user)
                if not client:
                    raise ValidationError("User is not associated with a client profile")

                ticket = serializer.save(client=client)
                
                # 🔥 NOTIFICATION CRÉATION TICKET AVEC TWILIO
                try:
                    notify_ticket_created(ticket)
                except Exception as e:
                    logger.error(f"Erreur notification création ticket {ticket.id}: {str(e)}")

            except Client.DoesNotExist:
                raise ValidationError("Client profile not found")

        elif user.userType == "admin":
            client_id = self.request.data.get("client_id")
            if not client_id:
                raise ValidationError("Admin must specify a client for the ticket")
            
            client = get_object_or_404(Client, id=client_id)
            ticket = serializer.save(client=client)
            
            # 🔥 NOTIFICATION CRÉATION TICKET AVEC TWILIO
            try:
                notify_ticket_created(ticket)
            except Exception as e:
                logger.error(f"Erreur notification création ticket {ticket.id}: {str(e)}")

        else:
            raise ValidationError("Only clients or admins can create tickets")

        return ticket

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
            
            # 🔥 NOTIFICATION ASSIGNATION TICKET AVEC TWILIO
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
            
    def perform_create(self, serializer):
        intervention = serializer.save()
        return intervention

class InterventionRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Intervention.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return InterventionCreateSerializer
        return InterventionSerializer

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
        if user.userType == 'admin' or user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=user.id)

    def post(self, request, *args, **kwargs):
        user = request.user
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

        if request.user.userType != 'client':
            raise PermissionDenied("Only clients can rate technicians")

        try:
            client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            raise PermissionDenied("Client profile not found")

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
        
        has_closed_ticket = Ticket.objects.filter(
            client=client,
            technician=technician,
            status='closed'
        ).exists()
        
        if not has_closed_ticket:
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

        if request.user.userType != 'client':
            return Response({'can_rate': False, 'reason': 'Only clients can rate technicians'})

        client = getattr(request.user, "client_profile", None)
        if not client:
            return Response({'can_rate': False, 'reason': 'No client profile found'})

        if TechnicianRating.objects.filter(client=client, technician=technician).exists():
            return Response({'can_rate': False, 'reason': 'Already rated this technician'})

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
        
        if request.user.userType != 'technician':
            return Response({'can_rate': False, 'reason': 'Only technicians can rate clients'})
        
        technician = request.user.technician_profile
        
        if ClientRating.objects.filter(client=client, technician=technician).exists():
            return Response({'can_rate': False, 'reason': 'Already rated this client'})
        
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
        ticket_id = request.GET.get('ticket_id')
        file_format = request.GET.get('format', 'pdf').lower()

        if ticket_id:
            tickets = Ticket.objects.filter(id=ticket_id, client__user=user)
        else:
            tickets = Ticket.objects.filter(client__user=user)

        if not tickets.exists():
            return HttpResponse("No tickets found", status=404)

        if file_format == 'pdf':
            ticket = tickets.first()
            buffer = export_ticket_pdf(ticket)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="ticket_{ticket.id}.pdf"'
            return response

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

        self.check_object_permissions(request, intervention)

        buffer = export_intervention_pdf(intervention)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="intervention_report_{intervention.id}.pdf"'
        return response

class MonthlyReportExcelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
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
        
        user = request.user
        if user.userType != "admin":
            return Response(
                {'error': 'You do not have permission to access this report'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        interventions = Intervention.objects.filter(
            intervention_date__year=year,
            intervention_date__month=month
        ).select_related('ticket', 'ticket__client', 'technician', 'technician__user'
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
    
    pdf_buffer = intervention_to_pdf_buffer(intervention)
    
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="intervention_report_{intervention_id}.pdf"'
    
    return response

# WhatsApp Views
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ticket_whatsapp_messages(request, ticket_id):
    """Récupère l'historique des messages WhatsApp pour un ticket"""
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
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
        
        try:
            confirmation = PendingConfirmation.objects.filter(
                phone_number=from_number,
                expires_at__gt=timezone.now()
            ).latest('created_at')
            
            intervention = confirmation.intervention
            
            if message_body in ['oui', 'yes', 'ok']:
                intervention.status = 'in_progress'
                intervention.save()
                
                whatsapp_service.send_message(
                    from_number, 
                    "✅ Votre confirmation a été enregistrée. L'intervention va commencer."
                )
                
            elif message_body in ['non', 'no', 'cancel']:
                intervention.status = 'cancelled'
                intervention.save()
                
                whatsapp_service.send_message(
                    from_number, 
                    "❌ L'intervention a été annulée comme demandé."
                )
            
            confirmation.delete()
            
        except PendingConfirmation.DoesNotExist:
            logger.info(f"Aucune confirmation en attente pour {from_number}")
            
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
        ticket = Ticket.objects.get(id=ticket_id)
        content = request.data.get('content', '').strip()
        
        user = request.user
        if user.userType not in ['admin', 'technician']:
            return Response(
                {'error': 'Seuls les administrateurs et techniciens peuvent envoyer des messages WhatsApp'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not content:
            return Response(
                {'error': 'Le message ne peut pas être vide'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not ticket.client.phone:
            return Response(
                {'error': 'Le client n\'a pas de numéro de téléphone enregistré'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            whatsapp_service = WhatsAppService()
        except Exception as e:
            logger.error(f"Erreur d'initialisation WhatsAppService: {str(e)}")
            return Response(
                {'error': 'Service WhatsApp non configuré'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        message_sid = whatsapp_service.send_message(ticket.client.phone, content)
        
        if message_sid is None:
            return Response(
                {'error': 'Échec de l\'envoi du message WhatsApp. Vérifiez la configuration Twilio.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        message = Message.objects.create(
            ticket=ticket,
            user=user,
            content=content,
            whatsapp_status='sent',
            whatsapp_sid=message_sid,
            is_whatsapp=True
        )
        
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
            
            user = request.user
            if not (user.userType == 'admin' or 
                   (user.userType == 'technician' and user.technician_profile == intervention.technician)):
                return Response(
                    {'error': 'Vous n\'êtes pas autorisé à finaliser cette intervention'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            intervention.status = 'completed'
            intervention.save()
            
            pdf_url = generate_intervention_pdf(intervention)
            
            whatsapp_service = WhatsAppService()
            # Cette méthode doit être définie dans votre WhatsAppService
            # whatsapp_service.send_intervention_completed_notification(intervention, pdf_url)
            
            return Response({
                'status': 'intervention completed',
                'pdf_url': pdf_url
            })
            
        except Intervention.DoesNotExist:
            return Response(
                {'error': 'Intervention non trouvée'}, 
                status=status.HTTP_404_NOT_FOUND
            )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ticket_messages(request, ticket_id):
    """Récupère tous les messages d'un ticket (normaux + WhatsApp)"""
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
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

# ---------- Vérification config ----------


# ---------- Historique messages ----------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ticket_whatsapp_messages(request, ticket_id):
    """Récupère l'historique WhatsApp d'un ticket"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    user = request.user

    if not (user.userType == 'admin' or
            (user.userType == 'client' and getattr(user, 'client_profile', None) == ticket.client) or
            (user.userType == 'technician' and getattr(user, 'technician_profile', None) == ticket.technician)):
        return Response({'error': 'Permission denied'}, status=403)

    messages = Message.objects.filter(ticket=ticket, is_whatsapp=True).order_by('timestamp')
    serializer = MessageSerializer(messages, many=True, context={'request': request})
    return Response(serializer.data)

# ---------- Webhook ----------
@csrf_exempt
def whatsapp_webhook(request):
    """Webhook pour réponses WhatsApp"""
    if request.method != 'POST':
        return HttpResponse(status=405)

    from_number = request.POST.get('From', '').replace('whatsapp:', '')
    message_body = request.POST.get('Body', '').strip().lower()
    logger.info(f"Message reçu de {from_number}: {message_body}")

    try:
        confirmation = PendingConfirmation.objects.filter(
            phone_number=from_number,
            expires_at__gt=timezone.now()
        ).latest('created_at')

        intervention = confirmation.intervention

        if message_body in ['oui', 'yes', 'ok']:
            intervention.status = 'in_progress'
            intervention.save()
            whatsapp_service.send_message(from_number, "✅ Confirmation reçue, intervention commencera bientôt.")
        elif message_body in ['non', 'no', 'cancel']:
            intervention.status = 'cancelled'
            intervention.save()
            whatsapp_service.send_message(from_number, "❌ Intervention annulée comme demandé.")

        confirmation.delete()

    except PendingConfirmation.DoesNotExist:
        logger.info(f"Aucune confirmation en attente pour {from_number}")
        whatsapp_service.send_message(from_number, "Pas de demande en attente. Contactez le support.")

    return HttpResponse(status=200)

# ---------- Helper DRY pour envoi ----------
def _send_whatsapp(ticket, recipient, content, user, request, send_func, recipient_label):
    if not content:
        return Response({'error': 'Le message ne peut pas être vide'}, status=400)
    if not recipient or not getattr(recipient, 'phone', None):
        return Response({'error': f"Aucun {recipient_label} avec un numéro de téléphone"}, status=400)

    try:
        message_sid = send_func(whatsapp_service, ticket, content, user)
    except Exception as e:
        logger.error(f"Erreur envoi WhatsApp: {e}")
        return Response({'error': f'Erreur lors de l\'envoi: {e}'}, status=500)

    if not message_sid:
        return Response({'error': f'Échec de l\'envoi au {recipient_label}'}, status=500)

    try:
        message = Message.objects.get(whatsapp_sid=message_sid)
        serializer = MessageSerializer(message, context={'request': request})
        data = serializer.data
    except Message.DoesNotExist:
        data = {}
        logger.warning(f"Message envoyé mais non trouvé en DB, SID={message_sid}")

    return Response({
        'status': 'success',
        'message': f'Message envoyé au {recipient_label} avec succès',
        'data': data,
        'whatsapp_sid': message_sid
    }, status=200)

# ---------- Envoi au client ----------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_to_client(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    user = request.user
    if user.userType not in ['admin', 'technician']:
        return Response({'error': 'Seuls admins/techniciens peuvent envoyer'}, status=403)

    content = request.data.get('content', '').strip()
    return _send_whatsapp(
        ticket=ticket,
        recipient=ticket.client,
        content=content,
        user=user,
        request=request,
        send_func=lambda svc, t, c, u: svc.send_to_client(ticket=t, message_body=c, user=u),
        recipient_label="client"
    )

# ---------- Envoi au technicien ----------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_to_technician(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    user = request.user
    if user.userType not in ['admin', 'technician']:
        return Response({'error': 'Seuls admins/techniciens peuvent envoyer'}, status=403)

    content = request.data.get('content', '').strip()
    return _send_whatsapp(
        ticket=ticket,
        recipient=ticket.technician,
        content=content,
        user=user,
        request=request,
        send_func=lambda svc, t, c, u: svc.send_to_technician(ticket=t, message_body=c, user=u),
        recipient_label="technicien"
    )