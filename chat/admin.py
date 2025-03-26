from django.contrib import admin
from .models import Room, Message, UserBlock, GameInvitation, DirectMessage

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_private', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('users',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'room', 'content', 'timestamp', 'is_read')
    list_filter = ('user', 'room', 'timestamp', 'is_read')
    search_fields = ('content', 'user__email')
    date_hierarchy = 'timestamp'

@admin.register(UserBlock)
class UserBlockAdmin(admin.ModelAdmin):
    list_display = ('id', 'blocker', 'blocked', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('blocker__email', 'blocked__email')

@admin.register(GameInvitation)
class GameInvitationAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'status', 'timestamp')
    list_filter = ('status', 'timestamp')
    search_fields = ('sender__email', 'receiver__email')

@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'content', 'timestamp', 'is_read')
    list_filter = ('timestamp', 'is_read')
    search_fields = ('content', 'sender__email', 'receiver__email')
    date_hierarchy = 'timestamp'