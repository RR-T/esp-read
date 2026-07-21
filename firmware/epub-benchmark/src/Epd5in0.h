// Minimal driver for the Waveshare 5inch e-Paper (EPD_5in0), 960x552, 1-bit.
//
// Controller: SSD16xx / SSD1677-family (confirmed from Waveshare's init sequence
// — 0x12 SWRESET, 0x18 temp, 0x01 driver-output, 0x11 data-entry, 0x44/0x45 RAM
// window, 0x4E/0x4F counters, 0x24/0x26 write-RAM, 0x3C border, 0x22+0x20 update).
// No custom LUT — the panel uses its internal OTP waveform.
//
// Buffer format: 1-bit packed, MSB-first, 120 bytes/row, 66,240 bytes total,
// bit 1 = white, bit 0 = black (same as the simulator's MonoFrameBuffer and
// CrossPoint's HalDisplay). `invert` flips this for sources that use 1 = ink
// (e.g. Adafruit GFXcanvas1).
//
// This is deliberately small and faithful to the Waveshare init so it can be
// lifted straight into CrossPoint's EInkDisplay as the port seed.

#pragma once
#include <Arduino.h>
#include <SPI.h>

class Epd5in0 {
public:
  static const uint16_t WIDTH = 960;
  static const uint16_t HEIGHT = 552;
  static const uint32_t BUFFER_SIZE = (uint32_t)(WIDTH / 8) * HEIGHT;  // 66240

  Epd5in0(SPIClass &spi, int8_t cs, int8_t dc, int8_t rst, int8_t busy,
          uint32_t spiHz = 8000000);

  bool begin();                 // full init; false if BUSY never releases
  void clearWhite();
  void displayFull(const uint8_t *image, bool invert = false);      // ~1.8s
  void displayPartialFull(const uint8_t *image, bool invert = false);  // ~0.7s
  void sleep();

private:
  SPIClass &_spi;
  int8_t _cs, _dc, _rst, _busy;
  SPISettings _settings;

  void reset();
  void cmd(uint8_t c);
  void data(uint8_t d);
  void streamRam(uint8_t reg, const uint8_t *buf, bool invert, uint8_t fill,
                 bool useFill);
  bool waitBusy(uint32_t timeoutMs = 30000);
  void setWindowFull();
  void turnOn(uint8_t mode);     // 0xF7 full, 0xFF partial
};
