"""Score a 2-bit adder bitstream on the shared RP-ICE pins.

One pass over the 16 sums. Each of s0, s1, and cout counts on its own,
so the score is correct output bits / 48.
"""

from machine import Pin
import time
import ice

a0 = Pin(20, Pin.OUT)
a1 = Pin(24, Pin.OUT)
b0 = Pin(30, Pin.OUT)
b1 = Pin(25, Pin.OUT)
s0 = Pin(22, Pin.IN)
s1 = Pin(23, Pin.IN)
cout = Pin(27, Pin.IN)

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
    print("BEGIN,{}".format(bin_name))
    for _ in range(REPEATS):
        for av1 in (0, 1):
            for av0 in (0, 1):
                for bv1 in (0, 1):
                    for bv0 in (0, 1):
                        a1.value(av1)
                        a0.value(av0)
                        b1.value(bv1)
                        b0.value(bv0)
                        time.sleep_ms(5)
                        total_sum = (av1 << 1 | av0) + (bv1 << 1 | bv0)
                        exp = ((total_sum >> 2) & 1, (total_sum >> 1) & 1, total_sum & 1)
                        got = (cout.value(), s1.value(), s0.value())
                        matches += sum(left == right for left, right in zip(exp, got))
                        total += 3
    a0.value(0)
    a1.value(0)
    b0.value(0)
    b1.value(0)
    print("RESULT,{},{},{},{}".format(bin_name, matches, total, matches / total))
    return matches, total
