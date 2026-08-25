#!/usr/bin/env python3
"""A deliberately custom TLS client: restricts cipher suites and pins
TLS 1.2, so its JA3 fingerprint is clearly distinct from any default
library configuration (curl/urllib/openssl/node all differ from each
other already, but only because of *their* defaults — this one is
custom on purpose, matching the "custom scripts" category the PS
asks the demo to distinguish).

Usage:
    python3 scripts/custom_client.py [host]
"""
from __future__ import annotations

import socket
import ssl
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "example.com"

context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.minimum_version = ssl.TLSVersion.TLSv1_2
context.maximum_version = ssl.TLSVersion.TLSv1_2
context.set_ciphers("ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384")
# Only the ClientHello shape matters for this fingerprinting demo, not
# actual trust validation, and this interpreter's CA bundle isn't set up.
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

with socket.create_connection((HOST, 443), timeout=5) as sock:
    with context.wrap_socket(sock, server_hostname=HOST) as tls:
        print(f"Connected: {tls.version()}, cipher={tls.cipher()[0]}")
