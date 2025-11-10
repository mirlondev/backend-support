# management/commands/seed_tickets.py
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from tcikets.models import Client, Technician, Ticket, Intervention

User = get_user_model()

class Command(BaseCommand):
    help = "Créer des tickets et interventions de test"

    def handle(self, *args, **kwargs):
        # --- Création de clients ---
        clients_data = [
            {"company": "Société Orange", "email": "support@orange.com"},
            {"company": "Banque Centrale", "email": "it@banquecentrale.com"},
            {"company": "Université Kinshasa", "email": "it@unikin.cd"},
        ]
        clients = []
        for i, c in enumerate(clients_data, start=1):
            user, _ = User.objects.get_or_create(
                username=f"client{i}",
                defaults={
                    "first_name": f"Client{i}",
                    "last_name": "Test",
                    "email": c["email"],
                    "userType": "client",
                    "phone": f"+24206000000{i}",
                },
            )
            client, _ = Client.objects.get_or_create(
                user=user,
                defaults={"company": c["company"], "phone": user.phone},
            )
            clients.append(client)

        # --- Création de techniciens ---
        technicians_data = [
            {"specialty": "network", "email": "tech1@example.com"},
            {"specialty": "hardware", "email": "tech2@example.com"},
        ]
        technicians = []
        for i, t in enumerate(technicians_data, start=1):
            user, _ = User.objects.get_or_create(
                username=f"tech{i}",
                defaults={
                    "first_name": f"Tech{i}",
                    "last_name": "Support",
                    "email": t["email"],
                    "userType": "technician",
                    "phone": f"+24206100000{i}",
                },
            )
            tech, _ = Technician.objects.get_or_create(
                user=user,
                defaults={"specialty": t["specialty"], "phone": user.phone},
            )
            technicians.append(tech)

        # --- Création de tickets ---
        tickets_titles = [
            "Panne réseau",
            "Imprimante en panne",
            "Problème logiciel",
            "Erreur serveur",
            "Mauvaise configuration switch",
            "Problème de WiFi",
            "Clavier défectueux",
            "Blue screen Windows",
            "Application qui plante",
            "Serveur email indisponible",
        ]
        priorities = ["low", "medium", "high", "urgent"]
        tickets = []

        for i, title in enumerate(tickets_titles, start=1):
            ticket, created = Ticket.objects.get_or_create(
                title=title,
                defaults={
                    "description": f"{title} - description automatique",
                    "priority": random.choice(priorities),
                    "client": random.choice(clients),
                    "technician": random.choice(technicians),
                    "problem_start_date": timezone.now(),
                },
            )
            tickets.append(ticket)
            if created:
                self.stdout.write(self.style.SUCCESS(f"✅ Ticket créé : {ticket.title}"))

        # --- Création d’interventions ---
        for ticket in tickets:
            intervention, created = Intervention.objects.get_or_create(
                ticket=ticket,
                defaults={
                    "technician": ticket.technician,
                    "report": f"Rapport automatique pour {ticket.title}",
                    "intervention_date": timezone.now().date(),
                    "start_time": timezone.now().time(),
                    "end_time": (timezone.now() + timezone.timedelta(hours=2)).time(),
                    "transport_cost": random.randint(10, 50),
                    "additional_costs": random.randint(5, 100),
                    "hours_worked": random.randint(1, 8),
                    "travel_time": random.randint(0, 2),
                    "status": "scheduled",
                },
            )
            if created:
                intervention.save()  # Calculera automatiquement total_cost
                self.stdout.write(self.style.SUCCESS(f"🛠️ Intervention créée pour : {ticket.title}"))
          
        self.stdout.write(self.style.SUCCESS("🎉 10 tickets et 10 interventions créés avec succès"))
