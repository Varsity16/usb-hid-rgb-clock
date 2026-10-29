# Firefly RGB Clock

Turn a **Cosmic Byte Firefly (CB-GK-18)** mechanical keyboard into a clock, using nothing but Python.

Press a hotkey and the keyboard shows the time for a few seconds: the **hour** lights up on the `F1`–`F12` keys and the **minutes** fill the `1`–`6` keys. Then it returns to your normal color.

> The vendor ships no SDK or protocol documentation for this keyboard, and [OpenRGB](https://openrgb.org) doesn't detect it. The per-key RGB protocol used here was worked out by capturing USB traffic from the official software and decoding it. See [How it works](#how-it-works) and [How the protocol was decoded](#how-the-protocol-was-decoded).

<!-- Add a demo photo or GIF here, e.g.: -->
<!-- ![Demo](docs/demo.gif) -->

---

## Contents

- [Features](#features)
- [How to read the time](#how-to-read-the-time)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Using it with a hotkey (Windows)](#using-it-with-a-hotkey-windows)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [How the protocol was decoded](#how-the-protocol-was-decoded)
- [Limitations and warnings](#limitations-and-warnings)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## Features

- **Per-key RGB control** of the Firefly keyboard from Python, with no vendor software running.
- **Analog-style clock on the keys**: hour on the function row, minutes on the number row.
- **Blinking progress indicator** for the minutes (see below).
- **On-demand display**: press a global hotkey, see the time for a set number of seconds, then the keyboard goes back to your idle color.
- **Fast**: in hotkey mode the keyboard connection stays open, so the clock appears almost instantly.
- **Small and dependency-light**: one Python file, one dependency (`hidapi`).
- A built-in **key walker** to map LED indexes to physical keys, useful if you want to extend this to other layouts.

## How to read the time

| Part | Keys | Meaning |
|---|---|---|
| Hour | `F1` – `F12` | The **bright red** key is the current hour (12-hour format). The other F-keys are very dim. |
| Minutes | `1` – `6` | Each key stands for **10 minutes**. Keys fill from left to right as the hour goes by. |

Within each 10-minute block, the key being filled behaves like this:

- **First 5 minutes (0–4):** the key **blinks**.
- **Last 5 minutes (5–9):** the key stays **on**.

Keys for earlier blocks stay on, and keys for later blocks stay off.

| Time | Minute keys `1 2 3 4 5 6` | Notes |
|---|---|---|
| 1:04 | `◍ · · · · ·` | key 1 blinking |
| 1:05 | `● · · · · ·` | key 1 steady |
| 1:14 | `● ◍ · · · ·` | key 1 steady, key 2 blinking |
| 1:16 | `● ● · · · ·` | keys 1 and 2 steady |
| 1:44 | `● ● ● ● ◍ ·` | keys 1–4 steady, key 5 blinking |
| 1:55 | `● ● ● ● ● ●` | all six steady |

(`●` steady, `◍` blinking, `·` off.)

The resolution is therefore 5 minutes, which is enough to tell roughly where you are in the hour at a glance.

## Requirements

- A **Cosmic Byte Firefly CB-GK-18** keyboard (USB ID `04d9:a1cd`). Other Firefly models may share the protocol, but this is untested.
- **Python 3.8+**
- [`hidapi`](https://pypi.org/project/hidapi/) (`pip install hidapi`)
- **Windows** for the global hotkey mode. The other modes only use `hidapi`, but have only been tested on Windows.
- The official Cosmic Byte software should be **closed** while you use this, so the two don't fight over the keyboard.

## Installation

```bash
git clone https://github.com/Varsity16/usb-hid-rgb-clock.git
cd usb-hid-rgb-clock
pip install -r requirements.txt   # or: pip install hidapi
```

## Usage

```bash
python firefly_rgb.py <mode> [arguments]
```

| Mode | What it does |
|---|---|
| `esc` | Lights only the `Esc` key red. A quick check that everything works. |
| `walk START END` | Lights LED indexes `START`..`END` one at a time (1.5 s each) and prints the index, so you can map indexes to keys. |
| `once` | Shows the clock for `SHOW_SECONDS`, restores the idle color, and exits. |
| `hotkey` | Stays running. **Ctrl+Alt+T** shows the clock for `SHOW_SECONDS`, then restores the idle color. Windows only. |
| `clock` | Always-on clock. Not recommended, see [Limitations](#limitations-and-warnings). |
| `setbase R G B` | Sets the idle color (each value 0–255) and applies it. `setbase off` turns the keys off between uses. The color is saved in `base_color.txt` next to the script. |

Typical first run:

```bash
python firefly_rgb.py esc               # Esc turns red? Then the connection works.
python firefly_rgb.py setbase 0 255 255 # idle color = cyan
python firefly_rgb.py once              # show the time for a few seconds
```

## Using it with a hotkey (Windows)

Starting a new Python process on every keypress takes several seconds. The reliable fast option is `hotkey` mode: start it once, and it waits in the background for the key combination.

Create a launcher shortcut on your desktop (run in PowerShell from the project folder):

```powershell
$ws  = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$env:USERPROFILE\Desktop\Start Keyboard Clock.lnk")
$lnk.TargetPath       = (Get-Command pythonw).Source
$lnk.Arguments        = "`"$PWD\firefly_rgb.py`" hotkey"
$lnk.WorkingDirectory = "$PWD"
$lnk.WindowStyle      = 7
$lnk.Save()
```

Double-click the shortcut once after you log in, then press **Ctrl+Alt+T** whenever you want to see the time. `pythonw` runs without a console window; to stop it, end `pythonw.exe` in Task Manager. Nothing is installed as a startup item.

If Ctrl+Alt+T is already taken by another program, the script exits with an error. Change `HOTKEY_VK` (see below).

## Configuration

Settings live near the top of `firefly_rgb.py`:

| Setting | Default | Meaning |
|---|---|---|
| `SHOW_SECONDS` | `5` | How long the time stays visible. |
| `HOTKEY_VK` | `0x54` (`T`) | Virtual-key code of the hotkey letter, used with Ctrl+Alt. |
| `BASE_COLOR` | `(90, 90, 90)` | Fallback idle color if `setbase` hasn't been used. `None` = keys off. |
| `DIM_BACKGROUND` | `True` | Turn the rest of the keyboard dark while the time shows, so the lit keys stand out. |
| `MIN_ON`, `MIN_OFF` | blue / near black | Colors of lit and unlit minute keys. |
| `PACKET_DELAY` | `0.01` | Pause (seconds) after each USB packet. Lower it (e.g. `0.004`) for faster updates; raise it if keys glitch. |
| `SEND_PREAMBLE` | `True` | Replay the extra setup step seen in the captures. |
| `KEY_INDEX` | see file | Map from key name to LED index. |

Colors are given as `(r, g, b)` with values 0–255 and scaled down to the keyboard's 0–63 range.

## How it works

This section describes the protocol **as observed in USB captures**. It is not official documentation, and some parts are inferred.

### Device

| Item | Value |
|---|---|
| USB ID | `04d9:a1cd` (vendor ID `04d9` is Holtek; reported as "HTLTEK / FIREFLY KEYBOARD") |
| HID interfaces | 0: keyboard · 1: media keys + vendor page `ff02` · 2: vendor page **`ff01`** · 3: mouse-type |
| Lighting interface | Interface 2, usage page `0xff01` |

### Transport

Each lighting update uses two kinds of transfers to interface 2:

- **Control transfer, `SET_REPORT`**: feature report, report ID 0, **8 bytes** (`bmRequestType 0x21`, `bRequest 0x09`, `wValue 0x0300`, `wIndex 2`, `wLength 8`). In `hidapi`: `send_feature_report(b"\x00" + data)`.
- **Interrupt OUT**, endpoint 4, **64 bytes**. In `hidapi`: `write(b"\x00" + data)`.

### Frame layout

A full frame is sent every time (there is no "change one key" command). It consists of:

| Step | Control packet (8 bytes) | Data |
|---|---|---|
| Preamble | `30 00 00 00 00 55 aa 00` | one 64-byte packet (mostly leftover memory from the vendor software) |
| Block 0 | `12 00 04 00 00 55 aa 00` | 128 bytes (2 × 64): **key mask** |
| Block 1 | `12 00 04 01 00 55 aa 00` | 128 bytes: **red** |
| Block 2 | `12 00 04 02 00 55 aa 00` | 128 bytes: **green** |
| Block 3 | `12 00 04 03 00 55 aa 00` | 128 bytes: **blue** |
| Commit | `08 ..` | none |

Byte *N* of each block belongs to **LED index *N***.

- **Block 0 (mask):** `0x10` for every index that has a key, `0` for the rest. Indexes `77, 84, 86, 87, 92, 93` are empty.
- **Blocks 1–3 (R, G, B):** values `0x00`–`0x3f` (6 bits per channel).
- Indexes `101`–`104` are four extra lights (probably an edge strip or logo) that stayed lit in some captures.

### LED indexes

Indexes follow the physical layout left to right, row by row:

| Index | Key |
|---|---|
| 0 | `Esc` |
| 1 – 12 | `F1` – `F12` |
| 13, 14, 15 | `Print Screen`, `Scroll Lock`, `Pause` |
| 16 | `` ` `` |
| 17 – 22 | `1` – `6` (confirmed; the rest of the number row most likely continues from 23, not verified) |

Use `walk` mode to map the remaining keys on your own board.

## How the protocol was decoded

The method is general and works for many cheap USB peripherals:

1. **Identify the device**: list HID interfaces with `hidapi` and unplug the keyboard to see which ones disappear. This gave `04d9:a1cd` and two vendor-defined interfaces (`ff01`, `ff02`).
2. **Capture the traffic**: Wireshark with **USBPcap**, capturing only the keyboard's USB device.
3. **Run controlled experiments** in the vendor's software, **one change at a time**, one capture per change: all red, all green, all blue, only `Esc` red, only `F1` red, only `F2` red, `Esc` green.
4. **Compare captures** to separate what changes from what doesn't:
   - all red vs green vs blue moved the `0x3f` values between three blocks, so each block is one color channel;
   - `Esc` vs `F1` vs `F2` moved a single non-zero byte from position 0 to 1 to 2, so the position is the key index;
   - the same 99 positions were set in every "all keys" capture, which revealed the key mask and the unused slots.
5. **Replay** the decoded sequence from Python, starting with a single key (`Esc`), then build up to full frames.
6. **Map the layout** by lighting indexes one at a time and noting which key lights.

A note for anyone repeating this: raw `.pcapng` captures also record every key you press while capturing, so don't publish them.

## Limitations and warnings

- **Frames appear to be saved in the keyboard.** After unplugging and replugging the keyboard, it came back showing the last clock colors, which suggests each update is written to non-volatile memory. It's unknown how many rewrites that memory tolerates, so avoid sending frames constantly. For this reason the always-on `clock` mode is **not recommended**, and the hotkey mode sends only a handful of frames per use.
- **The idle color is not read from the keyboard.** The script can't query the current color, so it returns to the color saved with `setbase`. If you change the color in the vendor software, run `setbase` again.
- **Built-in effects aren't restored.** After the clock, the keyboard returns to a static color, not to effects like Wave.
- **Some bytes are not understood.** The preamble's data packet and the trailing bytes of the commit packet look like uninitialized memory from the vendor software, and are replayed exactly as captured. If you see odd behavior, try `SEND_PREAMBLE = False`.
- **Only tested on one keyboard and on Windows.**
- The hotkey mode does not reconnect if the keyboard is unplugged or the PC sleeps. Start it again.

## Troubleshooting

| Problem | What to try |
|---|---|
| `Keyboard's ff01 interface not found.` | Check the USB connection and the USB ID (`04d9:a1cd`). Make sure nothing else has the device open. |
| Nothing changes after `esc` | Close the Cosmic Byte software and any RGB tool, then try again. Try a different USB port. |
| `Could not register Ctrl+Alt+T` | Another program uses that hotkey. Change `HOTKEY_VK` or close the other program. |
| Keys flicker or don't update | Raise `PACKET_DELAY` back toward `0.01`. |
| Clock is hard to read against a bright idle color | Keep `DIM_BACKGROUND = True`, or change `MIN_ON` to a color that contrasts with your idle color. |
| Hotkey stopped working | The background process may have ended (sleep or unplug). Start the launcher again. |
| No error messages in hotkey mode | `pythonw` hides the console. Run `python firefly_rgb.py hotkey` in a terminal to see errors. |

## Roadmap

- Restore the keyboard's built-in effect after the clock (needs the "set effect" command decoded).
- Reconnect automatically after sleep or unplugging.
- Read back the keyboard's current lighting, if the device supports it.
- Support other Firefly models (`CB-GK-16`, `CB-GK-34`, `CB-GK-37`), and possibly contribute a driver to [OpenRGB](https://openrgb.org).
- Optional extras: date display, timers, CPU/GPU load on the keys.

## Disclaimer

This is an independent, unofficial project and is **not affiliated with or endorsed by Cosmic Byte or Holtek**. It was developed by analyzing the traffic of a keyboard I own, for the purpose of interoperability. The protocol notes come from observation and may be incomplete or wrong. Use at your own risk: sending unexpected data to any USB device can cause unexpected behavior, and I take no responsibility for damage to your hardware.

## License

MIT. See [LICENSE](LICENSE).
