"""Passive TLS handshake capture using Scapy.

Extracts raw ClientHello/ServerHello handshake bytes from TCP port 443
traffic. Limitation: assumes the handshake message fits in a single TCP
segment, true for the vast majority of ClientHellos/ServerHellos; TCP
segment reassembly is not implemented.
"""
from __future__ import annotations

from typing import Callable, Optional

from scapy.all import sniff
from scapy.layers.inet import TCP

CONTENT_TYPE_HANDSHAKE = 0x16
HANDSHAKE_TYPE_CLIENT_HELLO = 0x01
HANDSHAKE_TYPE_SERVER_HELLO = 0x02


def _handshake_type(raw: bytes) -> Optional[int]:
    if len(raw) < 6 or raw[0] != CONTENT_TYPE_HANDSHAKE:
        return None
    return raw[5]


def capture(
    iface: Optional[str],
    on_client_hello: Callable[[bytes], None],
    on_server_hello: Callable[[bytes], None],
    count: int = 0,
) -> None:
    def _process(pkt) -> None:
        if not pkt.haslayer(TCP) or not pkt.haslayer("Raw"):
            return
        raw = bytes(pkt["Raw"].load)
        htype = _handshake_type(raw)
        if htype == HANDSHAKE_TYPE_CLIENT_HELLO:
            on_client_hello(raw)
        elif htype == HANDSHAKE_TYPE_SERVER_HELLO:
            on_server_hello(raw)

    sniff(iface=iface, filter="tcp port 443", prn=_process, store=False, count=count)
