from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView
from .models import User
from .models import Client, Technician, Ticket, Intervention,Procedure,Notification,ProcedureImage,ProcedureInteraction
from .serializers import (
    ClientSerializer, ClientCreateSerializer,
    TechnicianSerializer, TechnicianCreateSerializer,
    TicketSerializer, TicketCreateSerializer,
    InterventionSerializer, InterventionCreateSerializer,
    UserSerializer,
    ProcedureSerializer,
    NotificationSerializer

)
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics
from rest_framework import permissions
from django.utils import timezone
from django.db.models import F

from rest_framework import generics, permissions
from .models import Message, Ticket
from .serializers import MessageSerializer
#old
import os
import uuid
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from PIL import Image as PILImage
from .models import Procedure, ProcedureImage, ProcedureAttachment, ProcedureTag
from .serializers import (
    ProcedureSerializer, 
    ProcedureImageSerializer, 
    ProcedureAttachmentSerializer,
    ProcedureTagSerializer
)
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import Ticket, Message
from .serializers import TicketSerializer, MessageSerializer
from .permissions import IsAdminOrOwner

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.userType == 'client':
            return Ticket.objects.filter(client__user=user)
        elif user.userType == 'technician':
            return Ticket.objects.filter(technician__user=user)
        return Ticket.objects.all()

    # ---------- Action messages ----------
    @action(detail=True, methods=['get', 'post'])
    def messages(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)

        # Vérification permission
        user = request.user
        has_permission = False
        if user.userType == 'admin':
            has_permission = True
        elif user.userType == 'client' and getattr(user, 'client_profile', None) == ticket.client:
            has_permission = True
        elif user.userType == 'technician' and getattr(user, 'technician_profile', None) == ticket.technician:
            has_permission = True

        if not has_permission:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        # ---------- GET messages ----------
        if request.method == 'GET':
            messages = Message.objects.filter(ticket=ticket).order_by('timestamp')
            serializer = MessageSerializer(messages, many=True, context={'request': request})
            return Response(serializer.data)

        # ---------- POST créer message ----------
        elif request.method == 'POST':
            content = request.data.get('content', '').strip()
            if not content:
                return Response({'error': 'Le message ne peut pas être vide'}, status=400)

            message = Message.objects.create(
                ticket=ticket,
                user=user,
                content=content,
                is_whatsapp=False
            )
            serializer = MessageSerializer(message, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

class ProcedureListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = Procedure.objects.filter(is_active=True)
    serializer_class = ProcedureSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.request.user.is_authenticated:
            return queryset.filter(
                Q(status='published') | Q(author=self.request.user)
            ).order_by('-created_at')
        else:
            return queryset.filter(status='published').order_by('-created_at')

    def perform_create(self, serializer):
        procedure = serializer.save(author=self.request.user)
        
        # Handle images_ids if provided
        images_ids = self.request.data.get('images_ids', [])
        if images_ids:
            for image_id in images_ids:
                try:
                    image = ProcedureImage.objects.get(id=image_id, procedure__isnull=True)
                    image.procedure = procedure
                    image.save()
                except ProcedureImage.DoesNotExist:
                    continue

class ProcedureRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = Procedure.objects.all()
    serializer_class = ProcedureSerializer

    def get_object(self):
        obj = super().get_object()
        # Increment view count only for GET requests
        if self.request.method == 'GET':
            obj.views += 1
            obj.save(update_fields=['views'])
        return obj

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Check permissions
        if instance.author != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to update this procedure'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Handle images_ids if provided
        images_ids = request.data.get('images_ids', [])
        if images_ids:
            # Update existing orphaned images to link to this procedure
            for image_id in images_ids:
                try:
                    image = ProcedureImage.objects.get(id=image_id)
                    if image.procedure is None or image.procedure == instance:
                        image.procedure = instance
                        image.save()
                except ProcedureImage.DoesNotExist:
                    continue
        
        return super().update(request, *args, **kwargs)

class ProcedureImageListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ProcedureImage.objects.all()
    serializer_class = ProcedureImageSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        procedure_id = self.request.query_params.get('procedure_id')
        if procedure_id:
            return self.queryset.filter(procedure_id=procedure_id)
        return self.queryset.filter(procedure__author=self.request.user)

class ProcedureAttachmentListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ProcedureAttachment.objects.all()
    serializer_class = ProcedureAttachmentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        procedure_id = self.request.query_params.get('procedure_id')
        if procedure_id:
            return self.queryset.filter(procedure_id=procedure_id)
        return self.queryset.filter(procedure__author=self.request.user)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_procedure_image(request):
    """
    Enhanced endpoint for uploading images with better error handling and optimization
    """
    procedure_id = request.data.get('procedure_id')
    image_file = request.FILES.get('image')
    caption = request.data.get('caption', '')
    alt_text = request.data.get('alt_text', '')

    if not image_file:
        return Response(
            {'error': 'Image file is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate file type
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
    if image_file.content_type not in allowed_types:
        return Response(
            {'error': 'Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate file size (max 10MB)
    if image_file.size > 10 * 1024 * 1024:
        return Response(
            {'error': 'File size too large. Maximum size is 10MB.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    procedure = None
    if procedure_id:
        try:
            procedure = Procedure.objects.get(id=procedure_id)
            # Check if user has permission to add images to this procedure
            if procedure.author != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'You do not have permission to add images to this procedure'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        except Procedure.DoesNotExist:
            return Response(
                {'error': 'Procedure not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    try:
        # Optimize image before saving
        optimized_image = optimize_image(image_file)
        
        # Create the image record
        procedure_image = ProcedureImage.objects.create(
            procedure=procedure,  # Can be None for temporary uploads
            image=optimized_image,
            caption=caption,
            alt_text=alt_text or image_file.name
        )

        serializer = ProcedureImageSerializer(
            procedure_image, 
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response(
            {'error': f'Failed to process image: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_procedure_attachment(request):
    """
    Enhanced endpoint for uploading attachments including videos
    """
    procedure_id = request.data.get('procedure_id')
    file_upload = request.FILES.get('file')
    name = request.data.get('name', '')
    file_type = request.data.get('file_type', '')

    if not file_upload:
        return Response(
            {'error': 'File is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    if not procedure_id:
        return Response(
            {'error': 'procedure_id is required for attachments'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        procedure = Procedure.objects.get(id=procedure_id)
        # Check permissions
        if procedure.author != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to add attachments to this procedure'}, 
                status=status.HTTP_403_FORBIDDEN
            )
    except Procedure.DoesNotExist:
        return Response(
            {'error': 'Procedure not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

    # Validate file type
    allowed_types = [
        # Documents
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/plain',
        # Videos
        'video/mp4',
        'video/avi',
        'video/quicktime',
        'video/x-msvideo',
        'video/webm',
        'video/x-ms-wmv',
        # Archives
        'application/zip',
        'application/x-rar-compressed',
    ]

    if file_upload.content_type not in allowed_types:
        return Response(
            {'error': 'Invalid file type. Please check the allowed file formats.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate file size (max 100MB for videos, 50MB for documents)
    max_size = 100 * 1024 * 1024 if file_upload.content_type.startswith('video/') else 50 * 1024 * 1024
    if file_upload.size > max_size:
        max_size_mb = max_size // (1024 * 1024)
        return Response(
            {'error': f'File size too large. Maximum size is {max_size_mb}MB for this file type.'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Calculate file size in human readable format
        file_size_mb = file_upload.size / (1024 * 1024)
        if file_size_mb >= 1:
            file_size = f"{file_size_mb:.1f} MB"
        else:
            file_size_kb = file_upload.size / 1024
            file_size = f"{file_size_kb:.1f} KB"

        # Create the attachment record
        attachment = ProcedureAttachment.objects.create(
            procedure=procedure,
            file=file_upload,
            name=name or file_upload.name,
            file_type=file_type or file_upload.content_type,
            file_size=file_size
        )

        serializer = ProcedureAttachmentSerializer(
            attachment, 
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {'error': f'Failed to upload attachment: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_procedure_image(request, image_id):
    """
    Enhanced endpoint for deleting procedure images
    """
    try:
        image = ProcedureImage.objects.get(id=image_id)
        
        # Check permissions
        if image.procedure:
            if image.procedure.author != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'You do not have permission to delete this image'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Delete the file from storage
        if image.image:
            try:
                default_storage.delete(image.image.name)
            except:
                pass  # File might already be deleted
        
        image.delete()
        return Response(
            {'message': 'Image deleted successfully'}, 
            status=status.HTTP_200_OK
        )
    
    except ProcedureImage.DoesNotExist:
        return Response(
            {'error': 'Image not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_procedure_attachment(request, attachment_id):
    """
    Enhanced endpoint for deleting procedure attachments
    """
    try:
        attachment = ProcedureAttachment.objects.get(id=attachment_id)
        
        # Check permissions
        if attachment.procedure.author != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to delete this attachment'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete the file from storage
        if attachment.file:
            try:
                default_storage.delete(attachment.file.name)
            except:
                pass  # File might already be deleted
        
        attachment.delete()
        return Response(
            {'message': 'Attachment deleted successfully'}, 
            status=status.HTTP_200_OK
        )
    
    except ProcedureAttachment.DoesNotExist:
        return Response(
            {'error': 'Attachment not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
def serve_media_file(request, file_type, file_id):
    """
    Secure endpoint for serving media files
    """
    try:
        if file_type == 'image':
            media_obj = ProcedureImage.objects.get(id=file_id)
            file_field = media_obj.image
        elif file_type == 'attachment':
            media_obj = ProcedureAttachment.objects.get(id=file_id)
            file_field = media_obj.file
        else:
            raise Http404("Invalid file type")

        # Check if procedure is published or user has permission
        if media_obj.procedure:
            if media_obj.procedure.status != 'published':
                if not request.user.is_authenticated or \
                   (media_obj.procedure.author != request.user and not request.user.is_staff):
                    return Response(
                        {'error': 'You do not have permission to access this file'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )

        # Serve the file
        if not file_field:
            raise Http404("File not found")

        response = HttpResponse(
            default_storage.open(file_field.name).read(),
            content_type=getattr(media_obj, 'file_type', 'application/octet-stream')
        )
        response['Content-Disposition'] = f'inline; filename="{file_field.name}"'
        return response

    except (ProcedureImage.DoesNotExist, ProcedureAttachment.DoesNotExist):
        raise Http404("File not found")

def optimize_image(image_file):
    """
    Optimize image for web use
    """
    try:
        # Open the image
        img = PILImage.open(image_file)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Resize if too large
        max_width, max_height = 1920, 1080
        if img.width > max_width or img.height > max_height:
            img.thumbnail((max_width, max_height), PILImage.Resampling.LANCZOS)
        
        # Save optimized image
        from io import BytesIO
        output = BytesIO()
        
        # Determine format
        format_type = 'JPEG'
        if image_file.name.lower().endswith('.png'):
            format_type = 'PNG'
        elif image_file.name.lower().endswith('.webp'):
            format_type = 'WEBP'
        
        # Save with optimization
        save_kwargs = {'format': format_type, 'optimize': True}
        if format_type == 'JPEG':
            save_kwargs['quality'] = 85
        
        img.save(output, **save_kwargs)
        output.seek(0)
        
        # Create new file
        optimized_file = ContentFile(
            output.read(),
            name=image_file.name
        )
        
        return optimized_file
    
    except Exception:
        # Return original file if optimization fails
        return image_file

# Tag management views
class ProcedureTagListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = ProcedureTag.objects.all()
    serializer_class = ProcedureTagSerializer

    def perform_create(self, serializer):
        # Auto-generate slug from name
        from django.utils.text import slugify
        name = serializer.validated_data['name']
        slug = slugify(name)
        
        # Ensure unique slug
        original_slug = slug
        counter = 1
        while ProcedureTag.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
            
        serializer.save(slug=slug)
#new 

'''class ProcedureListView(generics.ListAPIView):
    serializer_class = ProcedureSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = Procedure.objects.filter(status='published')
        
        # Filtrage par catégorie
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category__icontains=category)
        
        # Filtrage par difficulté
        difficulty = self.request.query_params.get('difficulty', None)
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        
        # Filtrage par tag
        tag = self.request.query_params.get('tag', None)
        if tag:
            queryset = queryset.filter(tags__name__icontains=tag)
        
        # Tri
        sort = self.request.query_params.get('sort', '-created_at')
        if sort in ['created_at', '-created_at', 'views', '-views', 'likes', '-likes']:
            queryset = queryset.order_by(sort)
        
        return queryset'''

'''class ProcedureDetailView(generics.RetrieveAPIView):
    serializer_class = ProcedureSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Procedure.objects.all()
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Incrémenter le compteur de vues
        if request.user.is_authenticated:
            # Enregistrer l'interaction de vue
            ProcedureInteraction.objects.get_or_create(
                user=request.user,
                procedure=instance,
                interaction_type='view'
            )
        else:
            # Pour les utilisateurs anonymes, simplement incrémenter le compteur
            instance.views = F('views') + 1
            instance.save(update_fields=['views'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)'''

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def procedure_interaction(request, procedure_id):
    try:
        procedure = Procedure.objects.get(id=procedure_id)
        interaction_type = request.data.get('type')
        
        if interaction_type not in ['like', 'bookmark']:
            return Response(
                {'error': 'Type d\'interaction non valide'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Créer ou mettre à jour l'interaction
        interaction, created = ProcedureInteraction.objects.get_or_create(
            user=request.user,
            procedure=procedure,
            interaction_type=interaction_type
        )
        
        if not created:
            # Si l'interaction existe déjà, la supprimer (toggle)
            interaction.delete()
            # Décrémenter le compteur
            if interaction_type == 'like':
                procedure.likes = F('likes') - 1
            else:
                procedure.bookmarks = F('bookmarks') - 1
        else:
            # Incrémenter le compteur
            if interaction_type == 'like':
                procedure.likes = F('likes') + 1
            else:
                procedure.bookmarks = F('bookmarks') + 1
        
        procedure.save(update_fields=[f'{interaction_type}s'])
        procedure.refresh_from_db()
        
        return Response({
            'likes': procedure.likes,
            'bookmarks': procedure.bookmarks,
            'user_has_liked': ProcedureInteraction.objects.filter(
                user=request.user, 
                procedure=procedure, 
                interaction_type='like'
            ).exists(),
            'user_has_bookmarked': ProcedureInteraction.objects.filter(
                user=request.user, 
                procedure=procedure, 
                interaction_type='bookmark'
            ).exists()
        })
        
    except Procedure.DoesNotExist:
        return Response(
            {'error': 'Procédure non trouvée'}, 
            status=status.HTTP_404_NOT_FOUND
        )








'''@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    # Marquer toutes les notifications de l'utilisateur comme lues
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({"message": "Toutes les notifications ont été marquées comme lues"}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    # Marquer toutes les notifications de l'utilisateur comme lues
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({"message": "Toutes les notifications ont été marquées comme lues"}, status=status.HTTP_200_OK)


class NotificationListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)'''
        

class NotificationListView(generics.ListAPIView):
    """Liste toutes les notifications de l'utilisateur connecté"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

class UnreadNotificationListView(generics.ListAPIView):
    """Liste seulement les notifications non lues"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user, 
            is_read=False
        ).order_by('-created_at')

class NotificationDetailView(generics.RetrieveUpdateAPIView):
    """Détail d'une notification et marquer comme lue"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        """Marquer une notification comme lue"""
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, pk):
    """Marquer une notification spécifique comme lue"""
    try:
        notification = Notification.objects.get(pk=pk, user=request.user)
        notification.is_read = True
        notification.save()
        return Response({"message": "Notification marquée comme lue"}, status=status.HTTP_200_OK)
    except Notification.DoesNotExist:
        return Response({"error": "Notification non trouvée"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """Marquer toutes les notifications comme lues"""
    updated_count = Notification.objects.filter(
        user=request.user, 
        is_read=False
    ).update(is_read=True)
    
    return Response({
        "message": f"{updated_count} notifications marquées comme lues"
    }, status=status.HTTP_200_OK)

class NotificationStatsView(generics.RetrieveAPIView):
    """Statistiques des notifications"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        total = Notification.objects.filter(user=request.user).count()
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        
        return Response({
            "total_notifications": total,
            "unread_notifications": unread
        })
    

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ClientCreateSerializer
        return ClientSerializer

class TechnicianViewSet(viewsets.ModelViewSet):
    queryset = Technician.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TechnicianCreateSerializer
        return TechnicianSerializer


    
class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TicketCreateSerializer
        return TicketSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def get_queryset(self):
        user = self.request.user
        # si admin via champ userType
        if getattr(user, 'userType', 'admin') == 'admin' or user.is_staff:
            return Ticket.objects.all()
        
        # client
        try:
            client = Client.objects.get(user=user)
            return Ticket.objects.filter(client=client)
        except Client.DoesNotExist:
            pass
        
        # technician
        try:
            technician = Technician.objects.get(user=user)
            return Ticket.objects.filter(technician=technician)
        except Technician.DoesNotExist:
            pass
        
        return Ticket.objects.none()

    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        ticket = self.get_object()
        technician_id = request.data.get('technician_id')
        
        try:
            technician = Technician.objects.get(id=technician_id)
            ticket.technician = technician
            ticket.status = 'in_progress'
            ticket.save()
            return Response({'status': 'technician assigned'})
        except Technician.DoesNotExist:
            return Response({'error': 'Technician not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        ticket = self.get_object()
        ticket.status = 'closed'
        ticket.save()
        return Response({'status': 'ticket closed'})






#custom 404

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def active_technicians_stats(request):
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Pour le mois précédent
    if start_of_month.month == 1:
        start_last_month = start_of_month.replace(year=start_of_month.year - 1, month=12)
    else:
        start_last_month = start_of_month.replace(month=start_of_month.month - 1)
    end_last_month = start_of_month - timezone.timedelta(seconds=1)

    # Technicians actifs ce mois (tickets ouverts ou en cours)
    active_this_month = Technician.objects.filter(
        tickets__status__in=['open', 'in_progress'],
        tickets__created_at__gte=start_of_month
    ).distinct().count()

    # Technicians actifs le mois dernier
    active_last_month = Technician.objects.filter(
        tickets__status__in=['open', 'in_progress'],
        tickets__created_at__gte=start_last_month,
        tickets__created_at__lte=end_last_month
    ).distinct().count()

    # Calcul de la variation en %
    if active_last_month == 0:
        change_vs_last_month = None
    else:
        change_vs_last_month = ((active_this_month - active_last_month) / active_last_month) * 100

    return Response({
        "active_technicians": active_this_month,
        "change_vs_last_month": round(change_vs_last_month, 2) if change_vs_last_month is not None else None
    })
    


