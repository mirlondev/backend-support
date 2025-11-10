from django.apps import AppConfig


class TciketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tcikets'
    
    def ready(self):
        import tcikets.signals
    
