import json

import httpx
import pytest

from app.core.errors import ProviderError
from app.providers.channels.whatsapp_service import WhatsAppService
from app.providers.voice.omnidim import OmniDimClient


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_dispatch_posts_the_call_and_returns_the_request_id():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        body = {"success": True, "status": "dispatched", "requestId": 3166940}
        return httpx.Response(200, json=body)

    request_id = OmniDimClient(_client(handler), "key-1").dispatch(
        agent_id=158910, to_number="+6436881234", from_number_id=23,
        call_context={"job_title": "Data Engineer"}, metadata={"app_call_id": "c1"},
    )

    assert request_id == "3166940"
    assert seen["url"] == "https://omnidim.io/api/v1/calls/dispatch"
    assert seen["auth"] == "Bearer key-1"
    assert seen["body"] == {
        "agent_id": 158910, "to_number": "+6436881234", "from_number_id": 23,
        "call_context": {"job_title": "Data Engineer"}, "metadata": {"app_call_id": "c1"},
    }


def test_a_refused_key_is_reported_plainly():
    client = _client(lambda request: httpx.Response(401, json={"error": "unauthorized"}))

    with pytest.raises(ProviderError, match="API key was refused"):
        OmniDimClient(client, "bad").dispatch(agent_id=1, to_number="+6436881234")


def test_find_log_matches_our_call_id_across_pages():
    pages = {
        "1": [{"id": 1, "metadata": {"app_call_id": "other"}}],
        "2": [{"id": 2, "metadata": {"app_call_id": "c1"}, "call_status": "completed"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/calls/logs"
        assert request.url.params["agentid"] == "158910"
        rows = pages.get(request.url.params["pageno"], [])
        return httpx.Response(200, json={"call_log_data": rows, "total_records": 2})

    client = OmniDimClient(_client(handler), "key-1")
    assert client.find_log(agent_id=158910, app_call_id="c1")["id"] == 2
    assert client.find_log(agent_id=158910, app_call_id="missing") is None


def test_whatsapp_service_posts_to_your_own_number():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    WhatsAppService(_client(handler), "http://127.0.0.1:3000/send", "tok",
                    to_field="number", text_field="text").send("+64224379369", "Hello")

    assert seen == {"auth": "Bearer tok", "body": {"number": "+64224379369", "text": "Hello"}}


def test_whatsapp_service_errors_are_reported():
    client = _client(lambda request: httpx.Response(500, text="down"))

    with pytest.raises(ProviderError, match="HTTP 500"):
        WhatsAppService(client, "http://127.0.0.1:3000/send", "").send("+64224379369", "Hi")


def test_whatsapp_service_status_and_logout_use_the_same_address():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), request.headers.get("Authorization")))
        if request.url.path == "/status":
            return httpx.Response(200, json={"state": "qr", "qr": "data:image/png;base64,AA",
                                              "me": None, "error": None})
        return httpx.Response(200, json={"ok": True})

    service = WhatsAppService(_client(handler), "http://127.0.0.1:3010/send", "tok")

    assert service.status()["state"] == "qr"
    service.logout()
    assert seen == [("GET", "http://127.0.0.1:3010/status", "Bearer tok"),
                    ("POST", "http://127.0.0.1:3010/logout", "Bearer tok")]


def test_a_stopped_whatsapp_service_is_reported():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ProviderError, match="did not answer"):
        WhatsAppService(_client(handler), "http://127.0.0.1:3010/send").status()
