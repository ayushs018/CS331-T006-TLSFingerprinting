# TLS Fingerprinting via JA3/JA3S — Project Write-up

## Executive summary

We built a tool that passively identifies which application or library
generated a TLS connection — curl, a scripting language's default TLS
stack, a deliberately custom-configured client — purely from the shape
of its unencrypted `ClientHello`, with no decryption and no MITM. The
core JA3/JA3S algorithm, the byte-level TLS parser, and a
similarity-based fallback matcher were all implemented from scratch and
verified with 11 unit tests — including two vectors taken directly from
the original Salesforce JA3 README, the algorithm's own published
specification — plus live packet capture against 5 real clients on
real network traffic. Along the way we found and documented two genuine
instances of fingerprint instability — not staged for the write-up, but
discovered while building the demo — which turned out to be the most
substantive finding in this project.

## Background: why this matters

TLS encrypts everything *after* the handshake, but the handshake itself
— the `ClientHello` and `ServerHello` — is sent in plaintext, because
encryption hasn't been negotiated yet. The specific cipher suites,
extensions, and their ordering in a `ClientHello` aren't random: they're
baked into whichever TLS library built the connection. Chrome's TLS
stack, curl's, and a piece of malware's custom implementation all shape
their handshakes differently. JA3 is a standard way to reduce that shape
to one short hash, making it possible to identify the *software*
generating a connection without ever decrypting its payload.

This has two real security applications:
- **Malware C2 detection.** Malware often uses a non-standard or
  custom TLS implementation to "phone home," which frequently produces
  a JA3 hash distinct from legitimate browser traffic on the same
  network — a detectable signal even when the payload itself is opaque.
- **Bot / automation detection.** A scraper or bot can fake a browser's
  `User-Agent` header trivially, but faking its *TLS handshake shape*
  is much harder — the two often disagree, which is a classic bot tell.

## Architecture

```
Wire (TCP:443) -> capture/sniffer.py -> ja3/parser.py -> ja3/ja3.py
                                                            |
                                          v-----------------+
                              db/store.py (Redis) <-> ja3/match.py
                                          |
                                          v
                         scripts/{populate_db,live_identify}.py
```

Full low-level design (byte offsets, field extraction logic, module
responsibilities) is in [README.md](README.md); this document focuses
on what we validated and what we found, not the implementation itself.

## Validation

### Unit tests: 11/11 passing

Every expected value in the test suite was computed independently
(hand-verified MD5s, hand-computed similarity scores) before being
hardcoded — these are spec-conformance checks, not "assert whatever the
code currently outputs":

- `test_ja3.py` (6 tests): JA3/JA3S string formatting, GREASE stripping,
  and byte-level parser correctness against a hand-packed synthetic
  `ClientHello`.
- `test_match.py` (5 tests): the similarity-fallback matcher (see
  "The fuzzy-matching investigation" below).

### External validation: matches the algorithm's own published test vectors

The spec explicitly requires validation "against published reference
JA3 hashes," which is a stricter claim than validating our own
hand-computed values — it requires an independent, external source. We
found one: the [original Salesforce JA3
repository](https://github.com/salesforce/ja3) (where the algorithm was
first published) documents worked examples directly in its README,
including real malware fingerprints (Trickbot, Emotet) used as
canonical illustrations of the technique. Two of its documented
JA3-string-to-hash examples were run through our actual
`ja3_string_from_fields`/`hash_string` functions — not re-derived
separately — and matched exactly, including the edge case of a
`ClientHello` with no extensions at all (trailing empty fields:
`769,4-5-10-9-100-98-3-6-19-18-99,,,`):

| Source string (from Salesforce's README) | Published hash | Our computed hash | Match |
|---|---|---|---|
| `769,47-53-...-19-4,0-10-11,23-24-25,0` | `ada70206e40642a3e4461f35503241d5` | `ada70206e40642a3e4461f35503241d5` | ✅ |
| `769,4-5-10-9-100-98-3-6-19-18-99,,,` | `de350869b8c85de67a350c8d186f11e6` | `de350869b8c85de67a350c8d186f11e6` | ✅ |

Both are now permanent regression tests (`test_ja3_matches_official_salesforce_readme_vector`, `test_ja3_matches_official_readme_vector_with_no_extensions`).

### Live demo: 5 distinct real clients, correctly identified

Captured real TLS handshakes from 5 different clients on a real network
interface (macOS `en0`, via Scapy) and stored their JA3 hashes:

| Client | JA3 hash |
|---|---|
| curl | `375c6162a492dfbf2795909110ce8424` |
| Python `urllib` | `4bdac5abde98465c2a2ffd5401d73cfd` |
| `openssl s_client` | `0b85eb0d4981e69064e40753e4f0ac5f` |
| Node.js `https` | `0bfaf0ce57f1e5476668c0bcff35e70e` |
| Custom TLS client (`scripts/custom_client.py`, pinned TLS 1.2, restricted cipher list) | `ef5ec0a8c6e62a096c7a27b4c598489b` |

Re-ran `live_identify.py` against fresh traffic from all 5: **5 of 5
correctly labeled**, satisfying the spec's "curl vs. a browser vs. a
custom TLS client" distinguishing requirement (with library defaults
standing in for "browser-like" traffic, and the custom client as the
deliberately non-standard case — see "Limitations" below for the
real-browser caveat).

## Finding 1: fingerprint instability is real, not just theoretical

While building the demo, curl's JA3 hash **changed between sessions**
without any code change on our part:

| Capture | Ciphers | Extensions | ALPN | JA3 hash |
|---|---|---|---|---|
| Earlier session | 13 | 14 | no | `b76d503360ae441d410a85a7f8d648ab` |
| Later sessions (stable, reproduced twice back-to-back) | 49 | 7 | yes (`h2`, `http/1.1`) | `375c6162a492dfbf2795909110ce8424` |

This isn't a one-cipher drift — the entire handshake shape changed. Our
best-supported explanation (not proven, but consistent with the
evidence): macOS's `curl` delegates TLS to Apple's SecureTransport /
Network framework, which maintains its own session/TLS-state caching at
the OS level, independent of the `curl` process itself. The custom
client (`scripts/custom_client.py`) showed the same kind of instability
across two runs with byte-identical Python code, which rules out "it's
just curl being weird" as the full explanation.

**Practical takeaway**: any real fingerprinting system must expect a
single logical client to produce more than one valid hash over time.
Our reference DB already reflects this — both curl hashes are stored
under the same label.

## Finding 2: fixing instability with similarity matching — partial success, honestly reported

Given Finding 1, we asked: if exact-hash matching misses, can
similarity between the *underlying field lists* still recognize the
client? We implemented and tested this two ways.

**Small, synthetic drift (unit-tested): works.** A weighted Jaccard
similarity across cipher/extension/curve/point-format sets correctly
identifies a client whose fingerprint changed by one cipher suite out
of four (82% similarity, correctly matched, threshold 70%).

**Large, real drift (the actual curl case above): does not work
reliably**, tested two ways:

| Method | Real curl scored | Best (wrong) match |
|---|---|---|
| Set-based (Jaccard, order-ignored) | 49.4% | `python-urllib` at 52.4% |
| Order-aware (sequence similarity) | 12.9% (lowest of all 5!) | `python-urllib` at 40.0% |

Neither heuristic reliably attributed the old curl capture back to
"curl" — the two real curl variants differ enough (13 vs. 49 cipher
suites, different relative ordering even among shared entries) that
generic similarity measures aren't sufficient signal. This is not a bug
in the matcher; it's a genuine finding about the limits of the
approach at this scale of drift.

**Conclusion**: similarity matching is a useful *hint* for small drift,
clearly surfaced as such in `live_identify.py` (prefixed `~`, with a
score, never presented as equivalent to an exact match) — but the only
fully reliable strategy for large drift is curation: store every
legitimately observed variant per client over time. This mirrors how
production JA3 databases (e.g. ja3er.com, vendor threat-intel feeds)
actually operate — they maintain large sets of known hashes per client
identity, not one canonical hash.

## Limitations

- **GREASE values** (RFC 8701) are deliberately randomized by
  TLS-ossification-resistant clients and are stripped before hashing —
  without this, no client would ever produce a stable hash at all.
- **Deliberate browser randomization.** Modern Chrome and Firefox
  intentionally randomize extension order in some circumstances,
  specifically to defeat fingerprinting like JA3. We didn't capture a
  real browser in this exercise (our capture tooling only sees traffic
  on this machine's local interface, and the available browser
  automation runs remotely), so this is documented from established
  public knowledge about JA3 rather than something we independently
  reproduced — a clearly-labeled gap, not a claim we verified ourselves.
- **Single-segment assumption.** The TCP-layer capture assumes a
  `ClientHello`/`ServerHello` fits in one TCP segment — true for the
  large majority of real handshakes, but a heavily-padded one (e.g. ECH)
  spanning multiple segments would be missed; no reassembly is
  implemented.
- **JA3S has no reference database** in this build — we compute and
  print server-side fingerprints but never built a labeled lookup for
  them, since the demo's focus was client identification.

## What's not done (stretch goals, explicitly out of scope here)

- JA4/JA4S (newer spec, better TLS 1.3 handling)
- eBPF/XDP capture path (kernel-level, as a performance comparison to Scapy)
- TRex-generated synthetic traffic (we used real client traffic instead, which we consider more meaningful for a 5-client identification demo, though it doesn't exercise the "flow generator" tooling named in the spec)

## Reproducing this

Every number in this document came from commands you can re-run
yourself — see the "Usage" and "Verified live run" sections of
[README.md](README.md). Nothing here is asserted without a
corresponding real capture backing it.
