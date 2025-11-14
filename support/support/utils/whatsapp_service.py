# support/utils/whatsapp_service.py
from twilio.rest import Client
from django.conf import settings
from tcikets.models import Message, Ticket, User
import logging

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.whatsapp_number = settings.TWILIO_WHATSAPP_NUMBER

    def send_message(self, to: str, body: str, media_url: str = None):
        """Envoie un message WhatsApp via Twilio"""
        try:
            message = self.client.messages.create(
                from_=f"whatsapp:{self.whatsapp_number}",
                to=f"whatsapp:{to}",
                body=body,
                media_url=[media_url] if media_url else None,
            )
            return message.sid
        except Exception as e:
            logger.error(f"Erreur envoi WhatsApp: {e}")
            return None

    def send_to_client(self, ticket: Ticket, message_body: str, user: User):
        if not ticket.client.phone:
            return None
        sid = self.send_message(ticket.client.phone, message_body)
        if sid:
            Message.objects.create(
                ticket=ticket,
                user=user,
                content=message_body,
                whatsapp_sid=sid,
                whatsapp_status='sent',
                is_whatsapp=True,
            )
        return sid

    def send_to_technician(self, ticket: Ticket, message_body: str, user: User):
        if not ticket.technician or not ticket.technician.user.phone:
            return None
        sid = self.send_message(ticket.technician.user.phone, message_body)
        if sid:
            Message.objects.create(
                ticket=ticket,
                user=user,
                content=message_body,
                whatsapp_sid=sid,
                whatsapp_status='sent',
                is_whatsapp=True,
            )
        return sid