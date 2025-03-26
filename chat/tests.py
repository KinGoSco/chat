from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Room, Message, UserBlock, DirectMessage, GameInvitation

User = get_user_model()

class ChatTests(TestCase):
    def setUp(self):
        # Créer des utilisateurs de test
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='password123',
            first_name='User',
            last_name='One',
            is_active=True
        )
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='password123',
            first_name='User',
            last_name='Two',
            is_active=True
        )
        
        # Créer un client API
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)
        
        # Créer un salon de chat
        self.room = Room.objects.create(name='test-room')
        self.room.users.add(self.user1, self.user2)
    
    def test_room_creation(self):
        """Test la création d'un salon de chat"""
        data = {'name': 'new-room', 'is_private': False}
        response = self.client.post(reverse('room-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Room.objects.count(), 2)
        # Vérifier que l'utilisateur actuel est ajouté au salon
        new_room = Room.objects.get(name='new-room')
        self.assertTrue(new_room.users.filter(id=self.user1.id).exists())
    
    def test_sending_message(self):
        """Test l'envoi d'un message dans un salon"""
        url = reverse('messages-by-room', kwargs={'room_pk': self.room.id})
        data = {'content': 'Hello, world!'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Message.objects.count(), 1)
        message = Message.objects.first()
        self.assertEqual(message.content, 'Hello, world!')
        self.assertEqual(message.user, self.user1)
        self.assertEqual(message.room, self.room)
    
    def test_user_blocking(self):
        """Test le blocage d'un utilisateur"""
        data = {'blocked_id': self.user2.id}
        response = self.client.post(reverse('userblock-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserBlock.objects.count(), 1)
        self.assertTrue(UserBlock.objects.filter(blocker=self.user1, blocked=self.user2).exists())
    
    def test_direct_messaging(self):
        """Test l'envoi d'un message direct"""
        data = {'receiver_id': self.user2.id, 'content': 'Hello directly!'}
        response = self.client.post(reverse('directmessage-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DirectMessage.objects.count(), 1)
        dm = DirectMessage.objects.first()
        self.assertEqual(dm.content, 'Hello directly!')
        self.assertEqual(dm.sender, self.user1)
        self.assertEqual(dm.receiver, self.user2)
    
    def test_game_invitation(self):
        """Test l'envoi d'une invitation de jeu"""
        data = {'receiver_id': self.user2.id}
        response = self.client.post(reverse('gameinvitation-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GameInvitation.objects.count(), 1)
        invitation = GameInvitation.objects.first()
        self.assertEqual(invitation.sender, self.user1)
        self.assertEqual(invitation.receiver, self.user2)
        self.assertEqual(invitation.status, 'pending')