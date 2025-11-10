from rest_framework.permissions import BasePermission

class IsAdminOrOwner(BasePermission):
    """
    Vérifie les droits selon userType :
    - admin / staff → accès complet
    - technician → accès à ses tickets/interventions
    - client → accès à ses tickets/interventions
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Admin / staff
        if user.is_staff or getattr(user, 'userType', 'admin') == 'admin':
            return True

        # Technicien
        if getattr(user, 'userType', 'technician') == 'technician':
            if hasattr(obj, 'technician') and obj.technician and obj.technician.user.id == user.id:
                return True
            elif hasattr(obj, 'ticket') and obj.ticket and obj.ticket.technician and obj.ticket.technician.user.id == user.id:
                return True

        # Client
        if getattr(user, 'userType', 'client') == 'client':
            if hasattr(obj, 'client') and obj.client and obj.client.user.id == user.id:
                return True
            elif hasattr(obj, 'ticket') and obj.ticket and obj.ticket.client and obj.ticket.client.user.id == user.id:
                return True

        return False
