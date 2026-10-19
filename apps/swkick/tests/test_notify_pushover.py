import httpx

from app.notify import PushoverNotifier


def test_posts_expected_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"status": 1})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    PushoverNotifier("TOK", "USR", client=client).send("Title!", "Body!")

    assert captured["url"] == PushoverNotifier.API
    assert "token=TOK" in captured["body"]
    assert "user=USR" in captured["body"]
    assert "Title" in captured["body"]
