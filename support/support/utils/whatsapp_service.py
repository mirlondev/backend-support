from tcikets.models import User, Message, Ticket, Technician

from twilio.rest import Client
from django.conf import settings
import logging
from django.utils import timezone

from rest_framework.response import Response
import uuid

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self._validate_twilio_config()
        try:
            self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            self.whatsapp_number = settings.TWILIO_WHATSAPP_NUMBER
            logger.info("Service WhatsApp Twilio initialisé avec succès")
        except Exception as e:
            logger.error(f"Erreur d'initialisation Twilio: {str(e)}")
            raise

    def _validate_twilio_config(self):
        """Valide la configuration Twilio"""
        required_settings = [
            ('TWILIO_ACCOUNT_SID', getattr(settings, 'TWILIO_ACCOUNT_SID', None)),
            ('TWILIO_AUTH_TOKEN', getattr(settings, 'TWILIO_AUTH_TOKEN', None)),
            ('TWILIO_WHATSAPP_NUMBER', getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None))
        ]
        missing = [name for name, value in required_settings if not value]
        if missing:
            raise Exception(f"Paramètres Twilio manquants: {', '.join(missing)}")

    def _clean_phone_number(self, phone_number):
        """Nettoie et formate le numéro de téléphone pour le Congo"""
        if not phone_number:
            raise ValueError("Numéro de téléphone vide")
        
        # Supprimer tous les caractères non numériques
        cleaned = ''.join(filter(str.isdigit, str(phone_number)))
        
        if not cleaned:
            raise ValueError("Numéro de téléphone invalide")
        
        # Format pour le Congo (+242)
        if cleaned.startswith('2420'):
            cleaned = '242' + cleaned[4:]  # Supprimer le 0 après 242
        elif cleaned.startswith('0'):
            cleaned = '242' + cleaned[1:]  # Ajouter l'indicatif Congo
        
        # Twilio nécessite le format E.164 avec +
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
            
        return cleaned

    def send_message(self, to_number, message_body, media_url=None, ticket=None, user=None):
        """
        Envoie un message WhatsApp via Twilio et le sauvegarde en base
        """
        try:
            to_number = self._clean_phone_number(to_number)
            
            message_params = {
                #'from_': f'whatsapp:{self.whatsapp_number}',
                'from_':'whatsapp:+14155238886',
                'body': message_body,
                'to': f'whatsapp:{to_number}'
            }
            
            if media_url:
                message_params['media_url'] = [media_url]

            # Envoi WhatsApp via Twilio
            twilio_message = self.client.messages.create(**message_params)
            message_sid = twilio_message.sid

            # Sauvegarde en base de données
            if ticket and user:
                self._save_message_to_db(
                    ticket=ticket,
                    user=user,
                    message_body=message_body,
                    whatsapp_sid=message_sid,
                    status='sent',
                    media_url=media_url
                )

            logger.info(f"✅ Message WhatsApp envoyé: {message_sid} à {to_number}")
            return message_sid
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi WhatsApp à {to_number}: {str(e)}")
            
            # Sauvegarde de l'échec
            if ticket and user:
                self._save_message_to_db(
                    ticket=ticket,
                    user=user,
                    message_body=message_body,
                    status='failed',
                    error_message=str(e),
                    media_url=media_url
                )
            
            raise Exception(f"Erreur d'envoi WhatsApp: {str(e)}")

    def _save_message_to_db(self, ticket, user, message_body, whatsapp_sid=None, 
                          status='sent', error_message=None, media_url=None):
        """Sauvegarde le message dans la base de données"""
        try:
            message = Message(
                ticket=ticket,
                user=user,
                content=message_body,
                timestamp=timezone.now(),
                is_whatsapp=True,
                whatsapp_status=status,
                whatsapp_sid=whatsapp_sid
            )
            
            if error_message:
                message.error_message = error_message
                
            if media_url:
                message.media_url = media_url
                
            message.save()
            logger.info(f"💾 Message sauvegardé en base: {message.id}")
            return message
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde message: {str(e)}")
            return None

    def send_to_client(self, ticket, message_body, user, media_url=None):
        """
        Envoie un message WhatsApp au client d'un ticket
        """
        try:
            if not ticket or not ticket.client:
                raise Exception("Ticket ou client non spécifié")
            
            if not ticket.client.phone:
                raise Exception("Le client n'a pas de numéro de téléphone enregistré")
            
            message_sid = self.send_message(
                to_number=ticket.client.phone,
                message_body=message_body,
                media_url=media_url,
                ticket=ticket,
                user=user
            )
            
            return message_sid
            
        except Exception as e:
            logger.error(f"❌ Erreur send_to_client ticket {ticket.id}: {str(e)}")
            raise

    def send_to_technician(self, ticket, message_body, user, media_url=None):
        """
        Envoie un message WhatsApp au technicien assigné à un ticket
        """
        try:
            if not ticket or not ticket.technician:
                raise Exception("Ticket ou technicien non spécifié")
            
            if not ticket.technician.phone:
                raise Exception("Le technicien n'a pas de numéro de téléphone enregistré")
            
            message_sid = self.send_message(
                to_number=ticket.technician.phone,
                message_body=message_body,
                media_url=media_url,
                ticket=ticket,
                user=user
            )
            
            return message_sid
            
        except Exception as e:
            logger.error(f"❌ Erreur send_to_technician ticket {ticket.id}: {str(e)}")
            raise

    def notify_ticket_created(self, ticket):
        """
        Notifie la création d'un nouveau ticket aux administrateurs
        """
        try:
            if not ticket:
                raise Exception("Ticket non spécifié")

            message = (
                f"🎫 *NOUVEAU TICKET CRÉÉ*\n\n"
                f"📝 *Titre:* {ticket.title}\n"
                f"👤 *Client:* {ticket.client.user.get_full_name() or ticket.client.user.username}\n"
                f"🔢 *Code:* {ticket.code}\n"
                f"⚠️ *Priorité:* {ticket.get_priority_display()}\n"
                f"📱 *Téléphone:* {ticket.client.phone or 'Non renseigné'}\n"
                f"📍 *Localisation:* {ticket.client.company or 'Non spécifiée'}\n\n"
                f"_Ticket en attente d'assignation à un technicien_"
            )

            # Notifier les admins
            admins = User.objects.filter(userType="admin", is_active=True)
            sent_count = 0
            
            for admin in admins:
                if admin.phone and admin.phone != self.whatsapp_number:
                    try:
                        admin_phone_cleaned = self._clean_phone_number(admin.phone)
                        self.send_message(
                            to_number=admin_phone_cleaned,
                            message_body=message,
                            ticket=ticket,
                            user=admin
                        )
                        sent_count += 1
                        logger.info(f"📨 Notification création envoyée à l'admin {admin.username}")
                    except Exception as e:
                        logger.error(f"❌ Erreur envoi admin {admin.username}: {str(e)}")
            
            # Notifier le client
            if ticket.client.phone:
                try:
                    client_message = (
                        f"✅ *VOTRE TICKET A ÉTÉ CRÉÉ*\n\n"
                        f"📝 *Problème:* {ticket.title}\n"
                        f"🔢 *Référence:* {ticket.code}\n"
                        f"⚠️ *Priorité:* {ticket.get_priority_display()}\n"
                        f"📅 *Date:* {ticket.created_at.strftime('%d/%m/%Y à %H:%M')}\n\n"
                        f"_Un technicien vous contactera prochainement._"
                    )
                    
                    self.send_message(
                        to_number=ticket.client.phone,
                        message_body=client_message,
                        ticket=ticket,
                        user=ticket.client.user
                    )
                    sent_count += 1
                    logger.info(f"📨 Notification création envoyée au client")
                except Exception as e:
                    logger.error(f"❌ Erreur envoi client: {str(e)}")

            logger.info(f"📊 Notifications création ticket envoyées: {sent_count} message(s)")
            return sent_count > 0
            
        except Exception as e:
            logger.error(f"❌ Erreur notify_ticket_created ticket {getattr(ticket.client, 'address', 'Non spécifiée')}: {str(e)}")
            return False

    def notify_ticket_assigned(self, ticket):
        """
        Notifie l'assignation d'un ticket au technicien et au client
        """
        try:
            if not ticket or not ticket.technician:
                raise Exception("Ticket ou technicien non spécifié")

            notifications_sent = 0

            # Message pour le technicien
            tech_message = (
                f"🔧 *NOUVEAU TICKET ASSIGNÉ*\n\n"
                f"📝 *Problème:* {ticket.title}\n"
                f"👤 *Client:* {ticket.client.user.get_full_name() or ticket.client.user.username}\n"
                f"📱 *Téléphone client:* {ticket.client.phone or 'Non renseigné'}\n"
                f"🔢 *Référence:* {ticket.code}\n"
                f"⚠️ *Priorité:* {ticket.get_priority_display()}\n"
                f"📍 *Localisation:* {ticket.client.company or 'Non spécifiée'}\n\n"
                f"_Veuillez contacter le client pour planifier l'intervention._"
            )

            # Envoyer au technicien
            if ticket.technician.phone:
                try:
                    self.send_message(
                        to_number=ticket.technician.phone,
                        message_body=tech_message,
                        ticket=ticket,
                        user=ticket.technician.user
                    )
                    notifications_sent += 1
                    logger.info(f"📨 Notification assignation envoyée au technicien")
                except Exception as e:
                    logger.error(f"❌ Erreur envoi technicien: {str(e)}")

            # Message pour le client
            client_message = (
                f"✅ *VOTRE TICKET EST PRIS EN CHARGE*\n\n"
                f"🔧 *Technicien assigné:* {ticket.technician.user.get_full_name() or ticket.technician.user.username}\n"
                f"📱 *Contact technicien:* {ticket.technician.phone or 'Non renseigné'}\n"
                f"🔢 *Référence:* {ticket.code}\n\n"
                f"_Le technicien vous contactera prochainement pour planifier l'intervention._"
            )

            # Envoyer au client
            if ticket.client.phone:
                try:
                    self.send_message(
                        to_number=ticket.client.phone,
                        message_body=client_message,
                        ticket=ticket,
                        user=ticket.client.user
                    )
                    notifications_sent += 1
                    logger.info(f"📨 Notification assignation envoyée au client")
                except Exception as e:
                    logger.error(f"❌ Erreur envoi client: {str(e)}")

            logger.info(f"📊 Notifications assignation envoyées: {notifications_sent}/2")
            return notifications_sent > 0
            
        except Exception as e:
            logger.error(f"❌ Erreur notify_ticket_assigned ticket {ticket.id if ticket else 'N/A'}: {str(e)}")
            return False

    def send_intervention_created_notification(self, intervention):
        """Notifie la création d'une intervention"""
        try:
            message = (
                f"🛠️ *NOUVELLE INTERVENTION PLANIFIÉE*\n\n"
                f"🔧 *Technicien:* {intervention.technician.user.get_full_name()}\n"
                f"👤 *Client:* {intervention.client.user.get_full_name()}\n"
                f"📅 *Date:* {intervention.intervention_date.strftime('%d/%m/%Y')}\n"
                f"⏰ *Heure:* {intervention.start_time.strftime('%H:%M')}\n"
                f"📝 *Description:* {intervention.description}\n\n"
                f"_Intervention planifiée avec succès_"
            )

            notifications_sent = 0

            if intervention.technician and intervention.technician.phone:
                self.send_message(intervention.technician.phone, message)
                notifications_sent += 1

            if intervention.client and intervention.client.phone:
                self.send_message(intervention.client.phone, message)
                notifications_sent += 1

            logger.info(f"📨 Notifications intervention créée: {notifications_sent}/2")
            return notifications_sent > 0

        except Exception as e:
            logger.error(f"❌ Erreur notification intervention: {e}")
            return False

    def send_intervention_completed_notification(self, intervention, pdf_url=None):
        """Notifie la complétion d'une intervention"""
        try:
            base_message = (
                f"✅ *INTERVENTION TERMINÉE*\n\n"
                f"🔧 *Technicien:* {intervention.technician.user.get_full_name()}\n"
                f"👤 *Client:* {intervention.client.user.get_full_name()}\n"
                f"📅 *Date:* {intervention.intervention_date.strftime('%d/%m/%Y')}\n"
                f"⏰ *Durée:* {intervention.duration or 'Non spécifiée'}\n"
                f"📝 *Résumé:* {intervention.summary or 'Aucun résumé'}\n"
            )
            
            if pdf_url:
                base_message += f"\n📄 *Rapport:* {pdf_url}"

            notifications_sent = 0

            if intervention.client and intervention.client.phone:
                client_message = base_message + "\n\n_Merci pour votre confiance !_"
                self.send_message(intervention.client.phone, client_message)
                notifications_sent += 1

            if intervention.technician and intervention.technician.phone:
                tech_message = base_message + "\n\n_Intervention marquée comme terminée._"
                self.send_message(intervention.technician.phone, tech_message)
                notifications_sent += 1

            logger.info(f"📨 Notifications intervention terminée: {notifications_sent}/2")
            return notifications_sent > 0

        except Exception as e:
            logger.error(f"❌ Erreur notification intervention terminée: {e}")
            return False


# Fonctions utilitaires pour l'intégration dans les vues
def notify_ticket_created(ticket):
    """Notifier la création d'un ticket"""
    try:
        service = WhatsAppService()
        return service.notify_ticket_created(ticket)
    except Exception as e:
        logger.error(f"❌ Erreur notify_ticket_created: {str(e)}")
        return False

def notify_ticket_assigned(ticket):
    """Notifier l'assignation d'un ticket"""
    try:
        service = WhatsAppService()
        return service.notify_ticket_assigned(ticket)
    except Exception as e:
        logger.error(f"❌ Erreur notify_ticket_assigned: {str(e)}")
        return False

def notify_technician_assignment(ticket, technician_id, user):
    """Assigner un technicien et notifier"""
    try:
        technician_uuid = uuid.UUID(str(technician_id).strip())
        technician = Technician.objects.get(id=technician_uuid)
        
        if ticket.technician == technician:
            return {'status': 'technician already assigned', 'assigned': False}

        # Assigner le technicien
        ticket.technician = technician
        ticket.status = 'in_progress'
        ticket.save()

        # Notifier via WhatsApp
        notification_sent = notify_ticket_assigned(ticket)
        
        return {
            'status': 'technician assigned', 
            'assigned': True, 
            'notification_sent': notification_sent
        }
            
    except ValueError:
        raise ValidationError("UUID technicien invalide")
    except Technician.DoesNotExist:
        raise ValidationError("Technicien non trouvé")
    except Exception as e:
        logger.error(f"❌ Erreur notify_technician_assignment: {str(e)}")
        raise