from machine import Pin
import time
import ice

a = Pin(2, Pin.OUT)
b = Pin(3, Pin.OUT)
y = Pin(33, Pin.IN)

_fpga = None


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


patterns = [(0, 0), (0, 1), (1, 0), (1, 1)]
repeats = 5


def score(bin_name):
    fpga = _get_fpga()
    with open(bin_name, "rb") as f:
        fpga.cram(f)
    time.sleep_ms(100)

    matches = 0
    total = 0
    print("BEGIN,{}".format(bin_name))
    print("DATA,A,B,expected,measured,match")
    for _ in range(repeats):
        for av, bv in patterns:
            a.value(av)
            b.value(bv)
            time.sleep_ms(20)
            expected = av ^ bv
            measured = y.value()
            match = int(expected == measured)
            matches += match
            total += 1
            print("DATA,{},{},{},{},{}".format(av, bv, expected, measured, match))
            time.sleep_ms(10)

    a.value(0)
    b.value(0)
    print("RESULT,{},{},{},{}".format(bin_name, matches, total, matches / total))
    return matches, total
