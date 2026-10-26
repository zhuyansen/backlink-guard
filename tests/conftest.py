"""The guards every test runs under: a state folder of its own, no keys, and no network.

A test that reaches the network fails at once and names the host, instead of calling a paid API with a test key or
hanging on a proxy. pytest.fail raises a BaseException, which no `except Exception` or `except OSError` in the code
swallows. When it fires, stub the source the test reached; do not turn the guard off.
"""
import socket

import pytest

from backlink_guard import vet


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKLINK_GUARD_STATE", str(tmp_path))
    for name in ("GOANYAPI_API_KEY", "AISA_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(vet.aisa, "key", lambda: "")
    monkeypatch.setattr(vet.signals, "entity", lambda domain: "")        # no call to Google in tests
    monkeypatch.setattr(vet.blocklist, "load", lambda fresh=False: {})    # nor to GitHub for the shared list


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def lookup(host, *args, **kwargs):
        pytest.fail(f"reached the network ({host})")

    def connect(sock, address):
        pytest.fail(f"reached the network ({address})")
    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    monkeypatch.setattr(socket.socket, "connect", connect)
