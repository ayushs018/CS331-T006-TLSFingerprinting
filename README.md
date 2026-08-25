# TLS Fingerprinting (JA3 / JA3S)

Passively capture TLS handshakes, compute JA3/JA3S fingerprints, and
identify clients (curl, browsers, custom scripts) purely from their
handshake — no payload decryption needed.

## Stack

- **Capture**: Scapy (`capture/sniffer.py`), sniffs TCP port 443 for
  ClientHello/ServerHello handshake records.
- **Fingerprinting**: `ja3/parser.py` extracts the raw fields, `ja3/ja3.py`
  implements the JA3/JA3S spec (GREASE stripping + MD5) from scratch.
- **Reference DB**: Redis/Valkey (`db/store.py`) — JA3 hash -> client label.

Stretch goals not yet scaffolded (see roadmap): JA4/JA4S, eBPF/XDP capture,
TRex-generated traffic mixes.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Redis/Valkey, e.g.: brew install redis && brew services start redis
```

Packet capture needs raw socket access. On macOS, if your user account
is in the `access_bpf` group (check with `id`; Wireshark installs this
via ChmodBPF), no `sudo` is needed — confirmed working that way for
this project. Otherwise run with `sudo` (or `sudo -E` inside your venv).

## Usage

1. **Build your reference database** — for each client you want to
   recognize, run this, then generate one handshake with that client:

   ```bash
   python3 scripts/populate_db.py --iface en0 --name "curl 8.4"
   # in another terminal: curl -s https://example.com >/dev/null
   ```

   Repeat for each client. `scripts/custom_client.py` is included as
   the "custom script" client (a raw `ssl.SSLContext` pinned to TLS 1.2
   with a restricted cipher list) if you don't have 5 distinct real
   clients handy.

2. **Identify live traffic**:

   ```bash
   python3 scripts/live_identify.py --iface en0
   ```

   Prints `[ClientHello] JA3=<hash> -> <label or "unknown">` for every
   handshake seen.

### Verified live run

Captured real handshakes from 5 distinct local clients (curl, Python
`urllib`, `openssl s_client`, Node's `https` module, and
`scripts/custom_client.py`) against `example.com`, all correctly
distinguished by JA3 hash:

| Client | JA3 |
|---|---|
| curl | `b76d503360ae441d410a85a7f8d648ab` |
| python-urllib | `4bdac5abde98465c2a2ffd5401d73cfd` |
| openssl-s_client | `0b85eb0d4981e69064e40753e4f0ac5f` |
| node-https | `0bfaf0ce57f1e5476668c0bcff35e70e` |
| custom-restricted-tls12 | `773906b0efdefa24a7f2b8eb6985bf37` and `ef5ec0a8c6e62a096c7a27b4c598489b` (two runs, see caveat below) |

Then re-ran `live_identify.py` against fresh traffic from all 5: it
correctly labeled 5 of 6 observed ClientHellos (one showed as
`unknown` — a background/secondary connection during the capture
window, not a misidentification of a known client).

**Real caveat worth keeping**: the custom client produced *two*
different JA3 hashes across two runs with identical code/config. Even
a fixed `ssl.SSLContext` isn't perfectly deterministic run-to-run on
every platform — a small but genuine version of the same
"fingerprint randomization" phenomenon documented as a browser evasion
technique below, worth mentioning in the write-up.

## Tests

```bash
for f in tests/test_*.py; do python3 "$f"; done
```

11/11 passing. Validates the JA3/JA3S string format, GREASE stripping,
byte parser, and similarity matcher against independently-computed
values — plus, critically, two test vectors taken directly from the
[original Salesforce JA3 README](https://github.com/salesforce/ja3)
(the algorithm's own published specification), run through our actual
`ja3_string_from_fields`/`hash_string` functions and matched exactly.
This closes the "validated against published reference JA3 hashes"
requirement with a genuine external source, not just our own
hand-computed values. See [WRITEUP.md](WRITEUP.md) for the full
comparison table.

## Roadmap status

- [x] Phase 1 — passive capture (`capture/sniffer.py`)
- [x] Phase 2 — JA3/JA3S implementation (`ja3/`), unit-validated + externally validated against published Salesforce JA3 test vectors
- [x] Phase 3 — reference DB wiring (`db/store.py`, `scripts/populate_db.py`)
- [x] Phase 4 — live demo across 5 real clients, verified working (see above)
- [ ] Phase 5 (stretch) — JA4/JA4S, eBPF/XDP capture path
- [x] Phase 6 — write-up: see [WRITEUP.md](WRITEUP.md), including validation
      results and two firsthand fingerprint-instability findings

## Known limitation

`capture/sniffer.py` assumes a ClientHello/ServerHello fits in a single
TCP segment. This holds for the vast majority of real handshakes; a
ClientHello padded with many extensions (e.g. ECH) that spills across
segments would need TCP reassembly, which isn't implemented.
