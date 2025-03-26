from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from .models import Room, Message, UserBlock, GameInvitation, DirectMessage
from .serializers import (
    RoomSerializer, MessageSerializer, UserBlockSerializer, 
    GameInvitationSerializer, DirectMessageSerializer, UserSerializer
)

User = get_user_model()
channel_layer = get_channel_layer()

class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Room.objects.filter(users=self.request.user)
    
    def perform_create(self, serializer):
        room = serializer.save()
        room.users.add(self.request.user)
    
    @action(detail=True, methods=['post'])
    def add_user(self, request, pk=None):
        room = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            room.users.add(user)
            
            # Notify the room about new user
            async_to_sync(channel_layer.group_send)(
                f'chat_{room.name}',
                {
                    'type': 'user_join',
                    'user_id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
            )
            
            return Response({'status': 'user added'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def remove_user(self, request, pk=None):
        room = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            room.users.remove(user)
            
            # Notify the room about user leaving
            async_to_sync(channel_layer.group_send)(
                f'chat_{room.name}',
                {
                    'type': 'user_leave',
                    'user_id': user.id,
                    'email': user.email
                }
            )
            
            return Response({'status': 'user removed'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        room = self.get_object()
        messages = room.messages.all()
        
        # Pagination
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Message.objects.filter(
            room__users=self.request.user
        )
    
    def perform_create(self, serializer):
        room_id = self.kwargs.get('room_pk')
        room = get_object_or_404(Room, id=room_id)
        
        # Check if user is in the room
        if not room.users.filter(id=self.request.user.id).exists():
            raise permissions.PermissionDenied("You are not in this room")
        
        message = serializer.save(user=self.request.user, room=room)
        
        # Broadcast message to room
        async_to_sync(channel_layer.group_send)(
            f'chat_{room.name}',
            {
                'type': 'chat_message',
                'message': message.content,
                'user_id': self.request.user.id,
                'email': self.request.user.email,
                'first_name': self.request.user.first_name,
                'last_name': self.request.user.last_name,
                'timestamp': message.timestamp.isoformat()
            }
        )
        return message


class UserBlockViewSet(viewsets.ModelViewSet):
    serializer_class = UserBlockSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UserBlock.objects.filter(blocker=self.request.user)
    
    def perform_create(self, serializer):
        # Prevent self-blocking
        if serializer.validated_data['blocked'] == self.request.user:
            raise serializers.ValidationError("You cannot block yourself")
            
        serializer.save(blocker=self.request.user)


class GameInvitationViewSet(viewsets.ModelViewSet):
    serializer_class = GameInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return GameInvitation.objects.filter(
            Q(sender=self.request.user) | Q(receiver=self.request.user)
        )
    
    def perform_create(self, serializer):
        # Prevent self-invitation
        if serializer.validated_data['receiver'] == self.request.user:
            raise serializers.ValidationError("You cannot invite yourself")
            
        invitation = serializer.save(sender=self.request.user, status='pending')
        
        # Send notification to receiver
        async_to_sync(channel_layer.group_send)(
            f'user_{invitation.receiver.id}_notifications',
            {
                'type': 'notification_message',
                'notification_type': 'game_invitation',
                'message': f'{self.request.user.email} invited you to a game',
                'data': {
                    'invitation_id': invitation.id,
                    'sender_id': self.request.user.id,
                    'sender_email': self.request.user.email
                }
            }
        )
        
        # Also send via WebSocket for direct messages
        async_to_sync(channel_layer.group_send)(
            f'user_{invitation.receiver.id}_dm',
            {
                'type': 'game_invitation',
                'sender_id': self.request.user.id,
                'sender_email': self.request.user.email,
                'invitation_id': invitation.id
            }
        )
        
        return invitation
    
    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        invitation = self.get_object()
        response = request.data.get('response')
        
        if invitation.receiver != request.user:
            return Response(
                {"error": "Not authorized to respond to this invitation"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if response not in ['accepted', 'declined']:
            return Response(
                {"error": "Invalid response"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        invitation.status = response
        invitation.save()
        
        # Notify sender
        async_to_sync(channel_layer.group_send)(
            f'user_{invitation.sender.id}_notifications',
            {
                'type': 'notification_message',
                'notification_type': 'game_invitation_response',
                'message': f'{request.user.email} has {response} your game invitation',
                'data': {
                    'invitation_id': invitation.id,
                    'response': response
                }
            }
        )
        
        serializer = self.get_serializer(invitation)
        return Response(serializer.data)


class DirectMessageViewSet(viewsets.ModelViewSet):
    serializer_class = DirectMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DirectMessage.objects.filter(
            Q(sender=self.request.user) | Q(receiver=self.request.user)
        )
    
    def perform_create(self, serializer):
        # Prevent self-messaging
        if serializer.validated_data['receiver'] == self.request.user:
            raise serializers.ValidationError("You cannot message yourself")
            
        # Check if user is blocked
        receiver = serializer.validated_data['receiver']
        if UserBlock.objects.filter(
            Q(blocker=self.request.user, blocked=receiver) | 
            Q(blocker=receiver, blocked=self.request.user)
        ).exists():
            raise serializers.ValidationError("You cannot message this user due to a block")
            
        dm = serializer.save(sender=self.request.user)
        
        # Send via WebSocket
        async_to_sync(channel_layer.group_send)(
            f'user_{receiver.id}_dm',
            {
                'type': 'direct_message',
                'message': dm.content,
                'sender_id': self.request.user.id,
                'sender_email': self.request.user.email,
                'sender_first_name': self.request.user.first_name,
                'sender_last_name': self.request.user.last_name,
                'dm_id': dm.id,
                'timestamp': dm.timestamp.isoformat()
            }
        )
        
        return dm
    
    @action(detail=False, methods=['get'])
    def conversations(self, request):
        """Get list of users the current user has DM conversations with"""
        # Get unique users from both sent and received messages
        sent_to = DirectMessage.objects.filter(sender=request.user) \
            .values_list('receiver', flat=True).distinct()
        received_from = DirectMessage.objects.filter(receiver=request.user) \
            .values_list('sender', flat=True).distinct()
        
        # Combine and remove duplicates
        user_ids = set(list(sent_to) + list(received_from))
        users = User.objects.filter(id__in=user_ids)
        
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def with_user(self, request):
        """Get direct messages exchanged with a specific user"""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response(
                {"error": "user_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            other_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
            
        messages = DirectMessage.objects.filter(
            (Q(sender=request.user) & Q(receiver=other_user)) |
            (Q(sender=other_user) & Q(receiver=request.user))
        ).order_by('timestamp')
        
        # Mark received messages as read
        unread_messages = messages.filter(receiver=request.user, is_read=False)
        unread_messages.update(is_read=True)
        
        # Pagination
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = DirectMessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = DirectMessageSerializer(messages, many=True)
        return Response(serializer.data)


class UserSearchView(generics.ListAPIView):
    """Search for users by email or name"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if query:
            return User.objects.filter(
                Q(email__icontains=query) | 
                Q(first_name__icontains=query) | 
                Q(last_name__icontains=query)
            ).exclude(id=self.request.user.id)
        return User.objects.none()


# Function for tournament notifications
def notify_users_for_tournament(user_ids, match_details):
    """Send tournament notifications to users"""
    for user_id in user_ids:
        async_to_sync(channel_layer.group_send)(
            f'user_{user_id}_notifications',
            {
                'type': 'notification_message',
                'notification_type': 'tournament_match',
                'message': 'Your tournament match is about to begin',
                'data': match_details
            }
        )