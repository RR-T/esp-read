# Firmware performance tuning (build config)

Distilled from Espressif's [Maximizing Execution Speed](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/performance/speed.html)
guide and the Wi-Fi performance guide, **filtered for our actual workload** and
build stack (Arduino-ESP32 + PlatformIO, CrossPoint fork).

## The two things that frame everything

**1. Our device is idle ~99% of the time (deep sleep).** Speed only matters in
three narrow windows, so we optimize those and ignore levers aimed at
always-on / sustained-throughput apps:
- **A — wake → ready-to-render** (paid *every page turn*; measured **~142 ms**
  app-init on our board).
- **B — WiFi sync duration** (occasional; = energy per sync).
- **C — parse / render / decode** (already fast: ~1 ms/page, 82 ms/image, 7 MB/s
  inflate — not a concern).

**2. Arduino-ESP32 ships a *precompiled* framework with a fixed `sdkconfig`.**
That splits the levers into two reachability tiers:
- **Project-level** (always available): flash mode/freq, CPU freq, app-code
  compiler flags, `IRAM_ATTR` on *our* code, core debug level, and runtime APIs.
- **sdkconfig-level** (cache size, bootloader skip-validate, PSRAM memtest, lwIP
  windows, WiFi buffers): baked into the precompiled lib. Reachable **only** by
  rebuilding the framework from source / a custom sdkconfig.
  - ⚠️ **Verify:** our platform is `espressif32 @ 7.0.1` (the *pioarduino* fork),
    which may support `board_build.arduino.custom_sdkconfig` to override
    sdkconfig without hand-building. If it does, Tier 2/3 below get much cheaper.
    Confirm before planning around it (it triggers a full framework rebuild).

---

## Tier 1 — apply now in `platformio.ini` / our code (easy, real)

| Lever | How | Why it matters for us |
|---|---|---|
| **Flash QIO @ 80 MHz** | `board_build.arduino.memory_type = qio_opi` (our board) — gives flash **QIO** + OPI PSRAM | ~2× flash read → faster boot (window A) + faster XIP code. **CrossPoint's platformio.ini currently sets `flash_mode = dio`** — switch it. |
| **CPU @ 240 MHz** | default; keep (`setCpuFrequencyMhz(240)`) | Clock-scaling bench: 240 MHz is ~3× faster than 80 → race-to-sleep for CPU-bound parse/render. |
| **Minimal logging** | `build_flags = -DCORE_DEBUG_LEVEL=0` | Less CPU/flash per call + faster boot (Arduino equivalent of `CONFIG_LOG_DEFAULT_LEVEL`). |
| **App `-O2`** | `build_flags = -O2` (framework stays as shipped) | `CONFIG_COMPILER_OPTIMIZATION` = perf, but only for our app TU's. Marginal, free. |
| **WiFi power-save off during sync** | `WiFi.setSleep(false)` (= `esp_wifi_set_ps(WIFI_PS_NONE)`) while syncing, then sleep | Biggest WiFi latency/throughput lever available in Arduino — cuts sync time (window B). Re-enable before deep sleep. |
| **Fast-connect cache** | store BSSID + channel (+ optional static IP) in RTC memory; `WiFi.begin(ssid, pass, ch, bssid)` | **Measured 0.82 s vs 2.25 s cold** — biggest single sync-latency win, and it's firmware-level (no sdkconfig). |

## Tier 2 — needs custom sdkconfig; targets **wake latency** (window A)

These cut the per-page-turn wake cost, so they're the highest-value sdkconfig
options *for our deep-sleep-per-page model*:

| Option | Value | Effect |
|---|---|---|
| `CONFIG_BOOTLOADER_SKIP_VALIDATE_IN_DEEP_SLEEP` | `y` | Skip image validation on deep-sleep wake → faster wake (fine unless Secure Boot). |
| `CONFIG_SPIRAM_MEMTEST` | `n` | Skip PSRAM memtest (~1 s / 4 MB) each boot. |
| `CONFIG_BOOTLOADER_LOG_LEVEL` / `CONFIG_LOG_DEFAULT_LEVEL` | minimal | Faster boot; less runtime overhead. |
| `CONFIG_RTC_CLK_CAL_CYCLES` | `0` | Minor boot saving (costs RTC timing accuracy — we NTP-sync anyway). |
| `CONFIG_COMPILER_OPTIMIZATION` | `-O2` | Whole-framework perf (only when building from source). |

Reference: ESP-IDF `examples/system/startup_time` ships an optimized
`sdkconfig.defaults`. **Measure first** — our 142 ms is already << the ~1 s
e-ink refresh, so this is a nice-to-have, not a blocker. If we stay on the
precompiled core, 142 ms is simply our floor.

## Crypto & TLS (verified from the shipped arduino-esp32 sdkconfig)

- **Hardware AES: on** (`CONFIG_MBEDTLS_HARDWARE_AES=y`, `AES_USE_INTERRUPT`).
- **Hardware bignum/MPI: on** (`CONFIG_MBEDTLS_HARDWARE_MPI=y`) — accelerates
  RSA/DH modexp in the handshake.
- **Hardware SHA: on** (`CONFIG_MBEDTLS_HARDWARE_SHA=y`).
- **ECC point math: software** (no ECC/ECP-alt accel on the S3) — so the ECDHE
  curve ops in the handshake are the CPU cost; bulk AES-GCM + SHA are hardware.
- **TLS 1.3: NOT enabled** — only `CONFIG_MBEDTLS_SSL_PROTO_TLS1_2=y`. TLS 1.3
  would cut the handshake by ~1 RTT (1-RTT vs 1.2's 2-RTT), helping *connect
  latency* not *throughput*, and needs a newer core (arduino-esp32 3.x / IDF 5.x)
  + custom sdkconfig. Minor win, not worth a framework bump now.
- Net: nothing to tune for TLS crypto speed — the accelerators we have are
  already engaged; a ~1.5 MB OTA over HTTPS is CPU-bound on ECDHE handshake +
  ~10 s transfer, which is fine for an occasional update.

## Tier 3 — WiFi/TCP throughput (custom sdkconfig; LOW priority for us)

**ESP32-S3 throughput ceilings** (ESP-IDF, single stream, shielded box):

| Rank | TCP TX | TCP RX | UDP TX | UDP RX |
|---|---|---|---|---|
| iperf (tuned, PS off) | 84 | 74 | 99 | 89 |
| default | 64 | 60 | 96 | 87 |
| minimum | 23 | 18 | 49 | 59 |

(Mbit/s.) Those are the *tuned* ceilings. **Measured on our board (PS off, plain
HTTP LAN): 0.38 MB/s (3.2 Mbps)** — below even the "minimum" rank.

**Confirmed root cause — arduino ships a tiny TCP window.** The framework's
`sdkconfig` sets `CONFIG_LWIP_TCP_WND_DEFAULT=5760` and
`CONFIG_LWIP_TCP_SND_BUF_DEFAULT=5760` (5.76 KB) with `LWIP_WND_SCALE` **off** —
vs the IDF default rank's 32 KB and iperf's 64 KB. Throughput ≈ window ÷ RTT =
5760 B ÷ ~15 ms ≈ **0.38 MB/s**, matching the measurement exactly. So it's the
window, **not** the WiFi PHY or the test server.

**Fix — VERIFIED reachable** via the **pioarduino** platform's `custom_sdkconfig`
(Arduino 3.x / IDF 5.x; the *official* platform ships precompiled libs and can't).
Confirmed the values land in the generated sdkconfig. Needs a local
`huge_app.csv` in the project (pioarduino doesn't fall back to the framework's).
See `firmware/wifi-benchmark` `[env:xiao_s3_tuned]`.

Core throughput set (RAM buffers + window — the dominant levers):
```
CONFIG_LWIP_TCP_WND_DEFAULT=65535        # was 5760
CONFIG_LWIP_TCP_SND_BUF_DEFAULT=65535
CONFIG_LWIP_TCP_RECVMBOX_SIZE=64
CONFIG_LWIP_WND_SCALE=y
CONFIG_LWIP_TCP_RCV_SCALE=2
CONFIG_ESP_WIFI_STATIC_RX_BUFFER_NUM=24
CONFIG_ESP_WIFI_DYNAMIC_RX_BUFFER_NUM=64
CONFIG_ESP_WIFI_DYNAMIC_TX_BUFFER_NUM=64
CONFIG_ESP_WIFI_STATIC_TX_BUFFER_NUM=32  # PSRAM forces TX buffer static — this is the one that applies
CONFIG_ESP_WIFI_RX_BA_WIN=32
CONFIG_LWIP_IRAM_OPTIMIZATION=y
CONFIG_COMPILER_OPTIMIZATION_PERF=y      # -O2 whole framework
```
Optional / caveated:
- `CONFIG_ESP_WIFI_IRAM_OPT=y`, `CONFIG_ESP_WIFI_RX_IRAM_OPT=y`,
  `CONFIG_LWIP_EXTRA_IRAM_OPTIMIZATION=y` — doc-recommended, but consume IRAM →
  can overflow the link on the fuller CrossPoint firmware. Fine for this small
  benchmark; re-check IRAM budget before enabling in the fork.
- `CONFIG_SPIRAM_TRY_ALLOCATE_WIFI_LWIP=n` — arduino defaults to `y` (WiFi/lwIP
  buffers in PSRAM). Our PSRAM random access is ~9× slower than internal, so
  moving buffers to internal SRAM *may* raise throughput — but costs ~100 KB+
  internal RAM. Experiment only if still capped after the window fix.
- Leave **AMPDU on** (arduino default) and handle power-save at runtime
  (`WiFi.setSleep(false)`) — no sdkconfig needed for either.

**Measured: 0.38 → 2.41 MB/s (20 Mbps), a 6.3× win** — confirms the window was
the cap. (Short of the ~60 Mbps tuned ceiling, likely capped now by the plain
`python -m http.server` and/or the un-enabled IRAM opts — but 2.41 MB/s is well
past our needs.) **Two consequences to weigh for the fork:**
1. **RAM cost ~113 KB** — free heap dropped 247 KB → 128 KB. The full CrossPoint
   firmware has less headroom, so tune the numbers *down* (e.g. a 32 KB window is
   already the "default rank" ~60 Mbps and costs less) rather than max everything.
2. **Bottleneck flips:** tuned WiFi (2.41) ≈ SPI SD write (2–3 MB/s), so downloads
   become SD-bound — no reason to push WiFi harder. At our sizes it's moot either
   way (1 MB EPUB ≈ 0.4 s). **Optional for us:** 0.38 MB/s already gives ~2.6 s/EPUB,
~4 s/OTA. And if WiFi rose to ~4 MB/s, **SPI SD write (~2–3 MB/s) becomes the
bottleneck** — so downloads stay bounded either way; tuning only helps large
transfers (bitmap books, big libraries). Path 1 remains fine regardless.
(Internet HTTPS stays ~0.14 MB/s — WAN/TLS-bound, PS made no difference.)

Knobs, if a future feature ever needs fast bulk transfer:
- **Power-save (biggest lever, runtime):** `esp_wifi_set_ps(WIFI_PS_NONE)` /
  `WiFi.setSleep(false)` — default is `WIFI_PS_MIN_MODEM`, which caps throughput.
- **WiFi buffers (sdkconfig, iperf values):** `CONFIG_ESP_WIFI_STATIC_RX_BUFFER_NUM=24`,
  `CONFIG_ESP_WIFI_DYNAMIC_RX_BUFFER_NUM=64`, `CONFIG_ESP_WIFI_DYNAMIC_TX_BUFFER_NUM=64`,
  `CONFIG_ESP_WIFI_STATIC_TX_BUFFER_NUM=32`, `CONFIG_ESP_WIFI_RX_BA_WIN=32`,
  `CONFIG_ESP_WIFI_AMPDU_TX_ENABLED`/`_RX_ENABLED=y`,
  `CONFIG_ESP_WIFI_IRAM_OPT`/`_RX_IRAM_OPT=y`.
- **lwIP (sdkconfig):** `CONFIG_LWIP_TCP_WND_DEFAULT`, `CONFIG_LWIP_TCP_SND_BUF_DEFAULT`,
  `CONFIG_LWIP_TCP_RECVMBOX_SIZE`, `CONFIG_LWIP_TCP_MSS`, `CONFIG_LWIP_WND_SCALE`,
  `CONFIG_LWIP_IRAM_OPTIMIZATION` + `CONFIG_LWIP_EXTRA_IRAM_OPTIMIZATION`,
  `CONFIG_LWIP_TCPIP_TASK_AFFINITY`.
- Reference: ESP-IDF `examples/wifi/iperf` `sdkconfig.defaults*`.

## Tier 4 — skip for us

`IRAM_ATTR` placement of render code and instruction/data **cache-size tuning**
(`CONFIG_ESP32S3_INSTRUCTION_CACHE_SIZE`, `..._DATA_CACHE_SIZE`) trade DRAM for
speed we don't need — render is already fast and dominated by the e-ink refresh.

---

## Memory placement audit — CrossPoint was written for a ~380 KB-RAM, ~no-PSRAM chip

CrossPoint's `s3-port` still carries code comments citing **ESP32-C3 ~380 KB
RAM** (the original Xteink X4 target) — a chip with no meaningful PSRAM story.
Its EPUB engine (parser, layout, font cache, section/page cache, image
decoders) was necessarily written memory-conservative for that budget, so it's
very unlikely to already be PSRAM-aware. Our board has **8 MB PSRAM** vs their
~380 KB total internal — over 20× the headroom, and one we should actively claim
rather than leave latent, since our own benchmarks show internal SRAM (not
PSRAM) is *our* scarce resource too (~212 KB min free under parse+render load).

**Two-pronged approach, fork-time (needs the CrossPoint source in front of us):**

1. **Global lever (try first, near-zero effort):** tune
   `CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL` (size threshold below which `malloc()`
   always goes internal) and `CONFIG_SPIRAM_MALLOC_RESERVE_INTERNAL` (internal
   pool reserved for DMA-only needs). If the default threshold is conservative,
   CrossPoint's existing large `malloc()`/`new` calls may redirect to PSRAM with
   **no code changes** at all.
2. **Targeted audit:** grep `lib/Epub`, `lib/GfxRenderer`, `lib/EpdFont` for
   `malloc`/`new`/`heap_caps_malloc`, and classify each by access pattern using
   our own measured heuristic — **PSRAM sequential ≈ internal speed; PSRAM random
   access ≈ 9× slower** (512 ns/byte vs 55 ns/byte, measured on this board):
   - **Move to PSRAM** (large, mostly sequential/bulk): framebuffer, image
     decode/dither buffers (`ImageToFramebufferDecoder`, `Jpeg`/
     `PngToFramebufferConverter`), cached `section.bin`/page-layout buffers, SD
     read-staging buffers, font glyph bitmap cache.
   - **Keep internal** (small, hot, pointer-chasing): CSS parse trees,
     hyphenation trie lookups (check first — the trie data ships as generated
     header arrays, so it may already be flash/rodata-resident and cost no RAM
     at rest), any struct touched every render frame.
   - **Cannot move regardless of code (hardware constraint, confirmed this
     session):** WiFi's low-level static RX/TX buffers — the radio's DMA engine
     can only address internal RAM, not PSRAM.

Do this audit as part of the display/storage/battery HAL port (§3.1–3.3) rather
than speculatively now — it needs the real allocation call sites in front of us.

## Checklist when we build the fork

- [ ] platformio.ini: `memory_type = qio_opi` (flash QIO), confirm 240 MHz,
      `-DCORE_DEBUG_LEVEL=0`, `-O2`.
- [ ] Flip CrossPoint's `flash_mode = dio` → QIO for our board.
- [ ] Firmware: BSSID+channel (+static IP) fast-connect cache in RTC memory;
      `WiFi.setSleep(false)` during the sync window only.
- [ ] Decide whether `custom_sdkconfig` works on this platform; if so, apply the
      Tier-2 wake-latency options and re-measure the 142 ms app-init.
- [ ] Re-run `wifi-benchmark` after `setSleep(false)` + fast-connect to confirm
      the sync-window improvement.
