"""
pico2-ice connection checker for the shared RP-ICE pin bank.

Uses on-board hardwired pairs only (no breadboard jumpers required):

  IN0  ICE_27 <-> GPIO20
  IN1  ICE_26 <-> GPIO24
  IN2  ICE_25 <-> GPIO30
  IN3  ICE_23 <-> GPIO25
  OUT0 ICE_20 <-> GPIO22
  OUT1 ICE_19 <-> GPIO23
  OUT2 ICE_18 <-> GPIO27
  OUT3 ICE_21 <-> GPIO26

Upload first:
  wirecheck_high.bin
  wirecheck_follow.bin
  check_connections.py

Then:
  import check_connections
  check_connections.run()
"""

from machine import Pin
import time
import ice

# Shared RP-ICE bank. Names match wirecheck.pcf.
IN_PINS = [
    ("IN0", 20, "ICE_27"),
    ("IN1", 24, "ICE_26"),
    ("IN2", 30, "ICE_25"),
    ("IN3", 25, "ICE_23"),
]
OUT_PINS = [
    ("OUT0", 22, "ICE_20"),
    ("OUT1", 23, "ICE_19"),
    ("OUT2", 27, "ICE_18"),
    ("OUT3", 26, "ICE_21"),
]

CDONE_GPIO = 40
SETTLE_MS = 20
REPEATS = 3

_fpga = None
_ins = None
_outs = None
_cdone = None


def _setup_pins():
    global _ins, _outs, _cdone
    _ins = [(name, Pin(gpio, Pin.OUT), ice_name) for name, gpio, ice_name in IN_PINS]
    _outs = [(name, Pin(gpio, Pin.IN), ice_name) for name, gpio, ice_name in OUT_PINS]
    _cdone = Pin(CDONE_GPIO, Pin.IN)
    for _name, pin, _ice in _ins:
        pin.value(0)


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


def _load(bin_name):
    fpga = _get_fpga()
    with open(bin_name, "rb") as f:
        fpga.cram(f)
    time.sleep_ms(100)
    return _cdone.value()


def _read_outs():
    return [pin.value() for _name, pin, _ice in _outs]


def _set_ins(values):
    for (_name, pin, _ice), value in zip(_ins, values):
        pin.value(value)
    time.sleep_ms(SETTLE_MS)


def test_outputs_high():
    """FPGA drives all OUTs high. Checks FPGA → RP on each OUT pin."""
    print("TEST,OUTPUT_HIGH")
    cdone = _load("wirecheck_high.bin")
    print("CDONE,{}".format(cdone))
    if cdone != 1:
        print("FAIL,OUTPUT_HIGH,CDONE_not_set")
        return 0, 4

    passes = 0
    for _ in range(REPEATS):
        measured = _read_outs()
        for (name, _pin, ice_name), bit in zip(_outs, measured):
            ok = bit == 1
            passes += int(ok)
            print(
                "DATA,OUTPUT_HIGH,{},{},expected=1,measured={},{}".format(
                    name, ice_name, bit, "PASS" if ok else "FAIL"
                )
            )
        time.sleep_ms(10)

    # Each OUT is checked REPEATS times.
    total = len(_outs) * REPEATS
    print("RESULT,OUTPUT_HIGH,{},{},{}".format(passes, total, passes / total))
    return passes, total


def test_follow():
    """Each OUT should equal its matching IN. Checks full RP → FPGA → RP paths."""
    print("TEST,FOLLOW")
    cdone = _load("wirecheck_follow.bin")
    print("CDONE,{}".format(cdone))
    if cdone != 1:
        print("FAIL,FOLLOW,CDONE_not_set")
        return 0, len(_outs) * 2 * REPEATS

    passes = 0
    total = 0
    patterns = [
        [0, 0, 0, 0],
        [1, 1, 1, 1],
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
        [1, 0, 1, 0],
        [0, 1, 0, 1],
    ]

    for _ in range(REPEATS):
        for values in patterns:
            _set_ins(values)
            measured = _read_outs()
            for i, ((out_name, _opin, out_ice), (in_name, _ipin, in_ice)) in enumerate(
                zip(_outs, _ins)
            ):
                expected = values[i]
                bit = measured[i]
                ok = bit == expected
                passes += int(ok)
                total += 1
                print(
                    "DATA,FOLLOW,{}->{},drive={},expected={},measured={},{}".format(
                        in_name,
                        out_name,
                        expected,
                        expected,
                        bit,
                        "PASS" if ok else "FAIL",
                    )
                )
    _set_ins([0, 0, 0, 0])
    print("RESULT,FOLLOW,{},{},{}".format(passes, total, passes / total))
    return passes, total


def test_one_hot_isolation():
    """Drive one IN high at a time; only the matching OUT should go high."""
    print("TEST,ONE_HOT")
    cdone = _load("wirecheck_follow.bin")
    print("CDONE,{}".format(cdone))
    if cdone != 1:
        print("FAIL,ONE_HOT,CDONE_not_set")
        return 0, len(_outs) * len(_ins) * REPEATS

    passes = 0
    total = 0
    for _ in range(REPEATS):
        for hot in range(len(_ins)):
            values = [1 if i == hot else 0 for i in range(len(_ins))]
            _set_ins(values)
            measured = _read_outs()
            for i, (out_name, _opin, out_ice) in enumerate(_outs):
                expected = 1 if i == hot else 0
                bit = measured[i]
                ok = bit == expected
                passes += int(ok)
                total += 1
                print(
                    "DATA,ONE_HOT,hot=IN{},{},expected={},measured={},{}".format(
                        hot, out_name, expected, bit, "PASS" if ok else "FAIL"
                    )
                )
    _set_ins([0, 0, 0, 0])
    print("RESULT,ONE_HOT,{},{},{}".format(passes, total, passes / total))
    return passes, total


def run():
    _setup_pins()
    print("BEGIN,connection_check")
    print("BANK,shared_RP_ICE")
    for name, gpio, ice_name in IN_PINS:
        print("PIN,IN,{},GPIO{},{}".format(name, gpio, ice_name))
    for name, gpio, ice_name in OUT_PINS:
        print("PIN,OUT,{},GPIO{},{}".format(name, gpio, ice_name))

    results = []
    results.append(("OUTPUT_HIGH",) + test_outputs_high())
    results.append(("FOLLOW",) + test_follow())
    results.append(("ONE_HOT",) + test_one_hot_isolation())

    all_pass = True
    print("SUMMARY")
    for name, passes, total in results:
        ok = passes == total and total > 0
        all_pass = all_pass and ok
        print(
            "SUMMARY,{},{},{},{}".format(
                name, passes, total, "PASS" if ok else "FAIL"
            )
        )
    print("OVERALL,{}".format("PASS" if all_pass else "FAIL"))
    return all_pass


if __name__ == "__main__":
    run()
