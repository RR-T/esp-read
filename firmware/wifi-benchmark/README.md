# WiFi / network benchmark

Measures the reader's **sync + OTA path** on the XIAO ESP32-S3 Plus, to put real
numbers on the hardware spec sheet. Complements `../epub-benchmark/` (CPU / memory
/ render / image / inflate).

> ⚠️ **Attach the U.FL antenna before running.** This board variant has no
> onboard antenna trace; running WiFi without one can damage the radio.

## What it measures

1. **STA connect time** — three ways:
   - DHCP (cold)
   - reconnect hinted with the stored **BSSID + channel** (the fast-reconnect path)
   - **static IP** (optional; the guide claims it saves 1–3 s vs DHCP)
   Each line also reports RSSI (antenna sanity), channel, and IP.
2. **NTP sync time** — how long to get network time after connecting (NTP-on-sync).
3. **Download throughput (download + discard)** — MB/s + Mbps for:
   - a **LAN file** (`HTTP_TEST_URL`, plain HTTP → purest WiFi-link number) —
     validates the storage **Path-1** analysis: if it's below SD write speed,
     downloads are WiFi-bound (as assumed);
   - an **internet** target (`SPEEDTEST_URL`, Cloudflare 5 MB by default → works
     with zero config; includes WAN + TLS).
4. **HTTPS handshake + TLS heap** — validates the **OTA-over-GitHub** path and the
   ~55 KB TLS-heap estimate (why LAN sync uses plain HTTP and only OTA uses HTTPS).

## Setup

```bash
cp src/secrets.example.h src/secrets.h    # then edit: WiFi creds + test URLs
```

`secrets.h` is gitignored. Point `HTTP_TEST_URL` at a real file on your LAN (e.g.
a book from the desktop service); leave it `""` to skip that test. Optionally
define `STATIC_IP`/`GW`/`MASK` to time a static-IP connect.

## Run

```bash
cd firmware/wifi-benchmark
pio run -e xiao_s3 -t upload -t monitor
```

**The sketch will not enable WiFi until you confirm the antenna is attached** —
it prints a safety prompt and waits for you to type **`y`** (then Enter) in the
monitor. Nothing touches the radio before that. (No SD card or panel needed. If
PSRAM reports issues, flip `board_build.arduino.memory_type` as in the epub
benchmark.)

## Reading the results

- **Connect time** is most of each sync's awake time → dominates sync energy.
  Compare DHCP vs BSSID-hinted vs static to decide the firmware's connect strategy.
- **HTTP MB/s** vs the SD write speed (from the epub benchmark, once SD is wired)
  tells you which is the bottleneck for book downloads.
- **TLS heap** confirms whether HTTPS is affordable on-device and why we keep LAN
  traffic on plain HTTP.
