import os, re, uuid, mimetypes, logging
from io import BytesIO
from PIL import Image as PILImage
from io import BytesIO
from django.core.files.base import ContentFile
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field
from cloudinary import CloudinaryImage
from decimal import Decimal
# ------------------------------------------------------------------
# VALIDATEURS
# ------------------------------------------------------------------
phone_regex = RegexValidator(
    regex=r'^\+?242?\d{8,15}$',
    message="Téléphone au format +242055506688 (8-15 chiffres)."
)

# ------------------------------------------------------------------
# PATHS CLOUDINARY
# ------------------------------------------------------------------
def user_avatar_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('avatars', str(instance.id), filename)

def procedure_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    if instance.procedure:
        return os.path.join('procedures', str(instance.procedure.id), 'images', filename)
    return os.path.join('procedures', 'temp', 'images', filename)

def procedure_attachment_path(instance, filename):
    ext = filename.split('.')[-1]
    safe_filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('procedures', str(instance.procedure.id), 'attachments', safe_filename)

def intervention_image_path(instance, filename):
    """Chemin Cloudinary : interventions/<intervention_id>/images/<uuid>.<ext>"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('interventions', str(instance.intervention.id), 'images', filename)
# ------------------------------------------------------------------
# USER (avatar Cloudinary + userType)
# ------------------------------------------------------------------
class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(validators=[phone_regex], max_length=13, blank=True, null=True)
    userType = models.CharField(
        max_length=20,
        choices=(('admin', 'Admin'), ('technician', 'Technician'), ('client', 'Client')),
        default='client'
    )
    avatar = models.ImageField(upload_to=user_avatar_path, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    email = models.EmailField(('email address'), unique=True)   # <-- add this


    # ---------- Cloudinary helpers ----------
    def _get_cloudinary_public_id(self):
        if not self.avatar:
            return None
        path = str(self.avatar)
        return re.sub(r'\.[^.]+$', '', path)

    def _get_file_extension(self):
        if self.avatar:
            name = os.path.basename(str(self.avatar))
            _, ext = os.path.splitext(name)
            return ext.lower() if ext else '.jpg'
        return '.jpg'

    def get_avatar_url(self, **transformations):
        if not self.avatar:
            return None
        public_id = self._get_cloudinary_public_id()
        ext = self._get_file_extension()
        try:
            return CloudinaryImage(f"{public_id}{ext}").build_url(**transformations)
        except Exception as e:
            logging.getLogger(__name__).error(f"Cloudinary avatar URL error: {e}")
            return self.avatar.url if hasattr(self.avatar, 'url') else None

    @property
    def avatar_url(self):
        return self.get_avatar_url()

    @property
    def avatar_thumbnail(self):
        return self.get_avatar_url(
            width=150, height=150, crop='thumb', gravity='face',
            quality='auto', fetch_format='auto'
        )

    def save(self, *args, **kwargs):
        # Optimisation simple
        if self.avatar:
            try:
                img = PILImage.open(self.avatar)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                img.thumbnail((300, 300), PILImage.Resampling.LANCZOS)
                output = BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                output.seek(0)
                self.avatar = ContentFile(output.read(), name=self.avatar.name)
            except Exception:
                pass
        super().save(*args, **kwargs)

    class Meta:
        swappable = 'AUTH_USER_MODEL'

# ------------------------------------------------------------------
# CLIENT (sans phone/bio → on les lit via User)
# ------------------------------------------------------------------
class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='client_profile')
    company = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def average_rating(self):
        from .models import ClientRating
        ratings = ClientRating.objects.filter(client=self)
        return (sum(r.rating for r in ratings) / ratings.count()) if ratings.exists() else 0

    def total_ratings(self):
        from .models import ClientRating
        return ClientRating.objects.filter(client=self).count()

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.company}"

# ------------------------------------------------------------------
# TECHNICIEN (sans phone/bio → on les lit via User)
# ------------------------------------------------------------------
class Technician(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='technician_profile')
    specialty = models.CharField(
        max_length=20,
        choices=[('hardware', 'Matériel'), ('software', 'Logiciel'),
                 ('network', 'Réseau'), ('security', 'Sécurité')]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def average_rating(self):
        from .models import TechnicianRating
        ratings = TechnicianRating.objects.filter(technician=self)
        return (sum(r.rating for r in ratings) / ratings.count()) if ratings.exists() else 0

    def total_ratings(self):
        from .models import TechnicianRating
        return TechnicianRating.objects.filter(technician=self).count()

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_specialty_display()}"

# ------------------------------------------------------------------
# SIGNAL : création automatique des profils
# ------------------------------------------------------------------
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crée le profil Client ou Technician dès qu'un User est créé avec le bon userType."""
    if created:
        if instance.userType == 'client':
            Client.objects.get_or_create(user=instance)
        elif instance.userType == 'technician':
            Technician.objects.get_or_create(user=instance)

# ------------------------------------------------------------------
# PROCEDURE (tags, images, etc.)
# ------------------------------------------------------------------
class ProcedureTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#3B82F6')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Procedure(models.Model):
    DIFFICULTY_CHOICES = [('beginner', 'Débutant'), ('intermediate', 'Intermédiaire'), ('advanced', 'Avancé')]
    STATUS_CHOICES = [('draft', 'Brouillon'), ('published', 'Publié'), ('archived', 'Archivé')]
    CATEGORY_CHOICES = [('general', 'Général'), ('hardware', 'Hardware'), ('software', 'Software'),
                        ('network', 'Réseau'), ('security', 'Sécurité'), ('maintenance', 'Maintenance')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField()
    content = CKEditor5Field('Text', config_name='extends')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general', db_index=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='intermediate', db_index=True)
    estimated_time = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True, db_index=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='authored_procedures')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    views = models.PositiveIntegerField(default=0, db_index=True)
    likes = models.PositiveIntegerField(default=0)
    bookmarks = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    featured = models.BooleanField(default=False, db_index=True)
    tags = models.ManyToManyField(ProcedureTag, related_name='procedures', blank=True)
    related_procedures = models.ManyToManyField('self', symmetrical=True, blank=True)
    

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        if not self.meta_description and self.description:
            self.meta_description = self.description[:157] + "..."
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        slug = slugify(self.title)
        original_slug = slug
        counter = 1
        while Procedure.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
        return slug

    @property
    def reading_time(self):
        import re
        if not self.content:
            return 1
        plain_text = re.sub(r'<.*?>', '', self.content)
        return max(1, round(len(plain_text.split()) / 200))

    def __str__(self):
        return self.title

    class Meta:
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['author', 'status']),
            models.Index(fields=['-views']),
            models.Index(fields=['featured', 'status']),
        ]
        ordering = ['-created_at']

class ProcedureImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    procedure = models.ForeignKey(Procedure, related_name='images', on_delete=models.CASCADE, null=True, blank=True)
    image = models.ImageField(upload_to=procedure_image_path, max_length=500)
    caption = models.CharField(max_length=200, blank=True, null=True)
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    file_extension = models.CharField(max_length=10, blank=True, default='')

    # ---------- Métadonnées + Cloudinary ----------
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if self.image and is_new:
            try:
                name = getattr(self.image, 'name', '')
                _, ext = os.path.splitext(name)
                self.file_extension = ext.lower() if ext else '.png'
                self.image.seek(0)
                img = PILImage.open(self.image)
                self.width, self.height = img.size
                self.file_size = self.image.size
                self.image.seek(0)
            except Exception as e:
                logging.getLogger(__name__).error(f"ProcedureImage metadata error: {e}")
        super().save(*args, **kwargs)

    def _get_cloudinary_public_id(self):
        if not self.image:
            return None
        path = str(self.image)
        return re.sub(r'\.[^.]+$', '', path)

    def _get_file_extension(self):
        if self.file_extension:
            return self.file_extension if self.file_extension.startswith('.') else f'.{self.file_extension}'
        return '.png'

    def get_image_url(self, **transformations):
        if not self.image:
            return None
        public_id = self._get_cloudinary_public_id()
        ext = self._get_file_extension()
        try:
            return CloudinaryImage(f"{public_id}{ext}").build_url(**transformations)
        except Exception as e:
            logging.getLogger(__name__).error(f"Cloudinary URL error: {e}")
            url = self.image.url
            if not any(url.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                url += ext
            return url

    @property
    def image_url(self):
        return self.get_image_url()

    @property
    def thumbnail_url(self):
        return self.get_image_url(width=150, height=150, crop='fill', gravity='auto', quality='auto', fetch_format='auto')

    @property
    def medium_url(self):
        return self.get_image_url(width=800, crop='limit', quality='auto', fetch_format='auto')

    def __str__(self):
        return f"Image for {self.procedure.title if self.procedure else 'Temp'}"

class ProcedureAttachment(models.Model):
    ATTACHMENT_TYPES = [('document', 'Document'), ('video', 'Vidéo'), ('archive', 'Archive'), ('other', 'Autre')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    procedure = models.ForeignKey(Procedure, related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField(upload_to=procedure_attachment_path, max_length=500)
    name = models.CharField(max_length=200)
    file_type = models.CharField(max_length=50)
    file_size = models.CharField(max_length=20)
    attachment_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPES, default='other')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    downloads = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.attachment_type:
            self.attachment_type = self._determine_attachment_type()
        super().save(*args, **kwargs)

    def _determine_attachment_type(self):
        if self.file_type.startswith('video/'): return 'video'
        if self.file_type in ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/plain']: return 'document'
        if self.file_type in ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed']: return 'archive'
        return 'other'

    @property
    def file_url(self):
        return self.file.url if self.file else None

    @property
    def is_video(self):
        return self.attachment_type == 'video' or (self.file_type and self.file_type.startswith('video/'))

    def __str__(self):
        return f"{self.name} for {self.procedure.title}"

# ------------------------------------------------------------------
# TICKET / INTERVENTION / MESSAGE / NOTATION
# ------------------------------------------------------------------
class Ticket(models.Model):
    STATUS_CHOICES = [("open", "Ouvert"), ("in_progress", "En cours"), ("resolved", "Resolu"), ("closed", "Fermee")]
    PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    material_name = models.CharField(max_length=100, null=True, blank=True)
    problem_start_date = models.DateTimeField(null=True, blank=True)
    problem_type = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    attachments = models.FileField(upload_to="ticket_attachments/", null=True, blank=True)
    tags = models.CharField(max_length=100, blank=True, null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='tickets')
    technician = models.ForeignKey(Technician, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')

    def save(self, *args, **kwargs):
        if not self.code:
            year = timezone.now().year
            last = Ticket.objects.filter(code__endswith=f"-{year}").order_by('created_at').last()
            num = (int(last.code.split('-')[1][1:]) + 1) if last else 1
            self.code = f"TKT-N{num:03d}-{year}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.status})"
    
    class Meta:
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['technician', 'status']),
            models.Index(fields=['-created_at']),
        ]
        ordering = ['-created_at']



'''class Message(models.Model):
    WHATSAPP_STATUS_CHOICES = [('pending', 'En attente'), ('sent', 'Envoyé'), ('delivered', 'Livré'), ('failed', 'Échec'), ('read', 'Lu')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='chat_images/%Y/%m/%d/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    whatsapp_status = models.CharField(max_length=10, choices=WHATSAPP_STATUS_CHOICES, default='pending')
    whatsapp_sid = models.CharField(max_length=50, blank=True, null=True)
    is_whatsapp = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.user}: {self.content[:50] if self.content else 'Image message'}"
'''






# ========================
class ProcedureInteraction(models.Model):
    INTERACTION_TYPES = [
        ('view', 'Vue'),
        ('like', 'Like'),
        ('bookmark', 'Bookmark'),
        ('share', 'Partage'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Additional metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['user', 'procedure', 'interaction_type']
        verbose_name = 'Interaction avec procédure'
        verbose_name_plural = 'Interactions avec procédures'
        indexes = [
            models.Index(fields=['procedure', 'interaction_type']),
            models.Index(fields=['user', 'interaction_type']),
            models.Index(fields=['-created_at']),
        ]

   
        
# ========================
# Ticket Images with UUID
# ========================
class TicketImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='ticket_images/', blank=True, null=True)

    # Métadonnées
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    file_extension = models.CharField(max_length=10, blank=True, default='')

    uploaded_at = models.DateTimeField(auto_now_add=True)

    # ---------- LOGIQUE COMMUNE ----------
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if self.image and is_new:
            try:
                # Extension
                name = getattr(self.image, 'name', '')
                _, ext = os.path.splitext(name)
                self.file_extension = ext.lower() if ext else '.png'

                # Rewind
                self.image.seek(0)
                img = PILImage.open(self.image)
                self.width, self.height = img.size
                self.file_size = self.image.size
                self.image.seek(0)
            except Exception as e:
                logging.getLogger(__name__).error(f"TicketImage metadata error: {e}")
        super().save(*args, **kwargs)

    def _get_cloudinary_public_id(self):
        if not self.image:
            return None
        path = str(self.image)
        return re.sub(r'\.[^.]+$', '', path)

    def _get_file_extension(self):
        if self.file_extension:
            return self.file_extension if self.file_extension.startswith('.') else f'.{self.file_extension}'
        return '.png'

    def get_image_url(self, **transformations):
        if not self.image:
            return None
        public_id = self._get_cloudinary_public_id()
        ext = self._get_file_extension()
        try:
            return CloudinaryImage(f"{public_id}{ext}").build_url(**transformations)
        except Exception as e:
            logging.getLogger(__name__).error(f"Cloudinary URL error: {e}")
            return self.image.url

    # ---------- PROPRIÉTÉS RAPIDES ----------
    @property
    def image_url(self):
        return self.get_image_url()

    @property
    def thumbnail_url(self):
        return self.get_image_url(
            width=150,
            height=150,
            crop='fill',
            gravity='auto',
            quality='auto',
            fetch_format='auto'
        )

    @property
    def medium_url(self):
        return self.get_image_url(
            width=800,
            crop='limit',
            quality='auto',
            fetch_format='auto'
        )

    def __str__(self):
        return f"Image for {self.ticket.title}"
# ========================

class Intervention(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='interventions')
    technician = models.ForeignKey(Technician, on_delete=models.SET_NULL, null=True, blank=True, related_name='interventions')
    code = models.CharField(max_length=20, unique=True, blank=True, editable=False)  

    # Basic intervention details
    report = models.TextField(verbose_name="Intervention Report")
    intervention_date = models.DateField(verbose_name="Intervention Date", auto_now_add=True)
    start_time = models.TimeField(verbose_name="Start Time", null=True, blank=True)
    end_time = models.TimeField(verbose_name="End Time", null=True, blank=True)
    
    # Financial details
    transport_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Transport Cost"
    )
    additional_costs = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Additional Costs"
    )
    total_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Total Cost"
    )
    
    # Time tracking
    hours_worked = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Hours Worked"
    )
    travel_time = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Travel Time (hours)"
    )
    
    # Materials and resources
    materials_used = models.TextField(blank=True, null=True, verbose_name="Materials Used")
    equipment_used = models.TextField(blank=True, null=True, verbose_name="Equipment Used")
    
    # Status and completion
    INTERVENTION_STATUS = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    status = models.CharField(
        max_length=20, 
        choices=INTERVENTION_STATUS, 
        default='scheduled',
        verbose_name="Intervention Status"
    )
    
    # Verification
    customer_signature = models.TextField(blank=True, null=True, verbose_name="Customer Signature")
    customer_feedback = models.TextField(blank=True, null=True, verbose_name="Customer Feedback")
    customer_rating = models.IntegerField(
        blank=True, 
        null=True, 
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Customer Rating"
    )
    
    # Additional notes
    technician_notes = models.TextField(blank=True, null=True, verbose_name="Technician Notes")
    internal_notes = models.TextField(blank=True, null=True, verbose_name="Internal Notes")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Intervention for {self.ticket.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    

    def save(self, *args, **kwargs):
        self.total_cost = self.transport_cost + self.additional_costs

        if not self.code:
            self.code = f"INT-{uuid.uuid4().hex[:8].upper()}"  # Exemple: INT-1A2B3C4D

        super().save(*args, **kwargs)

    def calculate_total_time(self):
        """Calculate total time spent (work + travel)"""
        return self.hours_worked + self.travel_time
    
    def get_status_color(self):
        """Return color code based on status for UI purposes"""
        status_colors = {
            'scheduled': 'blue',
            'in_progress': 'orange',
            'completed': 'green',
            'cancelled': 'red',
        }
        return status_colors.get(self.status, 'gray')
    
    class Meta:
        indexes = [
            models.Index(fields=['ticket', '-intervention_date']),
            models.Index(fields=['technician', 'status']),
            models.Index(fields=['status', '-intervention_date']),
        ]
        ordering = ['-intervention_date', '-created_at']
    
    

    def __str__(self):
        return f"Intervention for {self.ticket.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    

class InterventionImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=intervention_image_path, max_length=500)
    caption = models.CharField(max_length=200, blank=True, null=True)
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)

    # Métadonnées
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    file_extension = models.CharField(max_length=10, blank=True, default='')

    # ------------------------------------------------------------------
    # Sauvegarde : remplit tailles, poids, extension
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if self.image and is_new:
            try:
                name = getattr(self.image, 'name', '')
                _, ext = os.path.splitext(name)
                self.file_extension = ext.lower() if ext else '.png'

                self.image.seek(0)
                img = PILImage.open(self.image)
                self.width, self.height = img.size
                self.file_size = self.image.size
                self.image.seek(0)
            except Exception as e:
                logging.getLogger(__name__).error(f"InterventionImage metadata error: {e}")
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Helpers Cloudinary
    # ------------------------------------------------------------------
    def _get_cloudinary_public_id(self):
        if not self.image:
            return None
        path = str(self.image)
        return re.sub(r'\.[^.]+$', '', path)

    def _get_file_extension(self):
        if self.file_extension:
            return self.file_extension if self.file_extension.startswith('.') else f'.{self.file_extension}'
        return '.png'

    def get_image_url(self, **transformations):
        if not self.image:
            return None
        public_id = self._get_cloudinary_public_id()
        ext = self._get_file_extension()
        try:
            return CloudinaryImage(f"{public_id}{ext}").build_url(**transformations)
        except Exception as e:
            logging.getLogger(__name__).error(f"Cloudinary URL error: {e}")
            return self.image.url if hasattr(self.image, 'url') else None

    # ------------------------------------------------------------------
    # URLs prêtes à l’emploi
    # ------------------------------------------------------------------
    @property
    def image_url(self):
        return self.get_image_url()

    @property
    def thumbnail_url(self):
        return self.get_image_url(
            width=150, height=150, crop='fill', gravity='auto',
            quality='auto', fetch_format='auto'
        )

    @property
    def medium_url(self):
        return self.get_image_url(
            width=800, crop='limit', quality='auto', fetch_format='auto'
        )

    @property
    def large_url(self):
        return self.get_image_url(
            width=1200, crop='limit', quality='auto', fetch_format='auto'
        )

    @property
    def webp_url(self):
        return self.get_image_url(
            width=800, crop='limit', quality='auto', fetch_format='webp'
        )

    def get_responsive_urls(self):
        """Retourne tous les formats utiles (comme ProcedureImage)"""
        return {
            'thumbnail': self.thumbnail_url,
            'medium': self.medium_url,
            'large': self.large_url,
            'webp': self.webp_url,
        }

    # ------------------------------------------------------------------
    # Représentation string
    # ------------------------------------------------------------------
    def __str__(self):
        return f"Image for {self.intervention.ticket.title if self.intervention else 'Temp'}"

class InterventionMaterial(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name='materials')
    name = models.CharField(max_length=100)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    serial_number = models.CharField(max_length=20, unique=True, blank=True, editable=False)  

    
    def save(self, *args, **kwargs):
        self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} - {self.quantity}"


class InterventionExpense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name='expenses')
    expense_type = models.CharField(max_length=100)  # e.g., transport, materials, etc.
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt = models.FileField(upload_to='expense_receipts/', blank=True, null=True)
    date_incurred = models.DateField()
    
    def __str__(self):
        return f"{self.expense_type} - {self.amount}"
    


# models.py
class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='chat_images/%Y/%m/%d/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    WHATSAPP_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('sent', 'Envoyé'),
        ('delivered', 'Livré'),
        ('failed', 'Échec'),
        ('read', 'Lu'),
    ]
    
    whatsapp_status = models.CharField(
        max_length=10, 
        choices=WHATSAPP_STATUS_CHOICES, 
        default='pending'
    )
    whatsapp_sid = models.CharField(max_length=50, blank=True, null=True)  # SID du message Twilio
    is_whatsapp = models.BooleanField(default=False)  # Si le message a été envoyé via WhatsApp

    class Meta:
        indexes = [
            models.Index(fields=['ticket', 'timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.user}: {self.content[:50] if self.content else 'Image message'}"
    
    
    

class TechnicianRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    technician = models.ForeignKey(Technician, on_delete=models.CASCADE, related_name='ratings')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='given_ratings')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['technician', 'client']  # A client can only rate a technician once

    def __str__(self):
        return f"{self.rating} stars for {self.technician} by {self.client}"

class ClientRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='ratings')
    technician = models.ForeignKey(Technician, on_delete=models.CASCADE, related_name='given_ratings')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['client', 'technician']  # A technician can only rate a client once

    def __str__(self):
        return f"{self.rating} stars for {self.client} by {self.technician}"
    


    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    
class PendingConfirmation(models.Model):
    """
    Stocke les confirmations en attente de réponse du client
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intervention = models.ForeignKey('Intervention', on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)
       