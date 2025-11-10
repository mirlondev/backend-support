from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView,ListAPIView, RetrieveUpdateDestroyAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from support.utils.export_utils import export_tickets_pdf, export_tickets_excel
from django.http import HttpResponse
from .models import User, Client, Technician, Ticket, Intervention, TicketImage,TechnicianRating,ClientRating
from .serializers import (
    ClientSerializer, ClientCreateSerializer,
    TechnicianSerializer, TechnicianCreateSerializer,
    TicketSerializer, TicketCreateSerializer,
    InterventionSerializer, InterventionCreateSerializer,
    UserSerializer,
    TechnicianRatingSerializer,
    ClientRatingSerializer
    
)
import io
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from support.utils.report_utils import export_intervention_pdf, export_monthly_report_excel
from .permissions import IsAdminOrOwner
from support.utils.pdf_utils import intervention_to_pdf_buffer
from weasyprint import HTML
import calendar
import uuid


class ClientRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Client.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ClientCreateSerializer
        return ClientSerializer

# Vue générique pour les techniciens
class TechnicianListCreateView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Technician.objects.all()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TechnicianCreateSerializer
        return TechnicianSerializer

class TechnicianRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Technician.objects.all()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return TechnicianCreateSerializer
        return TechnicianSerializer

# Vue générique pour les tickets
class TicketListCreateView(ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Admin ou staff
        if getattr(user, 'userType', 'admin') == 'admin' or user.is_staff:
            return Ticket.objects.all()
        
        # Client
        try:
            client = Client.objects.get(user=user)
            return Ticket.objects.filter(client=client)
        except Client.DoesNotExist:
            pass
        
        # Technicien
        try:
            technician = Technician.objects.get(user=user)
            return Ticket.objects.filter(technician=technician)
        except Technician.DoesNotExist:
            pass
        
        return Ticket.objects.none()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TicketCreateSerializer
        return TicketSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

class TicketRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Admin ou staff
        if getattr(user, 'userType', 'admin') == 'admin' or user.is_staff:
            return Ticket.objects.all()
        
        # Client
        try:
            client = Client.objects.get(user=user)
            return Ticket.objects.filter(client=client)
        except Client.DoesNotExist:
            pass
        
        # Technicien
        try:
            technician = Technician.objects.get(user=user)
            return Ticket.objects.filter(technician=technician)
        except Technician.DoesNotExist:
            pass
        
        return Ticket.objects.none()
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return TicketCreateSerializer
        return TicketSerializer

# Vue pour les actions personnalisées sur les tickets
class TicketActionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk, action):
        try:
            ticket = Ticket.objects.get(pk=pk)
            
            # Vérifier les permissions
            user = request.user
            if not (user.is_staff or getattr(user, 'userType', '') == 'admin'):
                # Vérifier si l'utilisateur est le client ou le technicien assigné
                is_client = hasattr(user, 'client_profile') and user.client_profile == ticket.client
                is_technician = hasattr(user, 'technician_profile') and user.technician_profile == ticket.technician
                
                if not (is_client or is_technician):
                    return Response(
                        {'error': 'You do not have permission to perform this action'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            
            if action == 'assign':
                technician_id = request.data.get('technician_id')
                
                if not technician_id:
                    return Response({'error': 'technician_id is required'}, status=400)
                
                try:
                    technician_uuid = uuid.UUID(str(technician_id).strip())
                    technician = Technician.objects.get(id=technician_uuid)
                    
                    # Vérifier si le technicien est déjà assigné
                    if ticket.technician == technician:
                        return Response(
                            {'status': 'technician already assigned'},
                            status=200
                        )
                    
                    ticket.technician = technician
                    ticket.status = 'in_progress'
                    ticket.save()
                    return Response({'status': 'technician assigned'})
                
                except ValueError:
                    return Response({'error': 'Invalid technician UUID'}, status=400)
                except Technician.DoesNotExist:
                    return Response({'error': 'Technician not found'}, status=404)

                except Ticket.DoesNotExist:
                    return Response(
                        {'error': 'Ticket not found'}, 
                        status=status.HTTP_404_NOT_FOUND
                    )

                
        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

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
        user = self.request.user
        if hasattr(user, 'technician_profile'):
            serializer.save(technician=user.technician_profile)
        else:
            serializer.save()


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
        if getattr(user, 'userType', None) == 'admin' or user.is_staff:
            return User.objects.all()

        # Sinon, il ne voit que lui-même
        return User.objects.filter(id=user.id)

    def post(self, request, *args, **kwargs):
        user = request.user

        # Seul admin ou staff peut créer un utilisateur
        if getattr(user, 'userType', None) != 'admin' and not user.is_staff:
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

# In your TechnicianRatingListCreateView, add a check for closed tickets
class TechnicianRatingListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TechnicianRatingSerializer
    
    def get_queryset(self):
        technician_id = self.kwargs.get('technician_id')
        return TechnicianRating.objects.filter(technician_id=technician_id)
    
    def perform_create(self, serializer):
        technician_id = self.kwargs.get('technician_id')
        technician = get_object_or_404(Technician, id=technician_id)
        
        # Check if user is a client
        try:
            client = Client.objects.get(user=self.request.user)
        except Client.DoesNotExist:
            raise PermissionDenied("Only clients can rate technicians")
        
        # Check if client has already rated this technician
        if TechnicianRating.objects.filter(technician=technician, client=client).exists():
            raise ValidationError("You have already rated this technician")
        
        # Check if client has worked with this technician on a closed ticket
        has_closed_ticket = Ticket.objects.filter(
            client=client,
            technician=technician,
            status='closed'
        ).exists()
        
        if not has_closed_ticket:
            raise PermissionDenied("You can only rate technicians you've worked with on closed tickets")
        
        serializer.save(technician=technician, client=client)
        
        
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
        try:
            technician = Technician.objects.get(user=self.request.user)
        except Technician.DoesNotExist:
            raise PermissionDenied("Only technicians can rate clients")
        
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
        
        # Check if user is a technician
        if hasattr(user, 'technician_profile'):
            technician = user.technician_profile
            ratings = TechnicianRating.objects.filter(technician=technician)
            response_data['technician_ratings'] = TechnicianRatingSerializer(ratings, many=True).data
            
            # Safe way to get average rating
            try:
                response_data['average_rating'] = technician.average_rating()
            except AttributeError:
                # Calculate manually if method doesn't exist
                if ratings.exists():
                    response_data['average_rating'] = sum([r.rating for r in ratings]) / ratings.count()
                else:
                    response_data['average_rating'] = 0
                    
            response_data['total_ratings'] = ratings.count()
        
        # Check if user is a client
        if hasattr(user, 'client_profile'):
            client = user.client_profile
            ratings = ClientRating.objects.filter(client=client)
            response_data['client_ratings'] = ClientRatingSerializer(ratings, many=True).data
            
            # Safe way to get average rating
            try:
                response_data['average_rating'] = client.average_rating()
            except AttributeError:
                # Calculate manually if method doesn't exist
                if ratings.exists():
                    response_data['average_rating'] = sum([r.rating for r in ratings]) / ratings.count()
                else:
                    response_data['average_rating'] = 0
                    
            response_data['total_ratings'] = ratings.count()
        
        return Response(response_data)
    
class CanRateTechnicianView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, technician_id):
        technician = get_object_or_404(Technician, id=technician_id)
        
        # Check if user is a client
        try:
            client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            return Response({'can_rate': False, 'reason': 'Only clients can rate technicians'})
        
        # Check if client has already rated this technician
        if TechnicianRating.objects.filter(technician=technician, client=client).exists():
            return Response({'can_rate': False, 'reason': 'Already rated this technician'})
        
        # Check if client has worked with this technician on a closed ticket
        has_closed_ticket = Ticket.objects.filter(
            client=client,
            technician=technician,
            status='closed'
        ).exists()
        
        return Response({'can_rate': has_closed_ticket, 'reason': ''})
    permission_classes = [IsAuthenticated]
    
    def get(self, request, technician_id):
        technician = get_object_or_404(Technician, id=technician_id)
        
        # Check if user is a client
        try:
            client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            return Response({'can_rate': False, 'reason': 'Only clients can rate technicians'})
        
        # Check if client has already rated this technician
        if TechnicianRating.objects.filter(technician=technician, client=client).exists():
            return Response({'can_rate': False, 'reason': 'Already rated this technician'})
        
        # Check if client has worked with this technician on a closed ticket
        has_closed_ticket = Ticket.objects.filter(
            client=client,
            technician=technician,
            status='closed'
        ).exists()
        
        return Response({'can_rate': has_closed_ticket, 'reason': ''})

class CanRateClientView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, client_id):
        client = get_object_or_404(Client, id=client_id)
        
        # Check if user is a technician
        try:
            technician = Technician.objects.get(user=request.user)
        except Technician.DoesNotExist:
            return Response({'can_rate': False, 'reason': 'Only technicians can rate clients'})
        
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
    
    
class ExportTicketsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, file_format):
        return self.process_export(request, file_format)
    
    def post(self, request, file_format):
        return self.process_export(request, file_format)
    
    def process_export(self, request, file_format):
        user = request.user

        # Récupération des tickets par rôle
        if getattr(user, 'userType', 'admin') == 'admin' or user.is_staff:
            tickets = Ticket.objects.all()
        elif hasattr(user, 'client_profile'):
            tickets = Ticket.objects.filter(client=user.client_profile)
        elif hasattr(user, 'technician_profile'):
            tickets = Ticket.objects.filter(technician=user.technician_profile)
        else:
            tickets = Ticket.objects.none()

        # Filtres
        status_filter = request.GET.get('status') or request.POST.get('status')
        priority_filter = request.GET.get('priority') or request.POST.get('priority')

        if status_filter:
            tickets = tickets.filter(status=status_filter)
        if priority_filter:
            tickets = tickets.filter(priority=priority_filter)

        # Nom du fichier
        filename = f"tickets_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}"

        if file_format == 'pdf':
            filename += '.pdf'
            buffer = export_tickets_pdf(tickets, filename)
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        elif file_format == 'excel':
            filename += '.xlsx'
            buffer = export_tickets_excel(tickets, filename)
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8''{filename}'
            return response

        return Response({'error': 'Invalid format'}, status=status.HTTP_400_BAD_REQUEST)
    
    
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


'''class MonthlyReportExcelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get month and year from query parameters (default to current month)
        current_date = timezone.now()
        month = request.GET.get('month', current_date.month)
        year = request.GET.get('year', current_date.year)
        
        try:
            month = int(month)
            year = int(year)
            
            # Validate month and year
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
        
        # Get interventions for the specified month and year
        user = request.user
        try:
            if hasattr(user, 'technician_profile'):
                # Technician can only see their own interventions
                interventions = Intervention.objects.filter(
                    technician=user.technician_profile,
                    intervention_date__year=year,
                    intervention_date__month=month
                ).select_related(
                    'ticket', 
                    'ticket__client', 
                    'technician', 
                    'technician__user'
                ).order_by('intervention_date', 'start_time')
            elif user.is_staff:
                # Admin can see all interventions
                interventions = Intervention.objects.filter(
                    intervention_date__year=year,
                    intervention_date__month=month
                ).select_related(
                    'ticket', 
                    'ticket__client', 
                    'technician', 
                    'technician__user'
                ).order_by('intervention_date', 'start_time')
            else:
                return Response(
                    {'error': 'You do not have permission to access this report'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Exception as e:
            return Response(
                {'error': f'Error retrieving interventions: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Check if there are any interventions
        if not interventions.exists():
            return Response(
                {'error': 'No interventions found for the specified period'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate Excel report
        try:
            buffer = export_monthly_report_excel(interventions, month, year)
        except Exception as e:
            return Response(
                {'error': f'Error generating Excel report: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Create response
        month_name = calendar.month_name[month]
        filename = f"monthly_intervention_report_{month_name}_{year}.xlsx"
        
        response = HttpResponse(
            buffer.getvalue(), 
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response'''
        
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
        if getattr(user, "userType", None) != "admin":
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