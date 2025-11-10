from rest_framework import serializers
from .models import Client, Technician, Ticket, Intervention,ProcedureTag, TicketImage,TechnicianRating,ClientRating, Message,ProcedureTag, ProcedureImage, ProcedureAttachment
from django.contrib.auth import get_user_model
import uuid
from .models import Procedure, Notification
from django.utils import timezone
from django.utils.timesince import timesince
User = get_user_model()


from .models import Procedure, ProcedureImage

class ProcedureTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcedureTag
        fields = ['id', 'name', 'slug']
        read_only_fields = ['slug']

class ProcedureImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ProcedureImage
        fields = [
            'id', 'procedure', 'image', 'image_url', 
            'caption', 'alt_text', 'uploaded_at'
        ]
        read_only_fields = ['uploaded_at']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

class ProcedureAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    is_video = serializers.SerializerMethodField()
    
    class Meta:
        model = ProcedureAttachment
        fields = [
            'id', 'procedure', 'file', 'file_url', 'download_url',
            'name', 'file_type', 'file_size', 'uploaded_at', 'is_video'
        ]
        read_only_fields = ['uploaded_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
    
    def get_download_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/procedures/media/attachment/{obj.id}/')
        return None
    
    def get_is_video(self, obj):
        return obj.file_type.startswith('video/') if obj.file_type else False

'''class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'userType', 'avatar', 'avatar_url', 'bio'
        ]
        read_only_fields = ['id', 'userType']

    def get_avatar_url(self, obj):
        request = self.context.get('request')
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None'''


class UserSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name',
                  'email', 'userType', 'profile_image','bio','avatar_url']

    def get_userType(self, obj):
        if hasattr(obj, 'client'):
            return "client"
        elif hasattr(obj, 'technician'):
            return "technician"
        elif obj.is_superuser:
            return "admin"
        return "unknown"
    
    def get_avatar_url(self, obj):
        request = self.context.get('request')
        if obj.profile_image and request:
            return request.build_absolute_uri(obj.profile_image.url)
        return None

class ProcedureRelatedSerializer(serializers.ModelSerializer):
    images = ProcedureImageSerializer(many=True, read_only=True)
    class Meta:
        model = Procedure
        fields = ['id', 'title', 'images','category', 'views', 'reading_time',  'description']
        
        
class ProcedureSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    tags = ProcedureTagSerializer(many=True, read_only=True)
    related_procedures = ProcedureRelatedSerializer(many=True, read_only=True)
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=50),
        write_only=True,
        required=False
    )
    images = ProcedureImageSerializer(many=True, read_only=True)
    attachments = ProcedureAttachmentSerializer(many=True, read_only=True)
    images_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    content_preview = serializers.SerializerMethodField()
    reading_time = serializers.SerializerMethodField()
    
    class Meta:
        model = Procedure
        fields = '__all__'
        read_only_fields = [
            'id', 'author', 'created_at', 'updated_at', 'views', 
            'likes', 'bookmarks'
        ]

    def get_content_preview(self, obj):
        """Generate a plain text preview of the content"""
        if not obj.content:
            return ""
        
        # Remove HTML tags for preview
        import re
        clean = re.compile('<.*?>')
        plain_text = re.sub(clean, '', obj.content)
        
        # Return first 200 characters
        return plain_text[:200] + "..." if len(plain_text) > 200 else plain_text
    
    def get_reading_time(self, obj):
        """Calculate estimated reading time"""
        if not obj.content:
            return "0 min"
        
        # Remove HTML tags
        import re
        clean = re.compile('<.*?>')
        plain_text = re.sub(clean, '', obj.content)
        
        # Calculate reading time (average 200 words per minute)
        word_count = len(plain_text.split())
        reading_time = max(1, round(word_count / 200))
        
        return f"{reading_time} min"

    def create(self, validated_data):
        tag_names = validated_data.pop('tag_names', [])
        images_ids = validated_data.pop('images_ids', [])
        
        procedure = Procedure.objects.create(**validated_data)
        
        # Handle tags
        for tag_name in tag_names:
            tag_name = tag_name.strip()
            if tag_name:
                tag, created = ProcedureTag.objects.get_or_create(
                    name=tag_name,
                    defaults={'slug': self._generate_slug(tag_name)}
                )
                procedure.tags.add(tag)
        
        # Handle images
        for image_id in images_ids:
            try:
                image = ProcedureImage.objects.get(id=image_id, procedure__isnull=True)
                image.procedure = procedure
                image.save()
            except ProcedureImage.DoesNotExist:
                continue
        
        return procedure

    def update(self, instance, validated_data):
        tag_names = validated_data.pop('tag_names', None)
        images_ids = validated_data.pop('images_ids', None)
        
        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Handle tags if provided
        if tag_names is not None:
            instance.tags.clear()
            for tag_name in tag_names:
                tag_name = tag_name.strip()
                if tag_name:
                    tag, created = ProcedureTag.objects.get_or_create(
                        name=tag_name,
                        defaults={'slug': self._generate_slug(tag_name)}
                    )
                    instance.tags.add(tag)
        
        # Handle images if provided
        if images_ids is not None:
            for image_id in images_ids:
                try:
                    image = ProcedureImage.objects.get(id=image_id)
                    if image.procedure is None or image.procedure == instance:
                        image.procedure = instance
                        image.save()
                except ProcedureImage.DoesNotExist:
                    continue
        
        return instance
    
    def _generate_slug(self, name):
        """Generate a unique slug for a tag"""
        from django.utils.text import slugify
        slug = slugify(name)
        original_slug = slug
        counter = 1
        
        while ProcedureTag.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        return slug
'''class NotificationSerializer(serializers.ModelSerializer):
    ticket_code = serializers.CharField(source='ticket.code', read_only=True, allow_null=True)
    ticket_title = serializers.CharField(source='ticket.title', read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'ticket', 'ticket_code', 'ticket_title', 'is_read', 'created_at']'''
        
class TicketNotificationSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour les tickets dans les notifications"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    
    class Meta:
        model = Ticket
        fields = ['id', 'code', 'title', 'status', 'status_display', 'priority', 'priority_display', 'created_at']

class NotificationSerializer(serializers.ModelSerializer):
    """Serializer complet pour les notifications"""
    ticket_details = TicketNotificationSerializer(source='ticket', read_only=True)
    time_since = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'ticket', 'ticket_details', 
            'is_read', 'created_at', 'time_since'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_time_since(self, obj):
        return timesince(obj.created_at, timezone.now())


class UserUpdateSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name',
                  'email', 'userType', 'profile_image']

    def get_userType(self, obj):
        if hasattr(obj, 'client'):
            return "client"
        elif hasattr(obj, 'technician'):
            return "technician"
        elif obj.is_superuser:
            return "admin"
        return "unknown"




class ClientSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = UserSerializer()

    average_rating = serializers.SerializerMethodField()
    total_ratings = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = ['id', 'user', 'company', 'phone', 'created_at', 'average_rating', 'total_ratings']
    
    def get_average_rating(self, obj):
        ratings = obj.ratings.all()
        if ratings:
            return sum([r.rating for r in ratings]) / len(ratings)
        return 0
    
    def get_total_ratings(self, obj):
        return obj.ratings.count()






class TechnicianSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = UserSerializer()

    average_rating = serializers.SerializerMethodField()
    total_ratings = serializers.SerializerMethodField()
    
    class Meta:
        model = Technician
        fields = ['id', 'user', 'specialty', 'phone', 'created_at', 'average_rating', 'total_ratings']
    
    def get_average_rating(self, obj):
        ratings = obj.ratings.all()
        if ratings:
            return sum([r.rating for r in ratings]) / len(ratings)
        return 0
    
    def get_total_ratings(self, obj):
        return obj.ratings.count()



class ClientCreateSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)

    class Meta:
        model = Client
        fields = ['id', 'username', 'password', 'first_name',
                  'last_name', 'email', 'phone', 'company']

    def create(self, validated_data):
        user_data = {
            'username': validated_data.pop('username'),
            'password': validated_data.pop('password'),
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'email': validated_data.pop('email'),
            'userType': 'client',  # Ajoutez cette ligne
        }
        user = User.objects.create_user(**user_data)
        client = Client.objects.create(user=user, **validated_data)
        return client
    
    
class TechnicianCreateSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)

    class Meta:
        model = Technician
        fields = ['id', 'username', 'password', 'first_name',
                  'last_name', 'email', 'phone', 'specialty']

    def create(self, validated_data):
        user_data = {
            'username': validated_data.pop('username'),
            'password': validated_data.pop('password'),
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'email': validated_data.pop('email'),
            'userType': 'technician',  # Ajoutez cette ligne
        }
        user = User.objects.create_user(**user_data)
        technician = Technician.objects.create(user=user, **validated_data)
        return technician


class TicketImageSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = TicketImage
        fields = ['id', 'image', 'image_url']
    
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


class MessageSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_type = serializers.SerializerMethodField()
    is_own_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'ticket', 'user', 'user_name', 'user_type', 
            'content', 'image', 'timestamp', 'is_whatsapp', 
            'whatsapp_status', 'whatsapp_sid', 'is_own_message'
        ]
        read_only_fields = ['id', 'timestamp', 'user']
    
    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    
    def get_user_type(self, obj):
        return obj.user.userType
    
    def get_is_own_message(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.user == request.user
        return False
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Ajouter l'URL complète de l'image si elle existe
        if instance.image and hasattr(instance.image, 'url'):
            request = self.context.get('request')
            if request:
                representation['image_url'] = request.build_absolute_uri(instance.image.url)
            else:
                representation['image_url'] = instance.image.url
        
        return representation

class TicketSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    client = ClientSerializer(read_only=True)
    technician = TechnicianSerializer(read_only=True)
    images = TicketImageSerializer(many=True, read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    problem_start_date = serializers.DateTimeField(required=False, allow_null=True)

    
    class Meta:
        model = Ticket
        fields = '__all__'
        
   
    


class TicketCreateSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    technician_id = serializers.UUIDField(required=False, allow_null=True)
    material_name = serializers.CharField(required=False, allow_blank=True)
    problem_start_date = serializers.DateTimeField(required=False, allow_null=True)
    problem_type = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(default="open")  # si tu veux un default

    class Meta:
        model = Ticket
        fields = ['id', 'title', 'description', 'priority', 'status',
                  'technician_id', 'material_name', 'problem_start_date',
                  'problem_type', 'images', 'attachments']
        
    def create(self, validated_data):
        request = self.context['request']
        images_data = validated_data.pop('images', [])
        attachments_data = validated_data.pop('attachments', [])

        user = request.user

        # cas client
        client = Client.objects.filter(user=user).first()
        if client:
            validated_data['client'] = client
        elif user.is_superuser:
            client_id = request.data.get('client_id')
            if not client_id:
                raise serializers.ValidationError("L'admin doit spécifier un client")
            validated_data['client'] = Client.objects.get(id=client_id)
        else:
            raise serializers.ValidationError("Utilisateur non autorisé à créer un ticket")

        # créer le ticket
        ticket = Ticket.objects.create(**validated_data)

        for img in images_data:
            TicketImage.objects.create(ticket=ticket, image=img)

        for att in attachments_data:
            TicketAttachment.objects.create(ticket=ticket, file=att)

        return ticket

    
    def update(self, instance, validated_data):
        images = validated_data.pop('images', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if images is not None:
            instance.images.all().delete()
            for image in images:
                TicketImage.objects.create(ticket=instance, image=image)
        return instance


        

# serializers.py
class InterventionSerializer(serializers.ModelSerializer):
    total_time = serializers.SerializerMethodField()
    technician = TechnicianSerializer(read_only=True)  # objet complet
    technician_id = serializers.IntegerField(source='technician.id', read_only=True)  # ID
    ticket_client_id = serializers.IntegerField(source='ticket.client.id', read_only=True)  # ID
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    ticket = TicketSerializer(read_only=True)  # ajoute ça si pas déjà fait

    
    class Meta:
        model = Intervention
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'total_cost')
    
    def get_total_time(self, obj):
        return obj.calculate_total_time()
    
    def validate(self, data):
        if data.get('start_time') and data.get('end_time'):
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError("End time must be after start time")
        return data


class InterventionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intervention
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'total_cost')


class TechnicianRatingSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.user.get_full_name', read_only=True)
    
    class Meta:
        model = TechnicianRating
        fields = ['id', 'technician', 'client', 'client_name', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at']

class ClientRatingSerializer(serializers.ModelSerializer):
    technician_name = serializers.CharField(source='technician.user.get_full_name', read_only=True)
    
    class Meta:
        model = ClientRating
        fields = ['id', 'client', 'technician', 'technician_name', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at']



class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['content', 'image', 'ticket', 'is_whatsapp']
        read_only_fields = ['user', 'timestamp']
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user:
            validated_data['user'] = request.user
        
        return super().create(validated_data)