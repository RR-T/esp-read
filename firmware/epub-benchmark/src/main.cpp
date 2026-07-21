// On-device EPUB feasibility benchmark — XIAO ESP32-S3 Plus + Waveshare 5" (EPD_5in0).
//
// Answers: does on-device parse/paginate/render fit comfortably in 8MB PSRAM, and
// what are the page-turn / refresh costs that govern the deep-sleep-per-page power
// model? Flash it, open the serial monitor at 115200, read the report.
//
// What it measures:
//   1. Board + memory inventory (flash, PSRAM, heap, largest free block)
//   2. PSRAM allocation + bandwidth vs internal RAM
//   3. Panel init + full/partial refresh timing (real e-ink numbers)
//   4. 1-bit text render cost (paginate + rasterise a page)
//   5. Representative EPUB workload: read a chapter off SD, strip tags,
//      paginate the whole thing, render page 1 — with heap watermarks
//
// SD prep (optional but recommended): put one chapter of a DRM-free book on a
// FAT32 microSD as /sample.xhtml (or /sample.txt). The desktop text-mode service
// output works directly. Without it, steps 1-4 still run.

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_GFX.h>
#include <Fonts/FreeSerif12pt7b.h>
#include <ctype.h>
#include "esp_heap_caps.h"
#include "Epd5in0.h"

// ---- Pin map: XIAO ESP32-S3 Plus (from CLAUDE.md) ----
static const int PIN_SCK = 7;    // D8
static const int PIN_MISO = 8;   // D9
static const int PIN_MOSI = 9;   // D10
static const int EPD_CS = 1;     // D0
static const int EPD_DC = 2;     // D1
static const int EPD_RST = 4;    // D3
static const int EPD_BUSY = 43;  // D6
static const int SD_CS = 44;     // D7

SPIClass spiBus(HSPI);
Epd5in0 epd(spiBus, EPD_CS, EPD_DC, EPD_RST, EPD_BUSY);
GFXcanvas1 *canvas = nullptr;  // 1-bit page buffer

bool panelOk = false;
bool sdOk = false;

// ---- text-area layout (device px) ----
static const int MARGIN_X = 40;
static const int TOP = 46;
static const int LINE_H = FreeSerif12pt7b.yAdvance;
static int spaceW = 8;

// --------------------------------------------------------------------------
static void rule(const char *title) {
  Serial.printf("\n==== %s ", title);
  for (int i = strlen(title); i < 40; i++) Serial.print('=');
  Serial.println();
}

static void reportMem(const char *tag) {
  size_t intFree = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
  size_t intBig = heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL);
  size_t psFree = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
  size_t psBig = heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
  Serial.printf("  %-14s internal free %7u (largest %7u) | PSRAM free %8u (largest %8u)\n",
                tag, (unsigned)intFree, (unsigned)intBig, (unsigned)psFree, (unsigned)psBig);
}

static void reportBoard() {
  rule("Board & memory");
  Serial.printf("  chip            %s rev%d, %d core(s) @ %d MHz\n",
                ESP.getChipModel(), ESP.getChipRevision(), ESP.getChipCores(),
                ESP.getCpuFreqMHz());
  Serial.printf("  flash           %u MB\n", (unsigned)(ESP.getFlashChipSize() >> 20));
  Serial.printf("  PSRAM           %u bytes total, %u free\n",
                (unsigned)ESP.getPsramSize(), (unsigned)ESP.getFreePsram());
  if (ESP.getPsramSize() == 0)
    Serial.println("  !! PSRAM NOT DETECTED — fix board_build.arduino.memory_type in platformio.ini");
  reportMem("at boot");
}

// --------------------------------------------------------------------------
static double bandwidthMBs(uint8_t *buf, size_t n, int reps) {
  uint32_t t0 = micros();
  for (int r = 0; r < reps; r++) memset(buf, r & 0xFF, n);
  uint32_t dt = micros() - t0;
  return (double)n * reps / dt;  // bytes/us == MB/s
}

static void benchPsram() {
  rule("PSRAM allocation & bandwidth");
  const size_t PS = 1u << 20;   // 1 MB
  const size_t IN = 128u << 10; // 128 KB
  uint8_t *ps = (uint8_t *)heap_caps_malloc(PS, MALLOC_CAP_SPIRAM);
  uint8_t *in = (uint8_t *)heap_caps_malloc(IN, MALLOC_CAP_INTERNAL);
  if (ps) Serial.printf("  PSRAM   1 MB alloc OK   memset %.1f MB/s\n", bandwidthMBs(ps, PS, 8));
  else Serial.println("  PSRAM   1 MB alloc FAILED");
  if (in) Serial.printf("  internal 128 KB alloc OK memset %.1f MB/s\n", bandwidthMBs(in, IN, 64));
  free(ps);
  free(in);
  Serial.println("  (PSRAM is slower than internal — note this for parse buffers.)");
}

// --------------------------------------------------------------------------
static bool initBus() {
  rule("Bus & peripherals");
  pinMode(EPD_CS, OUTPUT);
  pinMode(SD_CS, OUTPUT);
  digitalWrite(EPD_CS, HIGH);  // both CS deselected before any bus traffic
  digitalWrite(SD_CS, HIGH);
  spiBus.begin(PIN_SCK, PIN_MISO, PIN_MOSI, -1);

  sdOk = SD.begin(SD_CS, spiBus);  // SD first, per shared-bus rules
  Serial.printf("  SD card         %s\n", sdOk ? "mounted" : "not found (EPUB step will be skipped)");

  uint32_t t0 = millis();
  panelOk = epd.begin();
  Serial.printf("  panel init      %s (%lu ms)\n",
                panelOk ? "OK" : "BUSY timeout — check wiring/panel", millis() - t0);
  return panelOk;
}

static void benchRefresh() {
  rule("E-ink refresh timing");
  if (!panelOk) { Serial.println("  (panel not ready — skipped)"); return; }

  uint32_t t0 = millis();
  epd.clearWhite();
  Serial.printf("  clear (full)        %lu ms\n", millis() - t0);

  // Checkerboard test pattern in PSRAM.
  uint8_t *buf = (uint8_t *)heap_caps_malloc(Epd5in0::BUFFER_SIZE, MALLOC_CAP_SPIRAM);
  if (!buf) buf = (uint8_t *)malloc(Epd5in0::BUFFER_SIZE);
  if (buf) {
    for (uint32_t i = 0; i < Epd5in0::BUFFER_SIZE; i++) buf[i] = (i & 1) ? 0xAA : 0x55;
    t0 = millis();
    epd.displayFull(buf);
    Serial.printf("  full refresh        %lu ms\n", millis() - t0);
    t0 = millis();
    epd.displayPartialFull(buf);
    Serial.printf("  partial refresh     %lu ms\n", millis() - t0);
    free(buf);
  }
}

// --------------------------------------------------------------------------
static uint16_t wordWidth(const char *w) {
  int16_t x1, y1;
  uint16_t bw, bh;
  canvas->getTextBounds(w, 0, 0, &x1, &y1, &bw, &bh);
  return bw;
}

// Word-wrap + paginate `text`; render page 1 into the canvas if `render`.
// Returns the page count. Reports nothing (caller times it).
static int paginate(const char *text, bool render) {
  if (!canvas) return 0;
  const int maxX = MARGIN_X + (Epd5in0::WIDTH - 2 * MARGIN_X);
  const int bottom = Epd5in0::HEIGHT - 34;
  int pages = 1, penX = MARGIN_X, y = TOP + LINE_H;
  bool onPage1 = render;

  canvas->setFont(&FreeSerif12pt7b);
  canvas->setTextColor(1);
  if (render) canvas->fillScreen(0);

  char word[80];
  const char *p = text;
  while (*p) {
    while (*p && isspace((unsigned char)*p)) p++;
    if (!*p) break;
    const char *s = p;
    while (*p && !isspace((unsigned char)*p)) p++;
    int len = p - s;
    if (len > 79) len = 79;
    memcpy(word, s, len);
    word[len] = 0;

    int ww = wordWidth(word);
    int need = (penX == MARGIN_X) ? ww : spaceW + ww;
    if (penX + need > maxX) {  // wrap
      y += LINE_H;
      penX = MARGIN_X;
      if (y > bottom) {  // new page
        pages++;
        y = TOP + LINE_H;
        onPage1 = false;
      }
    }
    if (penX != MARGIN_X) penX += spaceW;
    if (onPage1) {
      canvas->setCursor(penX, y);
      canvas->print(word);
    }
    penX += ww;
  }
  return pages;
}

static void benchRender() {
  rule("1-bit text render");
  canvas = new GFXcanvas1(Epd5in0::WIDTH, Epd5in0::HEIGHT);
  if (!canvas || !canvas->getBuffer()) {
    Serial.println("  canvas alloc FAILED");
    return;
  }
  canvas->setFont(&FreeSerif12pt7b);
  spaceW = wordWidth(" ");
  if (spaceW < 4) spaceW = 6;

  static const char *lorem =
      "It is a truth universally acknowledged, that a single man in possession "
      "of a good fortune, must be in want of a wife. However little known the "
      "feelings or views of such a man may be on his first entering a "
      "neighbourhood, this truth is so well fixed in the minds of the "
      "surrounding families, that he is considered the rightful property of "
      "some one or other of their daughters. ";

  uint32_t t0 = micros();
  int pages = paginate(lorem, true);
  Serial.printf("  paginate+render 1 page   %lu us  (%d page(s) of sample para)\n",
                (unsigned long)(micros() - t0), pages);

  if (panelOk) {
    t0 = millis();
    epd.displayFull(canvas->getBuffer(), /*invert=*/true);  // GFX 1=ink -> panel 0=ink
    Serial.printf("  blit + full refresh      %lu ms\n", millis() - t0);
  }
}

// --------------------------------------------------------------------------
// Crude XHTML->text: drop tags, decode a few entities, collapse whitespace.
static size_t stripTags(const char *in, size_t n, char *out) {
  size_t o = 0;
  bool inTag = false, lastSpace = false;
  for (size_t i = 0; i < n; i++) {
    char c = in[i];
    if (c == '<') { inTag = true; continue; }
    if (c == '>') {  // tag boundary becomes whitespace
      inTag = false;
      if (!lastSpace) { out[o++] = ' '; lastSpace = true; }
      continue;
    }
    if (inTag) continue;
    if (c == '&') {  // minimal entity handling
      if (!strncmp(in + i, "&amp;", 5)) { out[o++] = '&'; i += 4; }
      else if (!strncmp(in + i, "&lt;", 4)) { out[o++] = '<'; i += 3; }
      else if (!strncmp(in + i, "&gt;", 4)) { out[o++] = '>'; i += 3; }
      else if (!strncmp(in + i, "&#", 2)) { while (i < n && in[i] != ';') i++; out[o++] = ' '; }
      else out[o++] = '&';
      lastSpace = false;
      continue;
    }
    if (isspace((unsigned char)c)) {
      if (!lastSpace) { out[o++] = ' '; lastSpace = true; }
    } else {
      out[o++] = c;
      lastSpace = false;
    }
  }
  out[o] = 0;
  return o;
}

static void benchEpub() {
  rule("EPUB-style workload (SD chapter)");
  if (!sdOk) { Serial.println("  (no SD card — skipped)"); return; }

  const char *path = SD.exists("/sample.xhtml") ? "/sample.xhtml"
                     : SD.exists("/sample.txt") ? "/sample.txt"
                                                : nullptr;
  if (!path) {
    Serial.println("  put /sample.xhtml or /sample.txt on the card — skipped");
    return;
  }

  File f = SD.open(path);
  size_t n = f.size();
  Serial.printf("  file            %s (%u bytes)\n", path, (unsigned)n);
  reportMem("before");

  char *raw = (char *)heap_caps_malloc(n + 1, MALLOC_CAP_SPIRAM);
  char *text = (char *)heap_caps_malloc(n + 1, MALLOC_CAP_SPIRAM);
  if (!raw || !text) { Serial.println("  alloc FAILED (file too big?)"); free(raw); free(text); f.close(); return; }

  uint32_t t0 = millis();
  size_t got = f.read((uint8_t *)raw, n);
  raw[got] = 0;
  f.close();
  Serial.printf("  SD read         %lu ms (%.2f MB/s)\n", millis() - t0,
                (double)got / 1024.0 / 1024.0 / ((millis() - t0) / 1000.0 + 1e-6));

  t0 = micros();
  size_t tlen = stripTags(raw, got, text);
  Serial.printf("  strip tags      %lu us -> %u chars text\n",
                (unsigned long)(micros() - t0), (unsigned)tlen);

  if (canvas) {
    t0 = millis();
    int pages = paginate(text, false);  // measure full pagination cost
    uint32_t pagMs = millis() - t0;
    t0 = micros();
    paginate(text, true);               // render page 1
    Serial.printf("  paginate (all)  %lu ms -> %d pages\n", pagMs, pages);
    Serial.printf("  render page 1   %lu us\n", (unsigned long)(micros() - t0));
    if (panelOk) epd.displayFull(canvas->getBuffer(), true);
  }

  reportMem("after");
  Serial.printf("  min internal free since boot: %u  | min PSRAM free: %u\n",
                (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL),
                (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_SPIRAM));
  free(raw);
  free(text);
}

// --------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  uint32_t start = millis();
  while (!Serial && millis() - start < 3000) delay(10);
  delay(300);
  Serial.println("\n\n######## esp-read on-device EPUB benchmark ########");

  reportBoard();
  benchPsram();
  initBus();
  benchRefresh();
  benchRender();
  benchEpub();

  rule("Done");
  Serial.println("  Reading guide:");
  Serial.println("   - full refresh ~1.8s / partial ~0.7s is expected for this panel");
  Serial.println("   - page render should be well under a few hundred ms");
  Serial.println("   - pagination time x pages = cold-open cost; if large, cache it to flash");
  Serial.println("   - watch 'min internal free' — fragmentation, not PSRAM, is the usual limit");
}

void loop() { delay(1000); }
