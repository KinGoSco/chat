from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'rooms', views.RoomViewSet, basename='room')
router.register(r'room-messages', views.MessageViewSet, basename='message')
router.register(r'blocks', views.UserBlockViewSet, basename='userblock')
router.register(r'game-invitations', views.GameInvitationViewSet, basename='gameinvitation')
router.register(r'direct-messages', views.DirectMessageViewSet, basename='directmessage')

urlpatterns = [
    path('', include(router.urls)),
    path('users/search/', views.UserSearchView.as_view(), name='user-search'),
    path('messages-by-room/<int:room_pk>/', views.MessageViewSet.as_view({'get': 'list', 'post': 'create'}), name='messages-by-room'),
]