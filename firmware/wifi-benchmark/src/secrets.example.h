#pragma once
// Copy this file to `secrets.h` (which is gitignored) and fill it in.

#define WIFI_SSID "your-network"
#define WIFI_PASS "your-password"

// HTTP download-throughput test: a real file on your LAN — e.g. a book served by
// the desktop service. Leave "" to skip. (Validates the storage Path-1 analysis:
// downloads should be WiFi-bound, not SD-bound.)
#define HTTP_TEST_URL "http://192.168.1.50:8000/book/REPLACE_WITH_ID.epub"

// HTTPS handshake test — validates the OTA-over-GitHub path + the ~55 KB TLS heap
// estimate. Default is our releases endpoint; any https URL works.
#define HTTPS_TEST_URL "https://api.github.com/repos/RR-T/esp-read/releases/latest"

// Internet speed test (download + discard). Optional — a sensible public default
// is built in (Cloudflare, 5 MB). Override to change size, or point at a big file
// on your LAN for a pure-WiFi number without the WAN/TLS overhead. Set "" to skip.
#define SPEEDTEST_URL "https://speed.cloudflare.com/__down?bytes=10000000"

// Optional: define all three to time a static-IP connect (guide claims it saves
// 1-3 s vs DHCP). Comment out to skip that test.
// #define STATIC_IP   "192.168.1.234"
// #define STATIC_GW   "192.168.1.1"
// #define STATIC_MASK "255.255.255.0"
