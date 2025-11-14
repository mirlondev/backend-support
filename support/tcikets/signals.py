# signals.py
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import Ticket, Notification, Client, Technician
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.conf import settings
from django.contrib.auth import get_user_model
from support.utils.whatsapp_service import WhatsAppService
from django.db.models import Q


from support.utils.callmebot import send_whatsapp_free
import os

User = get_user_model()
CMB_KEY = os.getenv("CALLMEBOT_APIKEY")   # à ajouter dans .env

@receiver(post_save, sender=Ticket)
def notify_admins_callmebot(sender, instance, created, **kwargs):
    if not created or not CMB_KEY:
        return

    admins = User.objects.filter(
        Q(userType='admin') | Q(is_staff=True)
    ).exclude(phone__isnull=True).exclude(phone='')

    msg = (
        f"🔔 *Nouveau ticket* {instance.code}\n"
        f"Titre : {instance.title}\n"
        f"Client : {instance.client.user.get_full_name()}\n"
        f"https://ton-site.com/admin/ticket/{instance.id}/change/"
    )[:500]  # limite 500 car

    for admin in admins:
        send_whatsapp_free(admin.phone, msg, CMB_KEY)

@receiver(user_logged_in)
def create_login_notifications(sender, request, user, **kwargs):
    if user.userType == 'admin':
        pending_tickets = Ticket.objects.filter(status='open').count()
        Notification.objects.create(
            user=user,
            title="Tickets en attente",
            message=f"{pending_tickets} tickets nécessitent votre attention",
        )
    
    elif user.userType == 'client':
        client_tickets = Ticket.objects.filter(
            client__user=user, 
            status='in_progress'
        )
        for ticket in client_tickets:
            Notification.objects.create(
                user=user,
                title="Ticket en cours",
                message=f"Votre ticket #{ticket.code} est en cours de traitement",
                ticket=ticket
            )
    
    elif user.userType == 'technician':
        technician_tickets = Ticket.objects.filter(
            technician__user=user,
            status='in_progress'
        )
        for ticket in technician_tickets:
            Notification.objects.create(
                user=user,
                title="Ticket assigné",
                message=f"Le ticket #{ticket.code} vous a été assigné",
                ticket=ticket
            )
            

User = get_user_model()

@receiver(post_save, sender=Ticket)
def handle_ticket_notifications(sender, instance, created, **kwargs):
    """
    Crée des notifications automatiques pour les tickets
    """
    if created:
        # Notification pour les admins lorsqu'un ticket est créé
        admins = User.objects.filter(userType='admin', is_active=True)
        for admin in admins:
            Notification.objects.create(
                user=admin,
                title="Nouveau ticket créé",
                message=f"Le ticket '{instance.title}' a été créé par {instance.client.user.get_full_name()}.",
                ticket=instance,
                is_read=False
            )
    
    # Vérifier si le technicien a été assigné ou modifié
    if instance.technician and instance.technician.user:
        # Vérifier si c'est une nouvelle assignation
        if kwargs.get('update_fields') is None or 'technician' in kwargs.get('update_fields', []):
            # Notification pour le technicien assigné
            Notification.objects.create(
                user=instance.technician.user,
                title="Ticket assigné",
                message=f"Le ticket '{instance.title}' vous a été assigné. Priorité: {instance.get_priority_display()}",
                ticket=instance,
                is_read=False
            )
            
            
# models.py  (ou un fichier signals.py importé dans ready())



User = settings.AUTH_USER_MODEL   # ou from .models import User
@receiver(pre_save, sender=User)
def set_user_type(sender, instance, **kwargs):
    """Affecte automatiquement userType pour les nouveaux super-utilisateurs."""
    if instance.pk is None and instance.is_superuser:
        instance.userType = 'admin'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crée le profil Client ou Technician après la création de l'utilisateur."""
    if not created:
        return

    with transaction.atomic():
        if instance.userType == 'client':
            Client.objects.get_or_create(user=instance)
        elif instance.userType == 'technician':
            Technician.objects.get_or_create(user=instance)

@receiver(pre_save, sender=User)
def force_admin_usertype(sender, instance, **kwargs):
    if instance.is_superuser:
        instance.userType = 'admin'
        


User = get_user_model()
whatsapp = WhatsAppService()

@receiver(post_save, sender=Ticket)
def notify_admins_on_ticket_creation(sender, instance, created, **kwargs):
    if not created:
        return

    admins = User.objects.filter(
        Q(userType='admin') | Q(is_staff=True)
    ).exclude(phone__isnull=True).exclude(phone='')

    msg = (
        f"🔔 Nouveau ticket *{instance.code}*\n"
        f"Titre : {instance.title}\n"
        f"Client : {instance.client.user.get_full_name()}"
    )

    for admin in admins:
        whatsapp.send_message(admin.phone, msg)