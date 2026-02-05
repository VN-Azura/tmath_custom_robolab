import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class TicketConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_name = 'tickets'
        self.room_group_name = 'tickets'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        message = json.loads(text_data)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name, message,
        )

    async def ticket_message(self, event):
        await self.send_json({
            "type": "ticket-message",
            "message": event['message'],
        })

    async def ticket_status(self, event):
        await self.send_json({
            "type": "ticket-status",
            "message": event['message'],
        })


class DetailTicketConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        id = self.scope['url_route']['kwargs']['id']
        # self.room_name = 'ticket'
        self.room_group_name = 'ticket-%d' % id

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        message = json.loads(text_data)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name, message,
        )

    async def ticket_message(self, event):
        await self.send_json({
            "type": "ticket-message",
            "message": event['message'],
        })

    async def ticket_status(self, event):
        await self.send_json({
            "type": "ticket-status",
            "message": event['message'],
        })
