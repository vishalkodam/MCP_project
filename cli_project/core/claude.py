from collections.abc import Callable

from anthropic import Anthropic
from anthropic.types import Message


class Claude:
    def __init__(self, model: str):
        self.client = Anthropic()
        self.model = model

    def add_user_message(self, messages: list, message):
        user_message = {
            "role": "user",
            "content": message.content if isinstance(message, Message) else message,
        }
        messages.append(user_message)

    def add_assistant_message(self, messages: list, message):
        assistant_message = {
            "role": "assistant",
            "content": message.content if isinstance(message, Message) else message,
        }
        messages.append(assistant_message)

    def text_from_message(self, message: Message):
        return "\n".join([block.text for block in message.content if block.type == "text"])

    def _request_params(
        self,
        messages,
        system=None,
        temperature=1.0,
        stop_sequences=[],
        tools=None,
        thinking=False,
        thinking_budget=1024,
    ):
        params = {
            "model": self.model,
            "max_tokens": 8000,
            "messages": messages,
            "temperature": temperature,
            "stop_sequences": stop_sequences,
        }

        if thinking:
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }

        if tools:
            params["tools"] = tools

        if system:
            params["system"] = system

        return params

    def chat(
        self,
        messages,
        system=None,
        temperature=1.0,
        stop_sequences=[],
        tools=None,
        thinking=False,
        thinking_budget=1024,
    ) -> Message:
        message = self.client.messages.create(
            **self._request_params(
                messages,
                system=system,
                temperature=temperature,
                stop_sequences=stop_sequences,
                tools=tools,
                thinking=thinking,
                thinking_budget=thinking_budget,
            )
        )
        return message

    def chat_stream(
        self,
        messages,
        system=None,
        temperature=1.0,
        stop_sequences=[],
        tools=None,
        thinking=False,
        thinking_budget=1024,
        on_token: Callable[[str], None] | None = None,
    ) -> Message:
        """Stream the reply token-by-token, calling ``on_token`` per text delta.

        Returns the final assembled ``Message`` — identical in shape to what
        :meth:`chat` returns — so tool-use handling and history bookkeeping
        work unchanged.
        """
        params = self._request_params(
            messages,
            system=system,
            temperature=temperature,
            stop_sequences=stop_sequences,
            tools=tools,
            thinking=thinking,
            thinking_budget=thinking_budget,
        )

        with self.client.messages.stream(**params) as stream:
            for text in stream.text_stream:
                if on_token is not None:
                    on_token(text)
            return stream.get_final_message()
