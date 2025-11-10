
import json
import time
import uuid
import asyncio
import base64
import os
from collections import defaultdict
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.files.base import ContentFile
from django.core.cache import cache
from .models import Ticket, Message
from django.contrib.auth.models import AnonymousUser

# For rate limiting events
TYPING_THROTTLE = 0.5  # seconds
ONLINE_THROTTLE = 5.0  # seconds
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

def json_serialize(obj):
    """Convert UUID and datetime to JSON-serializable formats."""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

class TicketChatConsumer(AsyncWebsocketConsumer):
    # Use Redis for distributed tracking in production
    CACHE_PREFIX = "ticket_chat_"
    CACHE_TIMEOUT = 86400  # 24 hours

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = None
        self.ticket_id = None
        self.room_group_name = None
        self.last_typing_time = 0
        self.last_online_time = 0

    active_connections = defaultdict(set)  # ticket_id -> set of channel_names
    user_channels = defaultdict(dict)  # user_id -> {ticket_id: channel_name}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = None
        self.ticket_id = None
        self.room_group_name = None
        self.last_typing_time = 0
        self.last_online_time = 0

    async def connect(self):
        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']
        self.room_group_name = f'ticket_{self.ticket_id}'
        user = self.scope["user"]

        if isinstance(user, AnonymousUser):
            await self.close()
            return

        self.user_id = str(user.id)

        if await self.has_permission(user, self.ticket_id):
            # Add to active connections
            self.active_connections[self.ticket_id].add(self.channel_name)
            self.user_channels[self.user_id][self.ticket_id] = self.channel_name

            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Notify others that this user is online
            await self.notify_online(user)
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Remove from active connections
        if self.ticket_id and self.channel_name in self.active_connections.get(self.ticket_id, set()):
            self.active_connections[self.ticket_id].discard(self.channel_name)
            
        if self.user_id and self.ticket_id in self.user_channels.get(self.user_id, {}):
            del self.user_channels[self.user_id][self.ticket_id]
            if not self.user_channels[self.user_id]:
                del self.user_channels[self.user_id]
        
        # Notify others that this user is offline
        user = self.scope["user"]
        if not isinstance(user, AnonymousUser):
            await self.notify_offline(user)
            
        # Leave room group
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            user = self.scope["user"]
            msg_type = data.get("type", "chat")

            if msg_type == "chat":
                message = data.get("message", "")
                message_id = data.get("id")
                image_data = data.get("image")  # Base64 encoded image
                
                # Save message to database
                saved_message = await self.save_message(message, image_data, message_id)
                
                if saved_message:
                    # Prepare event data
                    event_data = {
                        "type": "chat_message",
                        "user_id": str(user.id),
                        "user_type": getattr(user, 'userType', 'client'),
                        "message_id": message_id,
                        "timestamp": saved_message.timestamp.isoformat() if saved_message.timestamp else datetime.now().isoformat()
                    }
                    
                    # Add content or image URL to event data
                    if saved_message.content:
                        event_data["message"] = saved_message.content
                    if saved_message.image:
                        event_data["image_url"] = saved_message.image.url
                    
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        event_data
                    )

            elif msg_type == "typing":
                current_time = time.time()
                if current_time - self.last_typing_time > TYPING_THROTTLE:
                    self.last_typing_time = current_time
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "user_typing",
                            "user_id": str(user.id),
                            "user_name": f"{user.first_name} {user.last_name}",
                            "channel_name": self.channel_name,
                        }
                    )
            elif msg_type == "ping":
                # Respond to ping with pong to keep connection alive
                await self.send(text_data=json.dumps({"type": "pong", "timestamp": time.time()}))
        except json.JSONDecodeError:
            print("Invalid JSON received")
        except Exception as e:
            print(f"Error in receive: {e}")

    async def chat_message(self, event):
        # Prepare response data
        response_data = {
            "type": "chat",
            "id": event["message_id"],
            "user_id": event["user_id"],
            "user_type": event["user_type"],
            "timestamp": event.get("timestamp", datetime.now().isoformat())
        }
        
        # Add message or image URL
        if "message" in event:
            response_data["message"] = event["message"]
        if "image_url" in event:
            response_data["image_url"] = event["image_url"]
        
        await self.send(text_data=json.dumps(response_data, default=json_serialize))
       
    
    async def user_online(self, event):
        # Skip sending to the excluded channel (the user who went online)
        if self.channel_name == event.get("exclude_channel"):
            return

        await self.send(text_data=json.dumps({
            "type": "user_online",
            "user_id": event["user_id"],
            "user_name": event["user_name"],
            "user_type": event["user_type"]
        }, default=json_serialize))
        
    async def user_offline(self, event):
        # Skip sending to the excluded channel (the user who went offline)
        if self.channel_name == event.get("exclude_channel"):
            return

        await self.send(text_data=json.dumps({
            "type": "user_offline",
            "user_id": event["user_id"],
            "user_name": event["user_name"],
            "user_type": event["user_type"]
        }, default=json_serialize))

    # -----------------------------
    # Helper methods
    # -----------------------------
    async def notify_online(self, user):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_online",
                "user_id": str(user.id),
                "user_name": f"{user.first_name} {user.last_name}",
                "user_type": getattr(user, 'userType', 'client'),
                # Exclude self from online notification
                "exclude_channel": self.channel_name
            }
        )

    async def notify_offline(self, user):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_offline",
                "user_id": str(user.id),
                "user_name": f"{user.first_name} {user.last_name}",
                "user_type": getattr(user, 'userType', 'client'),
                # Exclude self from offline notification
                "exclude_channel": self.channel_name
            }
        )

    # -----------------------------
    # Permissions
    # -----------------------------
    @database_sync_to_async
    def has_permission(self, user, ticket_id):
        try:
            ticket = Ticket.objects.select_related(
                'client', 'technician'
            ).get(id=ticket_id)
            
            # Admin users have access to all tickets
            if getattr(user, 'is_staff', False) or getattr(user, 'userType', '') == 'admin':
                return True
                
            # Client can access their own tickets
            if hasattr(user, 'client_profile') and user.client_profile == ticket.client:
                return True
                
            # Technician can access assigned tickets
            if hasattr(user, 'technician_profile') and user.technician_profile == ticket.technician:
                return True
                
            return False
        except Ticket.DoesNotExist:
            return False
        except Exception as e:
            print(f"Permission check error: {e}")
            return False
        
        
    @database_sync_to_async
    def save_message(self, content, image_data=None, message_id=None):
        """Save message to database, handling images if provided"""
        try:
            user = self.scope["user"]
            ticket = Ticket.objects.get(id=self.ticket_id)
            
            message = Message(
                id=message_id or uuid.uuid4(),
                ticket=ticket,
                user=user,
                content=content
            )
            
            # Handle image data if provided
            if image_data:
                # Check if image data is a base64 string
                if isinstance(image_data, str) and image_data.startswith('data:image'):
                    format, imgstr = image_data.split(';base64,') 
                    ext = format.split('/')[-1] 
                    
                    # Validate image size
                    if len(imgstr) > MAX_IMAGE_SIZE * 1.37:  # Account for base64 overhead
                        raise ValueError("Image too large")
                    
                    # Create ContentFile from base64 data
                    data = ContentFile(
                        base64.b64decode(imgstr), 
                        name=f"{message.id}.{ext}"
                    )
                    message.image.save(f"{message.id}.{ext}", data, save=False)
            
            message.save()
            return message
        except Exception as e:
            print(f"Error saving message: {e}")
            return None

    @database_sync_to_async
    def get_recent_messages(self, limit=50):
        """Retrieve recent messages for the ticket"""
        try:
            messages = Message.objects.filter(
                ticket_id=self.ticket_id
            ).select_related('user').order_by('-timestamp')[:limit]
            
            # Convert to list in reverse order (oldest first)
            return list(reversed(messages))
        except Exception as e:
            print(f"Error retrieving messages: {e}")
            return []
