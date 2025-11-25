import json

from core.handle.textMessageHandlerRegistry import TextMessageHandlerRegistry

TAG = __name__


class TextMessageProcessor:
    """Main message processor class"""

    def __init__(self, registry: TextMessageHandlerRegistry):
        self.registry = registry

    async def process_message(self, conn, message: str) -> None:
        """Main entry point for processing messages"""
        try:
            # Parse JSON message
            msg_json = json.loads(message)

            # Process JSON message
            if isinstance(msg_json, dict):
                message_type = msg_json.get("type")

                # Log message
                conn.logger.bind(tag=TAG).info(f"Received {message_type} message: {message}")

                # Get and execute handler
                handler = self.registry.get_handler(message_type)
                if handler:
                    await handler.handle(conn, msg_json)
                else:
                    conn.logger.bind(tag=TAG).error(f"Received unknown message type: {message}")
            # Process pure numeric message
            elif isinstance(msg_json, int):
                conn.logger.bind(tag=TAG).info(f"Received numeric message: {message}")
                await conn.websocket.send(message)

        except json.JSONDecodeError:
            # Non-JSON messages are forwarded directly
            conn.logger.bind(tag=TAG).error(f"Failed to parse message: {message}")
            await conn.websocket.send(message)
