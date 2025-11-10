# management/commands/seed_procedures.py
import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tcikets.models import Procedure, ProcedureTag, ProcedureImage

User = get_user_model()

class Command(BaseCommand):
    help = 'Peupler la base de données avec 10 procédures d\'exemple et images placeholder'

    def handle(self, *args, **options):
        # Créer des tags
        tags_data = [
            'networking', 'installation', 'configuration', 'enterprise',
            'security', 'troubleshooting', 'hardware', 'software'
        ]
        tags = {}
        for tag_name in tags_data:
            tag, _ = ProcedureTag.objects.get_or_create(
                name=tag_name,
                defaults={'slug': tag_name}
            )
            tags[tag_name] = tag

        # Créer un utilisateur auteur
        author, _ = User.objects.get_or_create(
            username='jeanpierre',
            defaults={
                'first_name': 'Jean-Pierre',
                'last_name': 'Mukendi',
                'email': 'jeanpierre@example.com'
            }
        )

        # Liste de procédures
        procedures_data = [
            {
                "title": "Installation and Configuration of Network Equipment",
                "category": "Network Infrastructure",
                "difficulty": "intermediate",
                "tags": ["networking", "installation", "configuration", "enterprise"]
            },
            {
                "title": "Firewall Deployment and Security Policies",
                "category": "Security",
                "difficulty": "advanced",
                "tags": ["security", "configuration", "enterprise"]
            },
            # ... ajouter les autres 8 procédures ici
        ]

        # URL placeholder pour images
        placeholder_url = "https://placehold.co/600x400"

        for proc_data in procedures_data:
            procedure, created = Procedure.objects.get_or_create(
                title=proc_data["title"],
                defaults={
                    "description": f"Procedure for {proc_data['title']}.",
                    "content": f"## Steps\n\nThis is the procedure for {proc_data['title']}.",
                    "category": proc_data["category"],
                    "difficulty": proc_data["difficulty"],
                    "estimated_time": "1-3 hours",
                    "author": author,
                    "status": "published"
                }
            )

            if created:
                # Ajouter les tags
                for t in proc_data["tags"]:
                    procedure.tags.add(tags[t])

                # Ajouter une image placeholder
                try:
                    response = requests.get(placeholder_url)
                    if response.status_code == 200:
                        img_name = f"{procedure.title.replace(' ', '_')}.png"
                        procedure_image = ProcedureImage(
                            procedure=procedure,
                            caption=f"Image for {procedure.title}",
                            alt_text=f"{procedure.title} image"
                        )
                        procedure_image.image.save(img_name, ContentFile(response.content), save=True)
                        self.stdout.write(self.style.SUCCESS(f'Image pour "{procedure.title}" ajoutée'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Erreur téléchargement image: {e}"))

                self.stdout.write(self.style.SUCCESS(f'Procédure "{procedure.title}" créée avec succès'))
            else:
                self.stdout.write(self.style.WARNING(f'Procédure "{procedure.title}" existe déjà'))
