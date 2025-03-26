from rest_framework import serializers
from .models import Room, Message, UserBlock, GameInvitation, DirectMessage
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'is_active']

class MessageSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'user', 'content', 'timestamp', 'is_read']

class RoomSerializer(serializers.ModelSerializer):
    users = UserSerializer(many=True, read_only=True)
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Room
        fields = ['id', 'name', 'users', 'messages', 'is_private', 'created_at']

class UserBlockSerializer(serializers.ModelSerializer):
    blocker = UserSerializer(read_only=True)
    blocked = UserSerializer(read_only=True)
    
    blocked_id = serializers.PrimaryKeyRelatedField(
        write_only=True, 
        queryset=User.objects.all(),
        source='blocked'
    )

    class Meta:
        model = UserBlock
        fields = ['id', 'blocker', 'blocked', 'blocked_id', 'timestamp']

class GameInvitationSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)
    
    receiver_id = serializers.PrimaryKeyRelatedField(
        write_only=True, 
        queryset=User.objects.all(),
        source='receiver'
    )

    class Meta:
        model = GameInvitation
        fields = ['id', 'sender', 'receiver', 'receiver_id', 'timestamp', 'status']

class DirectMessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)
    
    receiver_id = serializers.PrimaryKeyRelatedField(
        write_only=True, 
        queryset=User.objects.all(),
        source='receiver'
    )

    class Meta:
        model = DirectMessage
        fields = ['id', 'sender', 'receiver', 'receiver_id', 'content', 'timestamp', 'is_read']