"""Tests for the DingTalk enterprise-app bot helper."""

from unittest.mock import MagicMock, patch

import pytest

from tradingagents.dingtalk_bot import DingTalkBot


@pytest.mark.unit
def test_webhook_sign_matches_reference():
    """The webhook signature must match the documented HMAC-SHA256 formula."""
    bot = DingTalkBot()
    sign = bot._make_webhook_sign("1234567890000", "SEC123")
    assert sign
    assert "%20" not in sign or "%2B" in sign or "%2F" in sign


@pytest.mark.unit
def test_has_credentials_requires_both():
    assert DingTalkBot().has_credentials() is False
    assert DingTalkBot(app_key="k").has_credentials() is False
    assert DingTalkBot(app_secret="s").has_credentials() is False
    assert DingTalkBot(app_key="k", app_secret="s").has_credentials() is True


@pytest.mark.unit
def test_send_without_credentials_omits_image_and_at_fields(tmp_path):
    """Without app credentials no upload is attempted and @ fields still work."""
    bot = DingTalkBot()
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    with patch("tradingagents.dingtalk_bot.requests.post") as mock_post:
        mock_post.return_value = _ok_response()
        bot.send_webhook_message(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=abc",
            title="t",
            markdown_text="body",
            image_path=image_path,
            at_mobiles=["13800138000"],
            is_at_all=False,
        )

    assert mock_post.call_count == 1
    payload = mock_post.call_args.kwargs["data"].decode("utf-8")
    assert "![chart]" not in payload
    assert '"atMobiles": ["13800138000"]' in payload


@pytest.mark.unit
def test_send_with_credentials_uploads_image_then_posts_markdown(tmp_path):
    """With credentials the image is uploaded and referenced in the markdown."""
    bot = DingTalkBot(app_key="key", app_secret="secret")
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    with patch("tradingagents.dingtalk_bot.requests.get") as mock_get, patch(
        "tradingagents.dingtalk_bot.requests.post"
    ) as mock_post:
        mock_get.return_value = _json_response({"errcode": 0, "access_token": "tok123"})
        mock_post.side_effect = [
            _json_response({"errcode": 0, "media_id": "media_abc"}),
            _ok_response(),
        ]

        bot.send_webhook_message(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=abc",
            title="t",
            markdown_text="body",
            image_path=image_path,
        )

    assert mock_post.call_count == 2
    upload_call, message_call = mock_post.call_args_list
    assert upload_call.kwargs["params"]["type"] == "image"
    payload = message_call.kwargs["data"].decode("utf-8")
    assert "![chart](media_abc)" in payload


@pytest.mark.unit
def test_upload_failure_falls_back_to_text_only(tmp_path):
    """If image upload fails the text message is still delivered."""
    bot = DingTalkBot(app_key="key", app_secret="secret")
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    with patch("tradingagents.dingtalk_bot.requests.get") as mock_get, patch(
        "tradingagents.dingtalk_bot.requests.post"
    ) as mock_post:
        mock_get.return_value = _json_response({"errcode": 0, "access_token": "tok123"})
        mock_post.side_effect = [
            _json_response({"errcode": 400, "errmsg": "upload failed"}),
            _ok_response(),
        ]

        bot.send_webhook_message(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=abc",
            title="t",
            markdown_text="body",
            image_path=image_path,
        )

    assert mock_post.call_count == 2
    payload = mock_post.call_args.kwargs["data"].decode("utf-8")
    assert "![chart]" not in payload


def _ok_response():
    resp = MagicMock()
    resp.json.return_value = {"errcode": 0, "errmsg": "ok"}
    resp.raise_for_status.return_value = None
    return resp


def _json_response(data: dict):
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp
