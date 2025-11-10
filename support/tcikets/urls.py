from django.urls import path
from . import views
from . import extend_views
from .search_views import (
    GlobalSearchView,
    TicketSearchView,
    ProcedureSearchView,
    InterventionSearchView,
    UserSearchView
)
urlpatterns = [
    path('whatsapp/webhook/', views.whatsapp_webhook),

    # Clients
    path('clients/', extend_views.ClientViewSet.as_view({'get': 'list'}), name='client-list'),
    path('clients/<uuid:pk>/', views.ClientRetrieveUpdateDestroyView.as_view(), name='client-detail'),

    # Techniciens
    path('technicians/', extend_views.TechnicianViewSet.as_view({'get': 'list'}), name='technician-list'),
    path('technicians/<uuid:pk>/', views.TechnicianRetrieveUpdateDestroyView.as_view(), name='technician-detail'),
    path('active-technicians-stats/', extend_views.active_technicians_stats, name='technician-stats'),


    # Tickets
    path("tickets/export/<str:file_format>/", views.ExportTicketPDFView.as_view(), name='export-tickets'),
    path('tickets/', views.TicketListCreateView.as_view(), name='ticket-list'),
    path('tickets/<uuid:id>/', views.TicketRetrieveUpdateDestroyView.as_view(), name='ticket-detail'),
    path('tickets/<uuid:pk>/<str:action>/', views.TicketActionsView.as_view(), name='ticket-actions'),
    path('tickets/<uuid:ticket_id>/interventions/', views.InterventionByTicketView.as_view(), name='ticket-interventions'),

    # Interventions
    path('interventions/', views.InterventionListView.as_view(), name='intervention-list-create'),
    path('interventions/<uuid:pk>/', views.InterventionRetrieveUpdateDestroyView.as_view(), name='intervention-detail'),
    path('interventions/<uuid:intervention_id>/export/pdf/', views.download_intervention_report, name='intervention-pdf-report'),
    path('interventions/monthly-report/excel/', views.MonthlyReportExcelView.as_view(), name='monthly-excel-report'),

    # Profil utilisateur
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('profile/avatar/', views.UserAvatarUploadView.as_view(), name='user-avatar-upload'),
    path('profile/change-password/', views.ChangePasswordView.as_view(), name='change-password'),

    # Users
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('users/<uuid:pk>/', views.UserDetailView.as_view(), name='user-detail'),

    # Ratings
    path('technicians/<uuid:technician_id>/ratings/', views.TechnicianRatingListCreateView.as_view(), name='technician-ratings'),
    path('clients/<uuid:client_id>/ratings/', views.ClientRatingListCreateView.as_view(), name='client-ratings'),
    path('user-ratings/', views.UserRatingsView.as_view(), name='user-ratings'),
    path('technicians/<uuid:technician_id>/can-rate/', views.CanRateTechnicianView.as_view(), name='can-rate-technician'),
    path('clients/<uuid:client_id>/can-rate/', views.CanRateClientView.as_view(), name='can-rate-client'),

    # WhatsApp Integration
    path('interventions/<uuid:intervention_id>/complete/', views.CompleteInterventionView.as_view(), name='complete_intervention'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('whatsapp/config/', views.whatsapp_config, name='whatsapp_config'),    
    path('tickets/<uuid:ticket_id>/whatsapp-messages/', views.ticket_whatsapp_messages, name='ticket_whatsapp_messages'),
   # path('tickets/<uuid:ticket_id>/send-whatsapp/', views.send_whatsapp_message_view, name='send_whatsapp_message'),
    
    # URLs pour les messages normaux (si besoin)
    #path('tickets/<uuid:ticket_id>/messages/', views.ticket_messages, name='ticket_messages'),
    path('tickets/<uuid:ticket_id>/messages/', extend_views.TicketViewSet.as_view({'get':"list"}), name='ticket-messages'),

    path('messages/', views.create_message, name='create_message'),
    
    path('notifications/', extend_views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread/', extend_views.UnreadNotificationListView.as_view(), name='unread-notifications'),
    path('notifications/<uuid:pk>/', extend_views.NotificationDetailView.as_view(), name='notification-detail'),
    path('notifications/<uuid:pk>/read/', extend_views.mark_notification_read, name='mark-notification-read'),
    path('notifications/mark-all-read/', extend_views.mark_all_notifications_read, name='mark-all-read'),
    path('notifications/stats/', extend_views.NotificationStatsView.as_view(), name='notification-stats'),
    
    path('tickets/<uuid:ticket_id>/send-to-client/', views.send_to_client, name='send_to_client'),
    path('tickets/<uuid:ticket_id>/send-to-technician/', views.send_to_technician, name='send_to_technician'),
    
    
 #  path('notifications/', extend_views.NotificationListView.as_view(), name='notification-list'),
    #path('notifications/mark-all-read/', extend_views.mark_all_notifications_read, name='mark-all-notifications-read'),
    
    path('procedures/', extend_views.ProcedureListCreateView.as_view(), name='procedure-list'),
    path('procedures/<uuid:pk>/', extend_views.ProcedureRetrieveUpdateDestroyView.as_view(), name='procedure-detail'),
    #path('procedures/upload_image/', extend_views.upload_procedure_image, name='procedure-upload-image'),
    #path('procedures/images/<uuid:image_id>/', extend_views.delete_procedure_image, name='procedure-delete-image'),
    path('procedures/<uuid:procedure_id>/interaction/', extend_views.procedure_interaction, name='procedure-interaction'),   
    #path('procedures/', views.ProcedureListCreateView.as_view(), name='procedure-list-create'),
    #path('procedures/<uuid:pk>/', views.ProcedureRetrieveUpdateDestroyView.as_view(), name='procedure-detail')    # Imagnagement
    path('procedures/images/', extend_views.ProcedureImageListCreateView.as_view(), name='procedure-image-list'),
    path('procedures/upload_image/', extend_views.upload_procedure_image, name='upload-procedure-image'),
    path('procedures/images/<uuid:image_id>/', extend_views.delete_procedure_image, name='delete-procedure-image') ,   # Attant management
    path('procedures/attachments/', extend_views.ProcedureAttachmentListCreateView.as_view(), name='procedure-attachment-list'),
    path('procedures/upload_attachment/', extend_views.upload_procedure_attachment, name='upload-procedure-attachment'),
    path('procedures/attachments/<uuid:attachment_id>/', extend_views.delete_procedure_attachment, name='delete-procedure-attachment') ,   # Medirving (secure)
    path('procedures/media/<str:file_type>/<uuid:file_id>/', extend_views.serve_media_file, name='serve-media-file') ,   # Tag gement
    path('procedures/tags/', extend_views.ProcedureTagListCreateView.as_view(), name='procedure-tag-list'),
    
    
    #serach section
    
    path("search/", GlobalSearchView.as_view(), name="global-search"),
    path("search/tickets/", TicketSearchView.as_view(), name="search-tickets"),
    path("search/procedures/", ProcedureSearchView.as_view(), name="search-procedures"),
    path("search/interventions/", InterventionSearchView.as_view(), name="search-interventions"),
    path("search/users/", UserSearchView.as_view(), name="search-users"),
    
]
