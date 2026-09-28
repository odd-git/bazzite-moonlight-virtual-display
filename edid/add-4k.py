#!/usr/bin/env python3
"""Add a 3840x2160@60 mode to an edid-generator EDID, keeping the monitor's identity.

edid-generator writes one detailed timing. We replace the "range limits" descriptor (slot 2) with a
second detailed timing, so the same fake monitor offers both the phone mode and 4K. The serial and
name stay the same: the GNOME portal permission is tied to them, a new identity means a new dialog.

Usage: add-4k.py 2856x1280.bin virtual.bin
"""
import sys

def dtd(pclk_khz, ha, hso, hsw, htot, va, vso, vsw, vtot, hmm, vmm, hpos, vpos):
    hb, vb, pc = htot - ha, vtot - va, pclk_khz // 10
    return bytes([pc & 0xff, pc >> 8, ha & 0xff, hb & 0xff, (ha >> 8) << 4 | hb >> 8,
                  va & 0xff, vb & 0xff, (va >> 8) << 4 | vb >> 8,
                  hso & 0xff, hsw & 0xff, (vso & 0xf) << 4 | vsw & 0xf,
                  (hso >> 8 & 3) << 6 | (hsw >> 8 & 3) << 4 | (vso >> 4 & 3) << 2 | (vsw >> 4 & 3),
                  hmm & 0xff, vmm & 0xff, (hmm >> 8) << 4 | vmm >> 8, 0, 0,
                  0x18 | vpos << 2 | hpos << 1])

b = bytearray(open(sys.argv[1], 'rb').read())
assert b[54 + 36 + 3] == 0xfd, "slot 2 is not the range limits descriptor"
# CVT reduced blanking: 533.25 MHz, 3840 3888 3920 4000 / 2160 2163 2168 2222, +hsync -vsync
b[54 + 36:54 + 54] = dtd(533250, 3840, 48, 32, 4000, 2160, 3, 5, 2222, 1016, 572, 1, 0)
b[127] = -sum(b[:127]) % 256
open(sys.argv[2], 'wb').write(b)
