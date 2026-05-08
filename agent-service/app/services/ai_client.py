from typing import Optional

import httpx

from app.config.settings import settings


class AIClientError(RuntimeError):
    pass


class DeepSeekChatClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or settings.openai_api_key
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.model_name = model_name or settings.model_name
        self.timeout = timeout or settings.ai_request_timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def reply(self, user_message: str, intent: str, conversation_id: Optional[str]) -> str:
        if not self.is_configured:
            raise AIClientError("OPENAI_API_KEY is not configured")

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an enterprise customer service AI assistant. "
                        "Reply in concise, helpful Chinese. Ask for missing order "
                        "numbers when needed. Do not invent order status, logistics, "
                        "refund progress, or account data."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Conversation ID: {conversation_id or 'new'}\n"
                        f"Detected intent: {intent}\n"
                        f"Customer message: {user_message}"
                    ),
                },
            ],
            "temperature": 0.3,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIClientError(str(exc)) from exc

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError("AI response did not include a chat message") from exc

        return content.strip()


deepseek_client = DeepSeekChatClient()
