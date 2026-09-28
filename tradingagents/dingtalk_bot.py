"""DingTalk enterprise-app bot helpers.

Wraps the DingTalk OpenAPI image-upload flow and the custom-group-webhook
markdown delivery so that ``analyze`` can attach a chart screenshot to its
report notification.

Environment variables used:
    DINGTALK_APP_KEY        AppKey for the DingTalk enterprise application.
    DINGTALK_APP_SECRET     AppSecret for the DingTalk enterprise application.
    DINGTALK_WEBHOOK_URL    Existing custom robot webhook URL.
    DINGTALK_WEBHOOK_SECRET Optional signing secret for the webhook.
"""

import base64
import hashlib
import hmac
import json
import mimetypes
import time
import urllib.parse
from pathlib import Path

import requests


class DingTalkBot:
    """Upload images via DingTalk OpenAPI and send markdown via webhook."""

    def __init__(self, app_key: str | None = None, app_secret: str | None = None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token: str | None = None
        self.base_url = "https://oapi.dingtalk.com"

    def has_credentials(self) -> bool:
        return bool(self.app_key and self.app_secret)

    def get_access_token(self) -> str:
        """Fetch and cache an access_token from app credentials."""
        if not self.has_credentials():
            raise RuntimeError("DINGTALK_APP_KEY and DINGTALK_APP_SECRET are required")

        url = f"{self.base_url}/gettoken"
        params = {"appkey": self.app_key, "appsecret": self.app_secret}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get("errcode") != 0:
            raise RuntimeError(f"DingTalk gettoken error: {result}")

        self.access_token = result["access_token"]
        return self.access_token

    def upload_image(self, image_path: str | Path) -> str:
        """Upload a local image and return its DingTalk media_id."""
        if not self.access_token:
            self.get_access_token()

        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        url = f"{self.base_url}/media/upload"
        params = {"access_token": self.access_token, "type": "image"}

        mime_type, _ = mimetypes.guess_type(str(image_path))
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/png"

        with open(image_path, "rb") as f:
            files = {"media": (image_path.name, f, mime_type)}
            response = requests.post(url, params=params, files=files, timeout=60)
        response.raise_for_status()
        result = response.json()
        if result.get("errcode") != 0:
            raise RuntimeError(f"DingTalk media/upload error: {result}")
        return result["media_id"]

    def send_webhook_message(
        self,
        webhook_url: str,
        title: str,
        markdown_text: str,
        image_path: str | Path | None = None,
        webhook_secret: str | None = None,
        at_mobiles: list[str] | None = None,
        is_at_all: bool = False,
    ) -> bool:
        """Send a markdown message, optionally embedding an uploaded image.

        If ``image_path`` is provided and app credentials are configured, the
        image is uploaded first and referenced in the markdown body.  Any
        upload failure is logged and the text message is still sent.
        """
        media_id: str | None = None
        if image_path and self.has_credentials():
            try:
                media_id = self.upload_image(image_path)
            except Exception as exc:  # pragma: no cover - best-effort fallback
                print(f"⚠️ DingTalk image upload failed, sending text only: {exc}")

        timestamp = str(int(time.time() * 1000))
        url = webhook_url
        if webhook_secret:
            sign = self._make_webhook_sign(timestamp, webhook_secret)
            url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

        text = markdown_text
        if media_id:
            text = f"{markdown_text}\n\n![chart]({media_id})"

        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
            "at": {
                "atMobiles": at_mobiles or [],
                "isAtAll": is_at_all,
            },
        }

        response = requests.post(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("errcode") != 0:
            raise RuntimeError(f"DingTalk webhook error: {result}")
        return True

    @staticmethod
    def _make_webhook_sign(timestamp: str, secret: str) -> str:
        """Generate the webhook signing token used by custom DingTalk robots."""
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return urllib.parse.quote_plus(base64.b64encode(hmac_code))


def get_bot_from_env() -> DingTalkBot:
    """Create a bot from environment variables."""
    import os

    return DingTalkBot(
        app_key=os.environ.get("DINGTALK_APP_KEY"),
        app_secret=os.environ.get("DINGTALK_APP_SECRET"),
    )
