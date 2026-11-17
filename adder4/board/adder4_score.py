"""Score a 4-bit adder bitstream.

8 inputs, 256 rows. Each row passes only when s0, s1, s2, s3, and cout
all match. One pass over the truth table (256 measurements).
"""

from machine import Pin
import time
import ice

a0 = Pin(20, Pin.OUT)
a1 = Pin(24, Pin.OUT)
a2 = Pin(30, Pin.OUT)
a3 = Pin(25, Pin.OUT)
b0 = Pin(28, Pin.OUT)
b1 = Pin(29, Pin.OUT)
b2 = Pin(2, Pin.OUT)
b3 = Pin(3, Pin.OUT)
s0 = Pin(22, Pin.IN)
s1 = Pin(23, Pin.IN)
s2 = Pin(27, Pin.IN)
s3 = Pin(26, Pin.IN)
cout = Pin(33, Pin.IN)

_fpga = None
REPEATS = 1


def _get_fpga():
    global _fpga
    if _fpga is None:
        _fpga = ice.fpga(
            cdone=Pin(40),
            clock=Pin(21),
            creset=Pin(31),
            cram_cs=Pin(5),
            cram_mosi=Pin(4),
            cram_sck=Pin(6),
            frequency=12,
        )
        _fpga.start()
    return _fpga


def score(bin_name):
    fpga = _get_fpga()
    with open(bin_name, "rb") as f:
        fpga.cram(f)
    time.sleep_ms(100)

    matches = 0
    total = 0
    for _ in range(REPEATS):
        for n in range(256):
            av = n & 0xF
            bv = n >> 4
            a0.value(av & 1)
            a1.value((av >> 1) & 1)
            a2.value((av >> 2) & 1)
            a3.value((av >> 3) & 1)
            b0.value(bv & 1)
            b1.value((bv >> 1) & 1)
            b2.value((bv >> 2) & 1)
            b3.value((bv >> 3) & 1)
            time.sleep_ms(2)
            total_sum = av + bv
            exp = (
                (total_sum >> 4) & 1,
                (total_sum >> 3) & 1,
                (total_sum >> 2) & 1,
                (total_sum >> 1) & 1,
                total_sum & 1,
            )
            got = (cout.value(), s3.value(), s2.value(), s1.value(), s0.value())
            matches += int(exp == got)
            total += 1
    for pin in (a0, a1, a2, a3, b0, b1, b2, b3):
        pin.value(0)
    print("RESULT,{},{},{},{}".format(bin_name, matches, total, matches / total))
    return matches, total
