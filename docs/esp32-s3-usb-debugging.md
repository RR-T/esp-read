# Debugging the XIAO ESP32-S3 over USB

A practical guide for this project's firmware (PlatformIO + Arduino framework),
on Fedora Linux. Tailored to the `firmware/epub-benchmark/` config, but applies
to any env on this board.

## Why the S3 is nice here

The ESP32-S3 has a **built-in USB Serial/JTAG controller** wired straight to the
XIAO's USB-C port (no CP2102/CH340 bridge chip, no external JTAG probe). One
cable gives you both:

- a **serial console** (`/dev/ttyACM0`) for `Serial.print` + flashing, and
- a **JTAG interface** for real source-level debugging (breakpoints, stepping,
  variable inspection).

Our `platformio.ini` already sets `-DARDUINO_USB_MODE=1` (Hardware CDC **and**
JTAG) and `-DARDUINO_USB_CDC_ON_BOOT=1` (so `Serial` = native USB), which is
exactly the mode that supports both at once.

> The board shows up as **`/dev/ttyACM0`** (native USB CDC), *not* `ttyUSB0`
> (that's for boards with a bridge chip).

---

## 0. One-time setup (Fedora)

**Serial access — already done.** You're in the `dialout` group, which owns
`/dev/ttyACM*`, so flashing and the monitor work with no extra steps. (If a
future user isn't: `sudo usermod -aG dialout $USER`, then log out/in.)

**JTAG access — needed only for source-level debugging (§3).** OpenOCD opens the
JTAG interface as a raw USB device (libusb), which `dialout` does *not* cover.
Install PlatformIO's udev rules once:

```bash
curl -fsSL https://raw.githubusercontent.com/platformio/platformio-core/develop/platformio/assets/system/99-platformio-udev.rules \
  | sudo tee /etc/udev/rules.d/99-platformio-udev.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
# then unplug and replug the board
```

These grant access to Espressif USB-JTAG devices (USB VID `303a`).

**The `pio` CLI.** If `pio` isn't on your PATH but you use the VS Code
PlatformIO extension, the CLI lives at `~/.platformio/penv/bin/pio`:

```bash
export PATH="$HOME/.platformio/penv/bin:$PATH"   # add to ~/.bashrc to persist
```

Or install standalone: `pipx install platformio`. All commands below can also be
run from the VS Code PlatformIO toolbar (✓ build, → upload, 🔌 monitor, 🐞 debug).

---

## 1. Serial (printf) debugging — the everyday path

This is 90% of embedded debugging. Flash, then watch the console.

```bash
cd firmware/epub-benchmark
pio run -e xiao_s3 -t upload          # build + flash over USB
pio device monitor -e xiao_s3         # opens at 115200 (from monitor_speed)
```

Or combined: `pio run -e xiao_s3 -t upload -t monitor`.

In code, `Serial` writes to USB:

```cpp
Serial.begin(115200);
Serial.printf("free heap: %u\n", ESP.getFreeHeap());
```

**Catch early output.** With native USB CDC, the host takes a moment to
enumerate the port after reset, so prints in the first ~1s can be lost. Wait for
the host to attach before printing (the benchmark already does this):

```cpp
Serial.begin(115200);
uint32_t t0 = millis();
while (!Serial && millis() - t0 < 3000) delay(10);   // wait up to 3s for host
```

**Turn crashes into file:line.** Add the exception decoder to the monitor so a
guru-meditation backtrace is symbolized automatically:

```ini
monitor_filters = esp32_exception_decoder
```

Monitor keys: **`Ctrl-C` quits**. pyserial's control menu is a *chord* —
`Ctrl-T` is a prefix, so nothing shows until you press a second key (e.g.
`Ctrl-T` then `Ctrl-H` for help, `Ctrl-T` then `Ctrl-R`/`Ctrl-D` to toggle
RTS/DTR). Filters are **not** toggled live via that menu — set them at launch
with `monitor_filters` (above) or `-f`, e.g.
`pio device monitor -e xiao_s3 -f esp32_exception_decoder -f time`.

> Some terminals (including VS Code's integrated terminal) intercept `Ctrl-T`,
> so the chord may never reach miniterm. If so, run the monitor in an external
> terminal (GNOME Terminal / Konsole) — but you rarely need the menu anyway.

---

## 2. Diagnosing a crash / reboot

When the board panics it prints a backtrace and reboots. With
`monitor_filters = esp32_exception_decoder` you get symbolized frames directly.
Otherwise, decode the raw `Backtrace: 0x...` line:

```bash
pio pkg exec -- xtensa-esp32s3-elf-addr2line \
  -e .pio/build/xiao_s3/firmware.elf 0x42001234 0x42005678
```

Other signals:

- **Reset reason** — print it at boot to tell a crash from a clean wake:
  ```cpp
  Serial.printf("reset reason: %d\n", esp_reset_reason());   // see esp_reset_reason_t
  ```
  (`ESP_RST_PANIC` = crashed, `ESP_RST_DEEPSLEEP` = normal wake, `ESP_RST_BROWNOUT`
  = power/battery issue.)
- **Brownout** messages usually mean power delivery — suspect USB current, or a
  battery/regulator problem, not your code.
- **Core dump**: on panic the ESP can save a core dump to flash; read it with
  `pio run -e xiao_s3 -t` … or `espcoredump.py`. Usually the backtrace is enough.

---

## 3. Source-level debugging (breakpoints) over built-in JTAG

No external hardware needed — the S3's built-in JTAG does it over the same cable.

Add a debug configuration to the env (or a dedicated debug env) in
`platformio.ini`:

```ini
[env:xiao_s3]
; ... existing settings ...
debug_tool = esp-builtin        ; use the S3's built-in USB-JTAG
debug_init_break = tbreak setup ; halt at setup() on launch
build_type = debug              ; -Og -ggdb (better stepping; optional)
```

Then:

```bash
pio debug -e xiao_s3            # CLI (GDB TUI)
```

or in VS Code: **Run → Start Debugging** (the PlatformIO debug session). You get
breakpoints, single-step, call stack, watch/inspect variables and memory, and
peripheral views.

Notes / caveats:

- `build_type = debug` lowers optimization so stepping matches the source. You
  can debug an optimized build too, but expect "value optimized out" and jumpy
  stepping.
- **Flash breakpoints are limited** (the S3 has 2 hardware breakpoints). Prefer a
  few well-placed ones over many.
- The debug session drives the same USB device as the monitor — **close the
  serial monitor before debugging**, or the port is busy.
- Debugging **deep-sleep** code is inherently awkward (see §4).

---

## 4. S3 / deep-sleep gotchas (important for this project)

- **Deep sleep kills the USB connection.** When the firmware calls
  `esp_deep_sleep_start()`, the USB Serial/JTAG peripheral powers down — the
  serial port **and** any JTAG session vanish, and the port re-appears only on
  the next wake/reset. Our whole reader is a deep-sleep-per-page loop, so:
  - While actively debugging a wake cycle, temporarily **disable the sleep call**
    (e.g. a `#define DEBUG_NO_SLEEP`) so the port stays up.
  - Or **log to SD** across sleeps and read it back, rather than relying on a live
    console.
  - Expect the monitor to disconnect each time the device sleeps; reconnect on
    wake. This is normal, not a fault.
- **Native-USB re-enumeration after flashing.** The port drops and re-appears
  around a flash/reset; if the monitor doesn't reconnect, replug or re-run the
  monitor. If flashing itself is flaky, force a clean reset after upload:
  ```ini
  board_upload.after_reset = hard_reset
  ```
- **`USB_MODE` conflict with USB-MSC.** `ARDUINO_USB_MODE=1` (our setting) gives
  CDC + JTAG — the right choice for debugging. CrossPoint's USB mass-storage mode
  needs TinyUSB (`ARDUINO_USB_MODE=0`), which **disables the built-in JTAG**. You
  can't have hardware JTAG debugging and USB-MSC in the same build; pick per task.
- **Don't enable WiFi without the U.FL antenna attached.** (Irrelevant to the
  benchmark, which uses no WiFi — but a rule for later firmware.)

---

## 5. Recovery — when it won't flash or is bootlooping

Force **download mode** manually (bypasses a crashed/hung app):

1. Hold the **BOOT** button (labelled `B`).
2. Tap **RESET** (`R`).
3. Release **BOOT**.

The board is now waiting for a flash regardless of what firmware was on it. Then
`pio run -e xiao_s3 -t upload`.

Wipe everything (clears NVS, a corrupt filesystem, bad OTA state):

```bash
pio run -e xiao_s3 -t erase
```

If the port disappears entirely and manual download mode doesn't help, try a
different USB-C cable/port (some cables are power-only) before suspecting the
board.

---

## 6. Cheat sheet

| Task | Command |
|------|---------|
| Build | `pio run -e xiao_s3` |
| Flash | `pio run -e xiao_s3 -t upload` |
| Monitor | `pio device monitor -e xiao_s3` |
| Flash + monitor | `pio run -e xiao_s3 -t upload -t monitor` |
| List ports | `pio device list` (or `ls /dev/ttyACM*`) |
| Source-level debug | `pio debug -e xiao_s3` (needs `debug_tool = esp-builtin`) |
| Decode an address | `pio pkg exec -- xtensa-esp32s3-elf-addr2line -e .pio/build/xiao_s3/firmware.elf 0x…` |
| Erase flash | `pio run -e xiao_s3 -t erase` |
| Manual download mode | hold **B**, tap **R**, release **B** |

**Recommended `platformio.ini` additions for debugging:**

```ini
monitor_filters = esp32_exception_decoder   ; symbolized crash backtraces
debug_tool = esp-builtin                    ; source-level debug over built-in JTAG
debug_init_break = tbreak setup
```
