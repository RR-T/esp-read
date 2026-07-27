// WiFi/network benchmark — XIAO ESP32-S3 Plus.
//
// Measures the reader's sync/OTA path so we can put real numbers on the spec
// sheet: STA connect time (DHCP / BSSID-hinted / static), NTP sync, HTTP LAN
// download throughput, and HTTPS handshake + TLS heap. Flash, open the serial
// monitor at 115200, read the report.
//
// !! Attach the U.FL antenna before running. Never run WiFi with no antenna.

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <time.h>
#include "esp_heap_caps.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#warning "No secrets.h — copy src/secrets.example.h to src/secrets.h and fill it in."
#define WIFI_SSID ""
#define WIFI_PASS ""
#endif

#ifndef HTTP_TEST_URL
#define HTTP_TEST_URL ""
#endif
#ifndef HTTPS_TEST_URL
#define HTTPS_TEST_URL "https://api.github.com/repos/RR-T/esp-read/releases/latest"
#endif
// Zero-config internet speed test: Cloudflare returns exactly N bytes. Override
// in secrets.h (e.g. point at a big file on your LAN for a pure-WiFi number).
#ifndef SPEEDTEST_URL
#define SPEEDTEST_URL "https://speed.cloudflare.com/__down?bytes=5000000"
#endif

// Internal SRAM vs PSRAM free, explicitly — ESP.getFreeHeap()/getMinFreeHeap()
// report MALLOC_CAP_INTERNAL only, which silently hides whether a change ate
// internal SRAM (scarce, ~320 KB) or PSRAM (abundant, ~8 MB). WiFi's low-level
// "static" RX/TX buffers are the radio's own DMA buffers, which MUST be
// internal (PSRAM isn't DMA-capable on the S3) — this makes that cost visible.
static void reportHeapSplit(const char *tag) {
  Serial.printf("  %-22s internal free %7u | PSRAM free %8u\n", tag,
                (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
                (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
}

static void rule(const char *title) {
  Serial.printf("\n==== %s ", title);
  for (int i = strlen(title); i < 40; i++) Serial.print('=');
  Serial.println();
}

// Connect once with a given strategy; print time + link info. Returns success.
static bool connectOnce(const char *label, bool useStatic, int32_t channel,
                        const uint8_t *bssid) {
  WiFi.disconnect(true, true);
  delay(200);
  WiFi.mode(WIFI_STA);
  if (useStatic) {
#ifdef STATIC_IP
    IPAddress ip, gw, mask;
    ip.fromString(STATIC_IP);
    gw.fromString(STATIC_GW);
    mask.fromString(STATIC_MASK);
    if (!WiFi.config(ip, gw, mask)) Serial.println("  WiFi.config(static) failed");
#endif
  }

  uint32_t t0 = millis();
  if (channel && bssid)
    WiFi.begin(WIFI_SSID, WIFI_PASS, channel, bssid);
  else
    WiFi.begin(WIFI_SSID, WIFI_PASS);

  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) delay(10);
  uint32_t dt = millis() - t0;

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("  %-22s %5lu ms   RSSI %d dBm   ch %d   IP %s\n", label,
                  (unsigned long)dt, WiFi.RSSI(), WiFi.channel(),
                  WiFi.localIP().toString().c_str());
    return true;
  }
  Serial.printf("  %-22s FAILED (20s timeout)\n", label);
  return false;
}

static void benchNtp() {
  rule("NTP time sync");
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  struct tm tm;
  uint32_t t0 = millis();
  bool ok = false;
  while (millis() - t0 < 10000) {
    if (getLocalTime(&tm, 10)) { ok = true; break; }
    delay(50);
  }
  if (ok) {
    char buf[32];
    strftime(buf, sizeof buf, "%Y-%m-%d %H:%M:%S", &tm);
    Serial.printf("  synced in %lu ms -> %s UTC\n", (unsigned long)(millis() - t0), buf);
  } else {
    Serial.printf("  NTP FAILED (%lu ms)\n", (unsigned long)(millis() - t0));
  }
}

// Download a URL and discard the body, reporting throughput. Handles http and
// https (TLS adds CPU cost, so an http source gives a purer WiFi-link number).
static void downloadAndDiscard(const char *label, const char *url) {
  const bool https = strncmp(url, "https://", 8) == 0;
  WiFiClientSecure secure;
  WiFiClient plain;
  WiFiClient *client = &plain;
  if (https) {
    secure.setInsecure();  // a speed test doesn't need cert verification
    client = &secure;
  }

  const uint32_t CAP_MS = 20000;  // never run a single download longer than this

  HTTPClient http;
  if (!http.begin(*client, url)) {
    Serial.printf("  %-16s begin failed (bad URL?)\n", label);
    return;
  }
  http.setConnectTimeout(8000);
  http.setTimeout(8000);
  http.useHTTP10(true);  // no chunked/keep-alive: server closes at end of body

  uint32_t t0 = millis();
  int code = http.GET();
  uint32_t ttfb = millis() - t0;  // request + time-to-first-byte
  if (code != HTTP_CODE_OK && code != HTTP_CODE_PARTIAL_CONTENT) {
    Serial.printf("  %-16s HTTP %d (ttfb %lu ms)\n", label, code, (unsigned long)ttfb);
    http.end();
    return;
  }

  int len = http.getSize();
  WiFiClient *s = http.getStreamPtr();
  s->setTimeout(4000);
  uint8_t buf[2048];
  size_t total = 0;
  int idle = 0;
  uint32_t tData = millis(), lastLog = tData;
  bool capped = false;
  while (http.connected() && (len < 0 || total < (size_t)len)) {
    size_t n = s->readBytes(buf, sizeof buf);
    if (n == 0) {
      if (++idle >= 2) break;  // two empty reads (~8s) -> stalled, stop
      continue;
    }
    idle = 0;
    total += n;  // discard
    uint32_t now = millis();
    if (now - lastLog >= 1000) {  // heartbeat so it's clearly not hung
      double sec = (now - tData) / 1000.0;
      Serial.printf("    ... %u KB  %.2f MB/s\n", (unsigned)(total / 1024),
                    total / 1048576.0 / sec);
      lastLog = now;
    }
    if (now - tData > CAP_MS) { capped = true; break; }
  }
  double sec = (millis() - tData) / 1000.0;
  http.end();

  if (sec <= 0) sec = 1e-3;
  Serial.printf("  %-16s %u KB  ttfb %lu ms  %.2f MB/s (%.1f Mbps)%s%s\n", label,
                (unsigned)(total / 1024), (unsigned long)ttfb, total / 1048576.0 / sec,
                total * 8.0 / 1e6 / sec, https ? "  [https+TLS]" : "",
                capped ? "  [20s cap]" : "");
}

static void benchDownloads() {
  rule("Download throughput (download + discard)");
  if (strlen(HTTP_TEST_URL) > 0)
    downloadAndDiscard("LAN service", HTTP_TEST_URL);  // purest WiFi-link number
  else
    Serial.println("  LAN service     (set HTTP_TEST_URL in secrets.h to test)");
  if (strlen(SPEEDTEST_URL) > 0)
    downloadAndDiscard("internet", SPEEDTEST_URL);
}

static void benchHttps() {
  rule("HTTPS handshake + TLS heap (OTA path)");
  String url = HTTPS_TEST_URL;
  if (url.length() == 0) { Serial.println("  HTTPS_TEST_URL empty in secrets.h — skipped"); return; }
  String u = url;
  if (u.startsWith("https://")) u = u.substring(8);
  else if (u.startsWith("http://")) u = u.substring(7);
  int slash = u.indexOf('/');
  String host = (slash < 0) ? u : u.substring(0, slash);
  if (host.length() == 0) {
    Serial.printf("  can't parse host from '%s' — skipped\n", url.c_str());
    return;
  }

  WiFiClientSecure client;
  client.setInsecure();  // handshake-cost + heap ballpark; verified TLS heap is similar

  uint32_t heapBefore = ESP.getFreeHeap();
  uint32_t t0 = millis();
  bool ok = client.connect(host.c_str(), 443);
  uint32_t hs = millis() - t0;
  uint32_t heapConn = ESP.getFreeHeap();

  if (ok) {
    Serial.printf("  handshake to %s: %lu ms\n", host.c_str(), (unsigned long)hs);
    Serial.printf("  TLS heap: free %u -> %u  (~%d KB for the session)\n",
                  (unsigned)heapBefore, (unsigned)heapConn,
                  (int)((heapBefore - heapConn) / 1024));
    client.printf("GET / HTTP/1.1\r\nHost: %s\r\nUser-Agent: esp-read-bench\r\n"
                  "Connection: close\r\n\r\n", host.c_str());
    uint32_t t1 = millis();
    size_t got = 0;
    uint8_t b[512];
    while (client.connected() && millis() - t1 < 5000) {
      int n = client.read(b, sizeof b);
      if (n > 0) got += n;
      else delay(1);
    }
    Serial.printf("  fetched %u bytes (headers+body)\n", (unsigned)got);
  } else {
    Serial.printf("  HTTPS connect FAILED to %s (%lu ms)\n", host.c_str(),
                  (unsigned long)hs);
  }
  client.stop();
  Serial.printf("  min free heap since boot: %u\n", (unsigned)ESP.getMinFreeHeap());
}

void setup() {
  Serial.begin(115200);
  uint32_t start = millis();
  while (!Serial && millis() - start < 10000) delay(10);
  delay(300);

  Serial.println("\n\n######## esp-read WiFi benchmark ########");
  Serial.println("!! Ensure the U.FL antenna is attached.");

  rule("Heap: baseline (before WiFi.mode/begin)");
  reportHeapSplit("pre-WiFi");

  if (strlen(WIFI_SSID) == 0) {
    Serial.println("No WIFI_SSID — copy src/secrets.example.h to src/secrets.h. Halting.");
    return;
  }

  // Antenna-confirmation gate removed for now — ENSURE THE U.FL ANTENNA IS
  // ATTACHED before flashing. Brief reminder + delay instead of a blocking prompt.
  Serial.println("!! Ensure the U.FL antenna is attached — starting WiFi in 3s...");
  delay(3000);

  rule("WiFi connect");
  if (!connectOnce("connect DHCP (cold)", false, 0, nullptr)) {
    Serial.println("  cannot continue without a connection.");
    return;
  }
  uint8_t bssid[6];
  memcpy(bssid, WiFi.BSSID(), 6);
  int32_t channel = WiFi.channel();
  connectOnce("reconnect bssid/ch", false, channel, bssid);
#ifdef STATIC_IP
  connectOnce("connect static IP", true, 0, nullptr);
#else
  Serial.println("  (define STATIC_IP/GW/MASK in secrets.h to time static-IP connect)");
#endif

  if (WiFi.status() != WL_CONNECTED) connectOnce("reconnect", false, 0, nullptr);

  // Connect times above used the DEFAULT power-save (WIFI_PS_MIN_MODEM), which
  // is realistic for a wake. Disable it now (WIFI_PS_NONE) for the throughput
  // tests — modem-sleep otherwise caps TCP throughput and adds latency. A real
  // sync would do the same: setSleep(false) for the sync window, then deep-sleep.
  WiFi.setSleep(false);
  Serial.println("\n(power-save now OFF / WIFI_PS_NONE for the tests below)");
  rule("Heap: after connect, before transfers");
  reportHeapSplit("connected");

  benchNtp();
  benchDownloads();
  benchHttps();

  rule("Heap: after transfers, WiFi still up");
  reportHeapSplit("post-transfer");

  // disconnect() alone (even with wifioff=true) may not release the driver's
  // own static/DMA buffers — those are reserved for the WiFi subsystem's
  // lifetime, not just "connected" time. mode(WIFI_OFF) drives esp_wifi_stop(),
  // the actual teardown a deep-sleep-per-page loop would do before sleeping.
  WiFi.disconnect(true, true);
  reportHeapSplit("after disconnect()");
  WiFi.mode(WIFI_OFF);
  reportHeapSplit("after mode(WIFI_OFF)");

  rule("Done");
  Serial.printf("  min free heap since boot: %u\n", (unsigned)ESP.getMinFreeHeap());
  Serial.println("  Reading guide:");
  Serial.println("   - connect time dominates each sync's awake time (energy)");
  Serial.println("   - HTTP MB/s: if < SD write speed, downloads are WiFi-bound (Path 1 ok)");
  Serial.println("   - TLS heap ~tens of KB: why LAN sync uses plain HTTP, OTA uses HTTPS");
  Serial.println("   - compare 'pre-WiFi' vs 'after mode(WIFI_OFF)' internal free:");
  Serial.println("     if they match, WiFi's internal-RAM cost is fully transient (sync-window only)");
  Serial.println("     if they don't, some cost persists while the WiFi driver stays initialized");
}

void loop() { delay(1000); }
