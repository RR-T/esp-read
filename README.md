# esp-read

A DIY e-ink e-reader built on an ESP32-S3: a Seeed XIAO ESP32-S3 Plus driving
a Waveshare 5" (960 × 552) e-paper panel. It's battery-powered and spends its
time in deep sleep.

| Path | What it is |
|---|---|
| `CLAUDE.md` | Quick-reference project context: hardware, pins and rules. |
| `ereader-build-guide.md` | The full design rationale. |
| `docs/` | Bring-up and assembly plan, debugging notes, CrossPoint adoption research. |
| `firmware/` | Firmware benchmarks (EPUB feasibility, WiFi) and the panel driver port. |
| `service/` | Desktop library server (Python/FastAPI/Docker) that serves books to the reader. |
| `simulator/` | Pixel-accurate tkinter mock-up of the panel, for building the UI without hardware. |
| `hardware/` | Protoboard build-sheet generators and PDFs. |
| `enclosure/` | 3D-printed case: SolidCraft model, measurements, renders. |

The reader only handles DRM-free books.
