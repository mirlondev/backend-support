from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


# ========================
# Custom User
# ========================
class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('technician', 'Technician'),
        ('client', 'Client'),
    )

    userType = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='client')
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)

    def __str__(self):
        return self.username


# ========================
# Client
# ========================
class Client(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="client_profile")
    phone = models.CharField(max_length=20)
    company = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.company}"


# ========================
# Technician
# ========================
class Technician(models.Model):
    SPECIALTY_CHOICES = [
        ('hardware', 'Matériel'),
        ('software', 'Logiciel'),
        ('network', 'Réseau'),
        ('security', 'Sécurité'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="technician_profile")
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES)
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_specialty_display()}"


# ========================
# Ticket
# ========================
class Ticket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Ouvert'),
        ('in_progress', 'En cours'),
        ('closed', 'Clôturé'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Faible'),
        ('medium', 'Moyenne'),
        ('high', 'Élevée'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='tickets')
    technician = models.ForeignKey(Technician, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"


# ========================
# Ticket Images
# ========================
class TicketImage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='ticket_images/', blank=True, null=True)

    def __str__(self):
        return f"Image for {self.ticket.title}"


# ========================
# Interventions
# ========================
class Intervention(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='interventions')
    report = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Intervention for {self.ticket.title} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
