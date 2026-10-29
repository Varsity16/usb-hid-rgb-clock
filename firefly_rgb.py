"""
Cosmic Byte Firefly (CB-GK-18) per-key lighting, decoded from USB captures.
VID 04d9 / PID a1cd, vendor interface with usage page 0xff01 (interface 2).

Protocol as seen in the captures (NOT official documentation):
  feature report (8 bytes, report ID 0)  -> announces what comes next
  interrupt OUT  (64 bytes)              -> data
Frame = preamble + 4 blocks of 128 bytes + commit
  block 0 = key mask (0x10 where a key exists, 0 elsewhere)
  block 1 = red,  block 2 = green,  block 3 = blue   (each 0..0x3f)
  byte N of each block = LED index N  (Esc=0, F1=1, F2=2 so far)

Usage:
  python firefly_rgb.py esc            # Esc red, everything else off
  python firefly_rgb.py walk 0 40      # light LED index 0..40 one by one
  python firefly_rgb.py clock          # always-on clock
  python firefly_rgb.py once           # show the time for 5 s, then exit
  python firefly_rgb.py setbase R G B  # idle color after the clock (0-255 each), or: setbase off
  python firefly_rgb.py hotkey         # Ctrl+Alt+T shows the time for 5 s (needs the script running)
Close the Cosmic Byte software first.
"""
import os
import sys
import time
from datetime import datetime

import hid

VID, PID, USAGE_PAGE = 0x04D9, 0xA1CD, 0xFF01
N_LEDS = 105
UNUSED = {77, 84, 86, 87, 92, 93}      # indexes where the captures had no key
EXTRA = [101, 102, 103, 104]           # extra lights, blue in your captures
PACKET_DELAY = 0.01                     # pause after each packet; lower = faster (try 0.004)
SEND_PREAMBLE = True                    # replay the "30" step seen in captures

# Filled in from the captures; walk mode helps you add the rest.
KEY_INDEX = {"Esc": 0}
KEY_INDEX.update({"F%d" % n: n for n in range(1, 13)})   # F1..F12 = 1..12
KEY_INDEX.update({str(n): 16 + n for n in range(1, 7)})  # 1..4 confirmed; 5, 6 = 21, 22 assumed

# Bytes copied from your captures (the tail of PREAMBLE_DATA and the last
# bytes of COMMIT look like leftover memory in the vendor software).
PREAMBLE_CTRL = bytes.fromhex("30 00 00 00 00 55 aa 00")
PREAMBLE_DATA = bytes.fromhex(
    "3f 00 00 00 3f 00 3f 3f 00 00 00 3f 00 3f 3f 3f 00 3f 00 00 00 00 00 00 "
    "20 e0 cb 06 00 00 00 00 00 00 00 00 80 0c bd 02 98 bd 64 00 a4 43 c6 67 "
    "00 00 00 00 5a 00 00 00 f8 be 64 00 00 a9 83 08")
COMMIT_CTRL = bytes.fromhex("08 37 3f 04 00 00 c4 3b")


def open_dev():
    for d in hid.enumerate(VID, PID):
        if d["usage_page"] == USAGE_PAGE:
            dev = hid.device()
            dev.open_path(d["path"])
            return dev
    raise SystemExit("Keyboard's ff01 interface not found.")


def ctrl(dev, data8):
    if dev.send_feature_report(bytes([0]) + data8) < 0:
        raise RuntimeError("feature report failed: %s" % dev.error())
    time.sleep(PACKET_DELAY)


def out(dev, data64):
    if dev.write(bytes([0]) + data64) < 0:
        raise RuntimeError("write failed: %s" % dev.error())
    time.sleep(PACKET_DELAY)


def send_frame(dev, rgb):
    """rgb: {led_index: (r, g, b)} with 0..255 values; everything else off."""
    mask, red, green, blue = (bytearray(128) for _ in range(4))
    for i in range(N_LEDS):
        if i not in UNUSED:
            mask[i] = 0x10
    for i, (r, g, b) in rgb.items():
        red[i], green[i], blue[i] = r >> 2, g >> 2, b >> 2   # 0..255 -> 0..63
    if SEND_PREAMBLE:
        ctrl(dev, PREAMBLE_CTRL)
        out(dev, PREAMBLE_DATA)
    for n, block in enumerate((mask, red, green, blue)):
        ctrl(dev, bytes([0x12, 0x00, 0x04, n, 0x00, 0x55, 0xAA, 0x00]))
        out(dev, bytes(block[:64]))
        out(dev, bytes(block[64:]))
    ctrl(dev, COMMIT_CTRL)


def need_clock_keys():
    need = ["F%d" % n for n in range(1, 13)] + [str(n) for n in range(1, 7)]
    missing = [k for k in need if k not in KEY_INDEX]
    if missing:
        raise SystemExit("Add these to KEY_INDEX first (use walk mode): %s" % missing)


MIN_ON = (0, 120, 255)
MIN_OFF = (0, 5, 10)


def blink_phase():
    """True for one second, False for the next, and so on."""
    return int(time.time()) % 2 == 0


def clock_frame(blink_on=True):
    """Hour: one bright F-key.  Minutes: keys 1-6, one key per 10 minutes.
    In the first 5 minutes of each 10-minute block the current key blinks;
    in the last 5 minutes it stays on.  Earlier keys stay on, later ones off."""
    now = datetime.now()
    hour12 = now.hour % 12 or 12
    current = now.minute // 10             # 0..5 -> the key being "filled"
    second_half = now.minute % 10 >= 5
    frame = {}
    for n in range(1, 13):
        frame[KEY_INDEX["F%d" % n]] = (255, 0, 0) if n == hour12 else (10, 0, 0)
    for i in range(6):
        if i < current:
            on = True
        elif i == current:
            on = second_half or blink_on
        else:
            on = False
        frame[KEY_INDEX[str(i + 1)]] = MIN_ON if on else MIN_OFF
    return frame


def clock(dev):
    """Always-on clock. Sends a new frame only when something changes."""
    need_clock_keys()
    last = None
    while True:
        frame = clock_frame(blink_phase())
        if frame != last:
            send_frame(dev, frame)
            last = frame
        time.sleep(0.2)


# ---- hotkey mode: show the time for a few seconds, then go back to BASE ----
HOTKEY_VK = 0x54                 # 'T'  -> Ctrl+Alt+T
SHOW_SECONDS = 5
BASE_COLOR = (90, 90, 90)        # idle lighting; None = all keys off
DIM_BACKGROUND = True            # True: rest of the keyboard goes dark while the time shows


BASE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_color.txt")


def load_base():
    """Idle color: saved with 'setbase', else BASE_COLOR above."""
    try:
        text = open(BASE_FILE).read().strip().lower()
        if text == "off":
            return None
        r, g, b = (max(0, min(255, int(x))) for x in text.split())
        return (r, g, b)
    except Exception:
        return BASE_COLOR


def base_frame():
    color = load_base()
    if color is None:
        return {}
    return {i: color for i in range(N_LEDS)
            if i not in UNUSED and i not in EXTRA}


def show_once(dev):
    """Show the clock for SHOW_SECONDS, go back to BASE, then return (script exits)."""
    need_clock_keys()
    end, last = time.time() + SHOW_SECONDS, None
    while time.time() < end:
        frame = {} if DIM_BACKGROUND else base_frame()
        frame.update(clock_frame(blink_phase()))
        if frame != last:
            send_frame(dev, frame)
            last = frame
        time.sleep(0.2)
    send_frame(dev, base_frame())


def hotkey_clock(dev):
    import ctypes
    from ctypes import wintypes
    need_clock_keys()
    user32 = ctypes.windll.user32
    MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY = 0x1, 0x2, 0x4000, 0x0312
    if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, HOTKEY_VK):
        raise SystemExit("Could not register Ctrl+Alt+T (another program may use it).")
    send_frame(dev, base_frame())
    print("Ready: press Ctrl+Alt+T to show the time for %d s. Ctrl+C to quit." % SHOW_SECONDS)
    msg = wintypes.MSG()
    try:
        while True:
            if user32.PeekMessageW(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, 1):
                end, last = time.time() + SHOW_SECONDS, None
                while time.time() < end:
                    frame = {} if DIM_BACKGROUND else base_frame()
                    frame.update(clock_frame(blink_phase()))
                    if frame != last:
                        send_frame(dev, frame)
                        last = frame
                    time.sleep(0.2)
                send_frame(dev, base_frame())
                # ignore presses that happened while the time was showing
                while user32.PeekMessageW(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, 1):
                    pass
            else:
                time.sleep(0.05)
    finally:
        user32.UnregisterHotKey(None, 1)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "esc"
    dev = open_dev()
    try:
        if mode == "esc":
            send_frame(dev, {KEY_INDEX["Esc"]: (255, 0, 0)})
        elif mode == "walk":
            lo, hi = int(sys.argv[2]), int(sys.argv[3])
            for i in range(lo, hi + 1):
                if i in UNUSED:
                    continue
                print("LED index", i, "-> which key is red?")
                send_frame(dev, {i: (255, 0, 0)})
                time.sleep(1.5)
        elif mode == "clock":
            clock(dev)
        elif mode == "hotkey":
            hotkey_clock(dev)
        elif mode == "once":
            show_once(dev)
        elif mode == "setbase":
            # python firefly_rgb.py setbase 255 120 0   |   setbase off
            text = "off" if sys.argv[2].lower() == "off" else " ".join(sys.argv[2:5])
            open(BASE_FILE, "w").write(text)
            send_frame(dev, base_frame())
            print("Idle color saved:", text)
        else:
            raise SystemExit(__doc__)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
