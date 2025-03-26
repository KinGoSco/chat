# Utilitaires de notification pour le système de tournois

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

channel_layer = get_channel_layer()

def send_tournament_notification(user_ids, match_details):
    """
    Envoie une notification de tournoi aux utilisateurs spécifiés
    
    Args:
        user_ids (list): Liste d'IDs utilisateurs à notifier
        match_details (dict): Détails du match à inclure dans la notification
    """
    for user_id in user_ids:
        async_to_sync(channel_layer.group_send)(
            f'user_{user_id}_notifications',
            {
                'type': 'notification_message',
                'notification_type': 'tournament_match',
                'message': 'Votre prochain match va commencer bientôt',
                'data': match_details
            }
        )

def send_chat_notification_to_room(room_name, notification_type, message, data=None):
    """
    Envoie une notification à tous les utilisateurs dans un salon de chat
    
    Args:
        room_name (str): Nom du salon
        notification_type (str): Type de notification
        message (str): Message à afficher
        data (dict, optional): Données supplémentaires
    """
    if data is None:
        data = {}
    
    async_to_sync(channel_layer.group_send)(
        f'chat_{room_name}',
        {
            'type': 'tournament_notification',
            'notification_type': notification_type,
            'message': message,
            'match_details': data
        }
    )

def send_direct_notification(user_id, notification_type, message, data=None):
    """
    Envoie une notification directe à un utilisateur spécifique
    
    Args:
        user_id (int): ID de l'utilisateur
        notification_type (str): Type de notification
        message (str): Message à afficher
        data (dict, optional): Données supplémentaires
    """
    if data is None:
        data = {}
    
    async_to_sync(channel_layer.group_send)(
        f'user_{user_id}_notifications',
        {
            'type': 'notification_message',
            'notification_type': notification_type,
            'message': message,
            'data': data
        }
    )