import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import (AsyncJsonWebsocketConsumer,
                                        JsonWebsocketConsumer)


class SubmissionConsumer(JsonWebsocketConsumer):
    groups = ['submissions']

    def connect(self):
        self.accept()

    def disconnect(self, close_code):
        # Leave room group
        pass

    def receive(self, text_data):
        message = json.loads(text_data)

        # Send message to room group
        async_to_sync(
            self.channel_layer.group_send(
                self.group_name, message,
            ),
        )

    def done_submission(self, event):
        self.send_json({
            "type": "done-submission",
            "message": event['message'],
        })

    def update_submission(self, event):
        self.send_json({
            "type": "update-submission",
            "message": event['message'],
        })


class DetailSubmission(JsonWebsocketConsumer):
    def connect(self):
        key = self.scope['url_route']['kwargs']['key']
        self.room_group_name = 'sub_%s' % key

        # Join room group
        async_to_sync(
            self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name,
            ),
        )

        self.accept()

    def disconnect(self, close_code):
        # Leave room group
        async_to_sync(
            self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            ),
        )

    def receive(self, text_data):
        message = json.loads(text_data)

        # Send message to room group
        async_to_sync(
            self.channel_layer.group_send(
                self.room_group_name, message,
            ),
        )

    def compile_message(self, event):
        self.send_json({
            "type": "compile-message",
        })

    def compile_error(self, event):
        self.send_json({
            "type": "compile-error",
            "message": event['message'],
        })

    def internal_error(self, event):
        self.send_json({
            "type": "internal-error",
        })

    def aborted_submission(self, event):
        self.send_json({
            "type": "aborted-submission",
        })

    def test_case(self, event):
        self.send_json({
            "type": "test-case",
            "message": event['message'],
        })

    def grading_begin(self, event):
        self.send_json({
            "type": "grading-begin",
        })

    def grading_end(self, event):
        self.send_json({
            "type": "grading-end",
            "message": event['message'],
        })

    def processing(self, event):
        self.send_json({
            "type": "processing",
        })


class AsyncSubmissionConsumer(AsyncJsonWebsocketConsumer):
    groups = ['async_submissions']

    async def send(self, *args, **kwargs):
        await super().send(*args, **kwargs)

    async def done_submission(self, event):
        await self.send_json({
            "type": "done-submission",
            "message": event['message'],
        })

    async def update_submission(self, event):
        await self.send_json({
            "type": "update-submission",
            "message": event['message'],
        })


class AsyncDetailSubmission(AsyncJsonWebsocketConsumer):
    async def connect(self):
        key = self.scope['url_route']['kwargs']['key']
        self.room_group_name = 'async_sub_%s' % key

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

    async def compile_message(self, event):
        await self.send_json({
            "type": "compile-message",
        })

    async def compile_error(self, event):
        await self.send_json({
            "type": "compile-error",
            "message": event['message'],
        })

    async def internal_error(self, event):
        await self.send_json({
            "type": "internal-error",
        })

    async def aborted_submission(self, event):
        await self.send_json({
            "type": "aborted-submission",
        })

    async def test_case(self, event):
        await self.send_json({
            "type": "test-case",
            "message": event['message'],
        })

    async def grading_begin(self, event):
        await self.send_json({
            "type": "grading-begin",
        })

    async def grading_end(self, event):
        await self.send_json({
            "type": "grading-end",
            "message": event['message'],
        })

    async def processing(self, event):
        await self.send_json({
            "type": "processing",
        })
