"""The local webhook sender must never follow redirects or send to a remote host."""

from urllib.request import Request

import pytest

from scripts.send_mock_webhook import _NoRedirect, validate_mock_url


def test_loopback_url_only():
    assert (
        validate_mock_url("http://127.0.0.1:5050/typeform/webhook")
        == "http://127.0.0.1:5050/typeform/webhook"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:5050/typeform/webhook",
        "http://localhost:5050/typeform/webhook",
        "http://127.0.0.1:5050@evil.example/typeform/webhook",
        "http://127.0.0.1:5050.evil.example/typeform/webhook",
        "http://127.0.0.1:bad/typeform/webhook",
        "http://127.0.0.1:80/typeform/webhook",
        "http://127.0.0.1:5050/another",
        "http://127.0.0.1:5050/typeform/webhook?token=1",
        "http://127.0.0.1:5050/typeform/webhook#frag",
        "http://127.0.0.1:5050/typeform/webhook%2F",
    ],
)
def test_unsafe_mock_url(url):
    with pytest.raises(ValueError):
        validate_mock_url(url)


def test_mock_sender_does_not_follow_redirects():
    assert (
        _NoRedirect().redirect_request(
            Request("http://127.0.0.1:5050/typeform/webhook"),
            None,
            302,
            "redirect",
            {},
            "https://evil.example/",
        )
        is None
    )
