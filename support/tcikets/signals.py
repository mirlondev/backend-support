# signals.py
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import Ticket, Notification
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

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