# support/search_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from .models import User,Ticket,Intervention,Procedure
from .serializers import UserSerializer,TicketSerializer,ProcedureSerializer,InterventionSerializer


class GlobalSearchView(APIView):
    def get(self, request):
        query = request.GET.get("q", "").strip()
        if not query:
            return Response({"error": "Missing query"}, status=400)

        procedures = Procedure.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )[:10]

        tickets = Ticket.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query) | Q(code__icontains=query)
        )[:10]

        interventions = Intervention.objects.filter(
             Q(code__icontains=query)
        )[:10]

        users = User.objects.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        )[:10]

        return Response({
            "procedures": ProcedureSerializer(procedures, many=True).data,
            "tickets": TicketSerializer(tickets, many=True).data,
            "interventions": InterventionSerializer(interventions, many=True).data,
            "users": UserSerializer(users, many=True).data,
        })


class TicketSearchView(APIView):
    def get(self, request):
        query = request.GET.get("q", "").strip()
        tickets = Ticket.objects.filter(
            tickets = Ticket.objects.filter(
                    Q(title__icontains=query) | 
                    Q(description__icontains=query) |
                    Q(code__icontains=query)
                )
        )
        return Response(TicketSerializer(tickets, many=True).data)


class ProcedureSearchView(APIView):
    def get(self, request):
        query = request.GET.get("q", "").strip()
        procedures = Procedure.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
        return Response(ProcedureSerializer(procedures, many=True).data)


class InterventionSearchView(APIView):
    def get(self, request):
        query = request.GET.get("q", "").strip()
        interventions = Intervention.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
        return Response(InterventionSerializer(interventions, many=True).data)


class UserSearchView(APIView):
    def get(self, request):
        query = request.GET.get("q", "").strip()
        users = User.objects.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        )
        return Response(UserSerializer(users, many=True).data)
