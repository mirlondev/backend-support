import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import RegexValidator,MinValueValidator,MaxValueValidator
from decimal import Decimal
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
import os
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field
from PIL import Image as PILImage
from io import BytesIO
from django.core.files.base import ContentFile

# Phone validator
phone_regex = RegexValidator(
    regex=r'^\+?242?\d{9,15}$',
    message="Phone number must be entered in the format: '+242999999999'. Up to 15 digits allowed."
)

def user_avatar_path(instance, filename):
    """Generate file path for user avatars"""
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join('avatars', str(instance.id), filename)

def procedure_image_path(instance, filename):
    """Generate file path for procedure images"""
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    if instance.procedure:
        return os.path.join('procedures', str(instance.procedure.id), 'images', filename)
    return os.path.join('procedures', 'temp', 'images', filename)

def procedure_attachment_path(instance, filename):
    """Generate file path for procedure attachments"""
    ext = filename.split('.')[-1]
    safe_filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join('procedures', str(instance.procedure.id), 'attachments', safe_filename)

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(validators=[phone_regex], max_length=13, blank=True, null=True) 

    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('technician', 'Technician'),
        ('client', 'Client'),
    )

    userType = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='client')
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to=user_avatar_path, blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    
    # Additional fields for better user experience
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username
    
    def save(self, *args, **kwargs):
        # Optimize avatar image on save
        if self.avatar:
            self.avatar = self._optimize_avatar()
        super().save(*args, **kwargs)
    
    def _optimize_avatar(self):
        """Optimize avatar image for web use"""
        if not self.avatar:
            return self.avatar
            
        try:
            img = PILImage.open(self.avatar)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Resize to reasonable size for avatars
            img.thumbnail((300, 300), PILImage.Resampling.LANCZOS)
            
            output = BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            
            return ContentFile(output.read(), name=self.avatar.name)
        except Exception:
            return self.avatar

    class Meta:
        swappable = 'AUTH_USER_MODEL'

class ProcedureTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#3B82F6')  # Hex color code
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    @property
    def procedure_count(self):
        return self.procedures.filter(is_active=True, status='published').count()
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Tag de procédure'
        verbose_name_plural = 'Tags de procédure'

class Procedure(models.Model):
    DIFFICULTY_CHOICES = [
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('published', 'Publié'),
        ('archived', 'Archivé'),
    ]
    
    CATEGORY_CHOICES = [
        ('general', 'Général'),
        ('hardware', 'Hardware'),
        ('software', 'Software'),
        ('network', 'Réseau'),
        ('security', 'Sécurité'),
        ('maintenance', 'Maintenance'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField()
    content =CKEditor5Field('Text', config_name='extends') # Utilisé pour le contenu détaillé
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general', db_index=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='intermediate', db_index=True)
    estimated_time = models.CharField(max_length=50)  # Ex: "2-4 hours"
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Métadonnées
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='authored_procedures')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    views = models.PositiveIntegerField(default=0, db_index=True)
    likes = models.PositiveIntegerField(default=0)
    bookmarks = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    
    # SEO and search optimization
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    meta_description = models.CharField(max_length=160, blank=True, help_text="SEO meta description")
    featured = models.BooleanField(default=False, db_index=True)
    
    # Relations
    tags = models.ManyToManyField(ProcedureTag, related_name='procedures', blank=True)
    related_procedures = models.ManyToManyField('self', symmetrical=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        if not self.meta_description and self.description:
            self.meta_description = self.description[:157] + "..."
        super().save(*args, **kwargs)
    
    def _generate_unique_slug(self):
        """Generate a unique slug for the procedure"""
        slug = slugify(self.title)
        original_slug = slug
        counter = 1
        
        while Procedure.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        return slug
    
    @property
    def reading_time(self):
        """Calculate estimated reading time in minutes"""
        if not self.content:
            return 1
        
        # Remove HTML tags and count words
        import re
        clean = re.compile('<.*?>')
        plain_text = re.sub(clean, '', self.content)
        word_count = len(plain_text.split())
        
        # Average reading speed: 200 words per minute
        return max(1, round(word_count / 200))
    
    @property
    def has_media(self):
        """Check if procedure has images or attachments"""
        return self.images.exists() or self.attachments.exists()
    
    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Procédure'
        verbose_name_plural = 'Procédures'
        indexes = [
            models.Index(fields=['status', 'is_active', '-created_at']),
            models.Index(fields=['category', 'difficulty']),
            models.Index(fields=['-views']),
            models.Index(fields=['featured', '-created_at']),
        ]

class ProcedureImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    procedure = models.ForeignKey(Procedure, related_name='images', on_delete=models.CASCADE, null=True, blank=True)
    image = models.ImageField(upload_to=procedure_image_path)
    caption = models.CharField(max_length=200, blank=True, null=True)
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)  # For ordering images
    
    # Image metadata
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)  # Size in bytes
    
    def save(self, *args, **kwargs):
        if self.image:
            # Get image dimensions and file size
            try:
                img = PILImage.open(self.image)
                self.width, self.height = img.size
                self.file_size = self.image.size
            except Exception:
                pass
        
        super().save(*args, **kwargs)
    
    @property
    def image_url(self):
        """Get the full URL for the image"""
        if self.image:
            return self.image.url
        return None
    
    @property
    def formatted_file_size(self):
        """Get human-readable file size"""
        if not self.file_size:
            return "Unknown"
        
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
    
    def __str__(self):
        procedure_title = self.procedure.title if self.procedure else "Temp upload"
        return f"Image for {procedure_title}"
    
    class Meta:
        ordering = ['order', 'uploaded_at']
        verbose_name = 'Image de procédure'
        verbose_name_plural = 'Images de procédure'

class ProcedureAttachment(models.Model):
    ATTACHMENT_TYPES = [
        ('document', 'Document'),
        ('video', 'Vidéo'),
        ('archive', 'Archive'),
        ('other', 'Autre'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    procedure = models.ForeignKey(Procedure, related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField(upload_to=procedure_attachment_path)
    name = models.CharField(max_length=200)
    file_type = models.CharField(max_length=50)
    file_size = models.CharField(max_length=20)
    attachment_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPES, default='other')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    downloads = models.PositiveIntegerField(default=0)
    
    # Additional metadata
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)  # Whether file can be downloaded by anyone
    
    def save(self, *args, **kwargs):
        if not self.attachment_type:
            self.attachment_type = self._determine_attachment_type()
        super().save(*args, **kwargs)
    
    def _determine_attachment_type(self):
        """Automatically determine attachment type based on file type"""
        if not self.file_type:
            return 'other'
        
        if self.file_type.startswith('video/'):
            return 'video'
        elif self.file_type in ['application/pdf', 'application/msword', 
                               'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                               'text/plain']:
            return 'document'
        elif self.file_type in ['application/zip', 'application/x-rar-compressed']:
            return 'archive'
        else:
            return 'other'
    
    @property
    def file_url(self):
        """Get the full URL for the file"""
        if self.file:
            return self.file.url
        return None
    
    @property
    def is_video(self):
        """Check if attachment is a video"""
        return self.attachment_type == 'video' or (self.file_type and self.file_type.startswith('video/'))
    
    @property
    def icon_class(self):
        """Get CSS icon class based on file type"""
        if self.is_video:
            return 'video'
        elif self.attachment_type == 'document':
            return 'file-text'
        elif self.attachment_type == 'archive':
            return 'archive'
        else:
            return 'file'
    
    def increment_downloads(self):
        """Increment download counter"""
        self.downloads += 1
        self.save(update_fields=['downloads'])
    
    def __str__(self):
        return f"{self.name} for {self.procedure.title}"
    
    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Pièce jointe de procédure'
        verbose_name_plural = 'Pièces jointes de procédure'

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

class ProcedureVersion(models.Model):
    """Track changes to procedures for version control"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    procedure = models.ForeignKey(Procedure, related_name='versions', on_delete=models.CASCADE)
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField()
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    change_summary = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-version_number']
        unique_together = ['procedure', 'version_number']
        verbose_name = 'Version de procédure'
        verbose_name_plural = 'Versions de procédure'

# Signal handlers for automatic operations
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

@receiver(post_save, sender=Procedure)
def create_procedure_version(sender, instance, created, **kwargs):
    """Create a version record when procedure is saved"""
    if not created:  # Only for updates, not initial creation
        try:
            last_version = instance.versions.first()
            version_number = (last_version.version_number + 1) if last_version else 1
            
            ProcedureVersion.objects.create(
                procedure=instance,
                version_number=version_number,
                title=instance.title,
                description=instance.description,
                content=instance.content,
                created_by=instance.author,
            )
        except Exception:
            pass  # Don't fail procedure save if version creation fails

@receiver(pre_delete, sender=ProcedureImage)
def delete_image_file(sender, instance, **kwargs):
    """Delete image file when ProcedureImage is deleted"""
    if instance.image:
        try:
            instance.image.delete(save=False)
        except Exception:
            pass

@receiver(pre_delete, sender=ProcedureAttachment)
def delete_attachment_file(sender, instance, **kwargs):
    """Delete attachment file when ProcedureAttachment is deleted"""
    if instance.file:
        try:
            instance.file.delete(save=False)
        except Exception:
            pass

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
        
# ========================
# Client with UUID
# ========================
class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="client_profile")
    

    phone = models.CharField(validators=[phone_regex], max_length=13, blank=True, null=True) 
    
    company = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def average_rating(self):
        # Use the reverse relation from ClientRating
        from .models import ClientRating  # Import here to avoid circular imports
        ratings = ClientRating.objects.filter(client=self)
        if ratings.exists():
            return sum([r.rating for r in ratings]) / ratings.count()
        return 0
    
    def total_ratings(self):
        from .models import ClientRating  # Import here to avoid circular imports
        return ClientRating.objects.filter(client=self).count()

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.company}"
    
#=================
# Technician with UUID
# ========================
class Technician(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    SPECIALTY_CHOICES = [
        ('hardware', 'Matériel'),
        ('software', 'Logiciel'),
        ('network', 'Réseau'),
        ('security', 'Sécurité'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="technician_profile")
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES)

    phone = models.CharField(validators=[phone_regex], max_length=13, blank=True, null=True) 
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def average_rating(self):
        # Use the reverse relation from TechnicianRating
        from .models import TechnicianRating  # Import here to avoid circular imports
        ratings = TechnicianRating.objects.filter(technician=self)
        if ratings.exists():
            return sum([r.rating for r in ratings]) / ratings.count()
        return 0
    
    def total_ratings(self):
        from .models import TechnicianRating  # Import here to avoid circular imports
        return TechnicianRating.objects.filter(technician=self).count()
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_specialty_display()}"


# ========================
# Ticket with UUID
# ========================
class Ticket(models.Model):    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = [
        ("open", "Ouvert"),
        ("in_progress", "En cours"),
        ("resolved", "Resolu"),
        ("closed", "Fermee"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]
    
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
    
    # Relations
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='tickets')
    technician = models.ForeignKey(Technician, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
   #created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_tickets')

    def __str__(self):
        return f"{self.title} ({self.status})"
    
    def save(self, *args, **kwargs):
        if not self.code:
            year = timezone.now().year
            # Trouver le dernier ticket créé cette année
            last_ticket = Ticket.objects.filter(code__endswith=f"-{year}").order_by('created_at').last()
            if last_ticket:
                # Extraire le numéro et incrémenter
                last_number = int(last_ticket.code.split('-')[1][1:])  # 'N001' -> 1
                new_number = last_number + 1
            else:
                new_number = 1
            self.code = f"TKT-N{new_number:03d}-{year}"
        super().save(*args, **kwargs)
        
        
        
# ========================
# Ticket Images with UUID
# ========================
class TicketImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='ticket_images/', blank=True, null=True)

    def __str__(self):
        return f"Image for {self.ticket.title}"


# ========================
# Interventions with UUID
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
        ordering = ['-intervention_date', '-created_at']
        verbose_name = "Intervention"
        verbose_name_plural = "Interventions"
    
    

    def __str__(self):
        return f"Intervention for {self.ticket.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    

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

class InterventionImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='intervention_images/')
    caption = models.CharField(max_length=200, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Image for {self.intervention.ticket.title}"

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
    

class PendingConfirmation(models.Model):
    """
    Stocke les confirmations en attente de réponse du client
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intervention = models.ForeignKey(Intervention, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
# =======