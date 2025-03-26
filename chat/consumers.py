import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room, Message, UserBlock, DirectMessage
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        
        # Check if user is authenticated
        if self.scope["user"].is_anonymous:
            await self.close()
            return
            
        # Check if user is allowed in the room
        if not await self.user_in_room():
            await self.close()
            return
            
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        
        # Notify users in the room that a new user has joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_join',
                'user_id': self.scope["user"].id,
                'email': self.scope["user"].email,
                'first_name': self.scope["user"].first_name,
                'last_name': self.scope["user"].last_name
            }
        )

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Notify users in the room that a user has left
            if not self.scope["user"].is_anonymous:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'user_leave',
                        'user_id': self.scope["user"].id,
                        'email': self.scope["user"].email
                    }
                )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        
        # Check if user is blocked by any user in the room
        is_blocked = await self.is_blocked_by_anyone_in_room()
        if is_blocked:
            # Don't broadcast the message if the user is blocked
            return
            
        # Save message to the database
        await self.save_message(message)
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'user_id': self.scope["user"].id,
                'email': self.scope["user"].email,
                'first_name': self.scope["user"].first_name,
                'last_name': self.scope["user"].last_name,
                'timestamp': (await sync_to_async(Message.objects.latest)('timestamp')).timestamp.isoformat()
            }
        )

    async def chat_message(self, event):
        # Check if message is from a blocked user
        sender_id = event['user_id']
        if await self.is_user_blocked(sender_id):
            return
            
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'user_id': event['user_id'],
            'email': event['email'],
            'first_name': event.get('first_name', ''),
            'last_name': event.get('last_name', ''),
            'timestamp': event.get('timestamp', '')
        }))
        
    async def user_join(self, event):
        # Send notification that user joined the room
        await self.send(text_data=json.dumps({
            'type': 'user_join',
            'user_id': event['user_id'],
            'email': event['email'],
            'first_name': event.get('first_name', ''),
            'last_name': event.get('last_name', '')
        }))
        
    async def user_leave(self, event):
        # Send notification that user left the room
        await self.send(text_data=json.dumps({
            'type': 'user_leave',
            'user_id': event['user_id'],
            'email': event['email']
        }))
        
    async def tournament_notification(self, event):
        # Send tournament notification
        await self.send(text_data=json.dumps({
            'type': 'tournament',
            'message': event['message'],
            'match_details': event.get('match_details', {})
        }))
        
    async def game_invitation(self, event):
        # Send game invitation notification
        await self.send(text_data=json.dumps({
            'type': 'game_invitation',
            'sender_id': event['sender_id'],
            'sender_email': event['sender_email'],
            'invitation_id': event['invitation_id']
        }))
        
    @database_sync_to_async
    def user_in_room(self):
        try:
            room = Room.objects.get(name=self.room_name)
            return room.users.filter(id=self.scope["user"].id).exists()
        except Room.DoesNotExist:
            return False
            
    @database_sync_to_async
    def is_blocked_by_anyone_in_room(self):
        try:
            room = Room.objects.get(name=self.room_name)
            users_in_room = room.users.all()
            return UserBlock.objects.filter(
                blocker__in=users_in_room,
                blocked=self.scope["user"]
            ).exists()
        except Room.DoesNotExist:
            return False
            
    @database_sync_to_async
    def is_user_blocked(self, user_id):
        return UserBlock.objects.filter(
            blocker=self.scope["user"],
            blocked__id=user_id
        ).exists()
            
    @database_sync_to_async
    def save_message(self, content):
        room = Room.objects.get(name=self.room_name)
        Message.objects.create(
            room=room, 
            user=self.scope["user"], 
            content=content
        )


class DirectMessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        
        # Check if user is authenticated
        if self.user.is_anonymous:
            await self.close()
            return
            
        self.user_group_name = f'user_{self.user.id}_dm'
        
        # Join user's personal group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave user's personal group
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        receiver_id = data.get('receiver_id')
        message = data.get('message')
        
        # Check if user is blocked by the receiver
        if await self.is_blocked_by_user(receiver_id):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': "This user has blocked you or you have blocked them."
            }))
            return
            
        # Save direct message to database
        dm = await self.save_direct_message(receiver_id, message)
        if not dm:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': "Could not send message. User not found."
            }))
            return
            
        # Send to receiver's personal group
        receiver_group_name = f'user_{receiver_id}_dm'
        receiver = await self.get_user(receiver_id)
        
        await self.channel_layer.group_send(
            receiver_group_name,
            {
                'type': 'direct_message',
                'message': message,
                'sender_id': self.user.id,
                'sender_email': self.user.email,
                'sender_first_name': self.user.first_name,
                'sender_last_name': self.user.last_name,
                'dm_id': dm.id,
                'timestamp': dm.timestamp.isoformat()
            }
        )
        
        # Send confirmation to the sender
        await self.send(text_data=json.dumps({
            'type': 'dm_sent',
            'message': message,
            'receiver_id': receiver_id,
            'receiver_email': receiver.email if receiver else "Unknown",
            'dm_id': dm.id,
            'timestamp': dm.timestamp.isoformat()
        }))

    async def direct_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'direct_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_email': event['sender_email'],
            'sender_first_name': event.get('sender_first_name', ''),
            'sender_last_name': event.get('sender_last_name', ''),
            'dm_id': event['dm_id'],
            'timestamp': event['timestamp']
        }))
        
    @database_sync_to_async
    def is_blocked_by_user(self, user_id):
        try:
            # Check if either user has blocked the other
            return UserBlock.objects.filter(
                blocker_id=user_id,
                blocked=self.user
            ).exists() or UserBlock.objects.filter(
                blocker=self.user,
                blocked_id=user_id
            ).exists()
        except:
            return True
            
    @database_sync_to_async
    def save_direct_message(self, receiver_id, content):
        try:
            receiver = User.objects.get(id=receiver_id)
            return DirectMessage.objects.create(
                sender=self.user,
                receiver=receiver,
                content=content
            )
        except User.DoesNotExist:
            return None
            
    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        
        # Check if user is authenticated
        if self.user.is_anonymous:
            await self.close()
            return
            
        self.notification_group_name = f'user_{self.user.id}_notifications'
        
        # Join user's notification group
        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave notification group
        if hasattr(self, 'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )
    
    async def notification_message(self, event):
        # Send notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': event['notification_type'],
            'message': event['message'],
            'data': event.get('data', {})
        }))