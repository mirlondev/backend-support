from django.contrib import admin
from .models import Client, Technician, Ticket, Intervention,Ticket,TicketImage, Message, Procedure,Notification, ClientRating, TechnicianRating,ProcedureTag, ProcedureImage, ProcedureAttachment
from django.contrib import admin
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django import forms
from django.contrib.auth import get_user_model
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
    list_display = ['procedure', 'caption', 'uploaded_at']

@admin.register(ProcedureAttachment)
class ProcedureAttachmentAdmin(admin.ModelAdmin):
    list_display = ['procedure', 'name', 'file_type', 'file_size']

@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'difficulty', 'status', 'author', 'created_at', 'views', 'likes']
    list_filter = ['category', 'difficulty', 'status', 'created_at']
    search_fields = ['title', 'description', 'content']
    filter_horizontal = ['tags', 'related_procedures']
    
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'title', 'ticket']
   


class TicketImageInline(admin.TabularInline):
    model = TicketImage
    extra = 1
    
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "userType")
@admin.register(Client)

class ClientAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'company', 'created_at', 'id')
    list_filter = ('company', 'created_at')

@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialty', 'phone', 'created_at', 'id')
    list_filter = ('specialty', 'created_at')

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
