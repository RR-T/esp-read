# Hardware spec sheet — XIAO ESP32-S3 Plus reader

Living record of measured performance, to size future firmware work. Fill in the
`TBD` rows as each benchmark runs. Sources:
- **epub** = `firmware/epub-benchmark/` (CPU/memory/render/image/inflate; no WiFi)
- **wifi** = `firmware/wifi-benchmark/` (connect/NTP/HTTP/HTTPS; needs U.FL antenna)
- **meter** = external instrument (multimeter / PPK2) — firmware can't self-measure current
- **panel** = needs the e-paper wired
- **sd** = needs storage wired

## Board
| Spec | Value | Source |
|---|---|---|
| MCU | ESP32-S3, dual LX7 @240 MHz | epub ✓ |
| PSRAM | **8.0 MB OPI** detected, ~7.9 MB free (`qio_opi`) | epub ✓ |
| Flash | 16 MB | epub ✓ |
| Internal SRAM free (idle) | ~350 KB | epub ✓ |

## CPU / memory
| Metric | Value | Source |
|---|---|---|
| Page render (paginate+rasterise 1 pg) | **11.5 ms** | epub ✓ |
| Pagination | **~1 ms/page** (20 pp in 19 ms) | epub ✓ |
| Strip tags | 8 ms / 28 KB | epub ✓ |
| JPEG decode+dither 480×320 | **82 ms** | epub ✓ |
| JPEG decode+dither 240×240 | **32 ms** | epub ✓ |
| Min internal free (under load) | **212 KB** | epub ✓ |
| Min PSRAM free (under load) | **7.0 MB** | epub ✓ |
| Sequential bandwidth (memset) | PSRAM **35 MB/s** · internal **761 MB/s** | epub ✓ |
| Random-access latency | PSRAM **512 ns/B** · internal **55 ns/B** (~9× slower) | epub ✓ |
| CPU clock scaling (fixed workload) | 240 MHz **1.00×** · 160 MHz 1.50× · 80 MHz **3.04×** | epub ✓ |
| Inflate throughput (ROM tinfl) | **7.2 MB/s out** (30 KB in 4.1 ms) | epub ✓ |
| Peak stack (miniz inflate wrapper) | **~12 KB** (needs >8 KB default; use heap inflate) | epub ✓ |

## Wake / power
| Metric | Value | Source |
|---|---|---|
| App-init → `setup()` latency | **~142 ms** (Arduino+PSRAM+USB init) | epub ✓ |
| Full reset → ready-to-render | TBD (+ bootloader) | epub |
| Deep-sleep wake-latency (real cycles) | TBD (`BENCH_SLEEP_CYCLES`) | epub |
| Deep-sleep current | TBD (~14 µA target) | meter |
| Active / render / refresh current | TBD | meter |
| WiFi-peak current | TBD | meter |

## WiFi (needs U.FL antenna)
| Metric | Value | Source |
|---|---|---|
| STA connect — reconnect (BSSID+ch) | **~0.8 s** (reliable → cache BSSID+ch in RTC) | wifi ✓ |
| STA connect — DHCP (cold) | **variable 0.8–2.25 s** (scan-dependent) | wifi ✓ |
| RSSI at bench location | **−54 dBm** (healthy; antenna good) | wifi ✓ |
| NTP sync time | **variable** (0 s warm, ~5 s first-packet) | wifi ✓ |
| Min free heap w/ WiFi up | **~247 KB** stock · **~128 KB tuned** (bigger buffers cost ~113 KB) | wifi ✓ |
| **LAN download — stock** (window 5760) | **0.38 MB/s (3.2 Mbps)** | wifi ✓ |
| **LAN download — tuned** (window 65535) | **2.41 MB/s (20 Mbps) — 6.3×** via pioarduino `custom_sdkconfig` | wifi ✓ |
| Internet HTTPS+WAN download | 0.14 MB/s stock / ~1.7 (tuned, tiny sample) — WAN/TLS-bound | wifi ~ |
| HTTPS handshake time | TBD (set HTTPS_TEST_URL — it's empty in secrets.h) | wifi |
| TLS session heap | TBD (needs HTTPS_TEST_URL) | wifi |
| Crypto accel | HW **AES + MPI(bignum) + SHA** on; ECC = software; **TLS 1.2 only** | sdkconfig ✓ |
| Download bottleneck | stock: WiFi (0.38) ≪ SD write → WiFi-bound. **Tuned: WiFi (2.41) ≈ SD write (2–3) → now balanced/SD-bound** | wifi ✓ |

## Storage (Path 1: shared SPI + SdFat)
| Metric | Value | Source |
|---|---|---|
| SD read throughput | TBD | epub+sd |
| SD write throughput | TBD | sd |
| Per-page `progress.bin` write | TBD | sd |

## E-ink (needs panel)
| Metric | Value | Source |
|---|---|---|
| Full refresh | TBD (~1.8 s spec) | panel |
| Partial/fast refresh | TBD (~0.7 s spec) | panel |
| Partial-refresh RED-RAM correctness | TBD (driver gotcha) | panel |
| Ghosting cadence (full every N) | TBD | panel |

## Interpretation so far
On-device parse + paginate + image decode are all fast and memory-light with
huge headroom (212 KB internal / 7 MB PSRAM min). See
`crosspoint-adoption-plan.md` §5 — the CrossPoint feasibility gate is cleared on
every axis measured to date.
