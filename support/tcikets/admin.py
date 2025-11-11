from django.contrib import admin
from .models import Client, Technician, Ticket, Intervention,Ticket,TicketImage, Message, Procedure,Notification, ClientRating, TechnicianRating,ProcedureTag, ProcedureImage, ProcedureAttachment
from django.contrib import admin
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django import forms
from django.contrib.auth import get_user_model
from django.utils.html import format_html
User = get_user_model() 





class ProcedureAdminForm(forms.ModelForm):
    class Meta:
        model = Procedure
        fields = '__all__'
        widgets = {
            'steps': CKEditorUploadingWidget(),
        }
@admin.register(ProcedureTag)
class ProcedureTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
@admin.register(ProcedureImage)
class ProcedureImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'procedure', 'image_preview', 'caption',  'uploaded_at']
    list_filter = ['uploaded_at', 'procedure']
    search_fields = ['caption', 'alt_text', 'procedure__title']
    readonly_fields = ['image_preview_large', 'width', 'height', 'uploaded_at']
    
    fieldsets = (
        ('Image', {
            'fields': ('procedure', 'image', 'image_preview_large')
        }),
        ('Informations', {
            'fields': ('caption', 'alt_text', 'order')
        }),
        ('Métadonnées', {
            'fields': ('width', 'height', 'formatted_file_size', 'file_extension', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )
    
    def image_preview(self, obj):
        """Miniature dans la liste"""
        if obj.thumbnail_url:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />',
                obj.thumbnail_url
            )
        return "Pas d'image"
    image_preview.short_description = 'Aperçu'
    
    def image_preview_large(self, obj):
        """Grande prévisualisation dans le formulaire"""
        if obj.medium_url:
            return format_html(
                '<img src="{}" style="max-width: 500px; max-height: 500px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />'
                '<br><br>'
                '<a href="{}" target="_blank" class="button">Voir en taille réelle</a>',
                obj.medium_url,
                obj.image_url
            )
        return "Pas d'image"
    image_preview_large.short_description = 'Prévisualisation'


@admin.register(ProcedureAttachment)
class ProcedureAttachmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'procedure', 'attachment_type', 'file_size', 'downloads', 'uploaded_at']
    list_filter = ['attachment_type', 'uploaded_at', 'is_public']
    search_fields = ['name', 'description', 'procedure__title']
    readonly_fields = ['file_preview', 'downloads', 'uploaded_at']
    
    fieldsets = (
        ('Fichier', {
            'fields': ('procedure', 'file', 'file_preview')
        }),
        ('Informations', {
            'fields': ('name', 'description', 'attachment_type', 'is_public')
        }),
        ('Métadonnées', {
            'fields': ('file_type', 'file_size', 'icon_class', 'downloads', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )
    
    def file_preview(self, obj):
        """Aperçu du fichier"""
        if obj.is_video:
            return format_html(
                '<video controls style="max-width: 500px; max-height: 300px; border-radius: 8px;">'
                '<source src="{}" type="{}">'
                'Votre navigateur ne supporte pas la balise video.'
                '</video>',
                obj.file_url,
                obj.file_type
            )
        elif obj.attachment_type == 'document':
            return format_html(
                '<a href="{}" target="_blank" class="button">📄 Ouvrir le document</a>',
                obj.file_url
            )
        else:
            return format_html(
                '<a href="{}" target="_blank" class="button">📎 Télécharger</a>',
                obj.file_url
            )
    file_preview.short_description = 'Aperçu'
   

@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'difficulty', 'status', 'author', 'created_at', 'views', 'likes']
    list_filter = ['category', 'difficulty', 'status', 'created_at']
    search_fields = ['title', 'description', 'content']
    filter_horizontal = ['tags', 'related_procedures']
    
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'title', 'ticket']
   

# admin.py

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'created_at')  # ✅ retire 'phone'

@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialty', 'created_at')  # ✅ retire 'phone'




class TicketImageInline(admin.TabularInline):
    model = TicketImage
    extra = 1
    readonly_fields = ('image_preview', 'width', 'height', 'file_size', 'uploaded_at')
    fields = ('image', 'image_preview', 'width', 'height', 'file_size', 'uploaded_at')

    def image_preview(self, obj):
        if obj.thumbnail_url:
            return format_html(
                '<img src="{}" style="width:50px;height:50px;object-fit:cover;" />',
                obj.thumbnail_url
            )
        return "Pas d’image"
    image_preview.short_description = "Aperçu"
    
    
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "userType")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'priority', 'client', 'technician', 'created_at', )
    list_filter = ('status', 'priority', 'created_at')
    inlines = [TicketImageInline]

@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'created_at')
    list_filter = ('created_at',)
    
    
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('content', 'user',  'ticket')

@admin.register(ClientRating)
class ClientRatingAdmin(admin.ModelAdmin):
    list_display = ('comment', 'rating', 'client', 'technician')
    

@admin.register(TechnicianRating)
class TechnicianRatingAdmin(admin.ModelAdmin):
    list_display = ('comment', 'rating', 'client', 'technician')
