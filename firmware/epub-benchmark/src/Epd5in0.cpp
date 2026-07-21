#include "Epd5in0.h"

Epd5in0::Epd5in0(SPIClass &spi, int8_t cs, int8_t dc, int8_t rst, int8_t busy,
                 uint32_t spiHz)
    : _spi(spi), _cs(cs), _dc(dc), _rst(rst), _busy(busy),
      _settings(spiHz, MSBFIRST, SPI_MODE0) {}

void Epd5in0::reset() {
  digitalWrite(_rst, HIGH);
  delay(20);
  digitalWrite(_rst, LOW);
  delay(2);
  digitalWrite(_rst, HIGH);
  delay(20);
}

void Epd5in0::cmd(uint8_t c) {
  _spi.beginTransaction(_settings);
  digitalWrite(_dc, LOW);
  digitalWrite(_cs, LOW);
  _spi.transfer(c);
  digitalWrite(_cs, HIGH);
  _spi.endTransaction();
}

void Epd5in0::data(uint8_t d) {
  _spi.beginTransaction(_settings);
  digitalWrite(_dc, HIGH);
  digitalWrite(_cs, LOW);
  _spi.transfer(d);
  digitalWrite(_cs, HIGH);
  _spi.endTransaction();
}

// Stream a whole RAM bank in one CS-held transaction (fast path). Either copies
// `buf` (optionally inverted) or writes a constant `fill`.
void Epd5in0::streamRam(uint8_t reg, const uint8_t *buf, bool invert,
                        uint8_t fill, bool useFill) {
  cmd(reg);
  _spi.beginTransaction(_settings);
  digitalWrite(_dc, HIGH);
  digitalWrite(_cs, LOW);
  for (uint32_t i = 0; i < BUFFER_SIZE; i++) {
    uint8_t b = useFill ? fill : (invert ? (uint8_t)~buf[i] : buf[i]);
    _spi.transfer(b);
  }
  digitalWrite(_cs, HIGH);
  _spi.endTransaction();
}

bool Epd5in0::waitBusy(uint32_t timeoutMs) {
  uint32_t start = millis();
  while (digitalRead(_busy) == HIGH) {  // HIGH = busy on this panel
    if (millis() - start > timeoutMs) return false;
    delay(1);
  }
  return true;
}

void Epd5in0::turnOn(uint8_t mode) {
  cmd(0x22);
  data(mode);
  cmd(0x20);
  waitBusy();
}

// RAM window + address counters — exact values from Waveshare's EPD_5in0 init.
void Epd5in0::setWindowFull() {
  cmd(0x11);  // data entry mode
  data(0x01);
  cmd(0x44);  // RAM X start/end (in bytes)
  data(0x00);
  data(0x00);
  data((uint8_t)((WIDTH - 1) & 0xFF));
  data((uint8_t)((WIDTH - 1) >> 8));
  cmd(0x45);  // RAM Y start/end
  data((uint8_t)((HEIGHT - 1) & 0xFF));
  data((uint8_t)((HEIGHT - 1) >> 8));
  data(0x00);
  data(0x00);
  cmd(0x4E);  // RAM X counter
  data(0x00);
  data(0x00);
  cmd(0x4F);  // RAM Y counter
  data(0x00);
  data(0x00);
}

bool Epd5in0::begin() {
  pinMode(_cs, OUTPUT);
  pinMode(_dc, OUTPUT);
  pinMode(_rst, OUTPUT);
  pinMode(_busy, INPUT);
  digitalWrite(_cs, HIGH);

  reset();
  if (!waitBusy()) return false;
  cmd(0x12);  // SWRESET
  if (!waitBusy()) return false;

  cmd(0x18);  // temperature sensor: use internal
  data(0x80);

  cmd(0x0C);  // booster soft start
  data(0xAE);
  data(0xC7);
  data(0xC3);
  data(0xC0);
  data(0x80);

  cmd(0x01);  // driver output control (gate lines = HEIGHT)
  data((uint8_t)((HEIGHT - 1) & 0xFF));
  data((uint8_t)((HEIGHT - 1) >> 8));
  data(0x02);

  setWindowFull();
  if (!waitBusy()) return false;

  cmd(0x3C);  // border waveform
  data(0x01);
  return true;
}

void Epd5in0::clearWhite() {
  setWindowFull();
  streamRam(0x24, nullptr, false, 0xFF, true);  // BW RAM = white
  streamRam(0x26, nullptr, false, 0xFF, true);  // "previous" RAM = white
  turnOn(0xF7);
}

void Epd5in0::displayFull(const uint8_t *image, bool invert) {
  setWindowFull();
  streamRam(0x24, image, invert, 0, false);
  turnOn(0xF7);
}

// Approximate partial: re-writes the BW RAM and runs the fast update mode. A
// production partial refresh also seeds the 0x26 "previous" bank and tweaks the
// border — this is enough to measure the ~0.7s partial-update cost.
void Epd5in0::displayPartialFull(const uint8_t *image, bool invert) {
  setWindowFull();
  streamRam(0x24, image, invert, 0, false);
  turnOn(0xFF);
}

void Epd5in0::sleep() {
  cmd(0x10);  // deep sleep mode
  data(0x01);
}
