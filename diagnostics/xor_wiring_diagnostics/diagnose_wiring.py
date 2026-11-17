
from machine import Pin
import time
import ice

a = Pin(2, Pin.OUT)
b = Pin(3, Pin.OUT)
y = Pin(33, Pin.IN)

fpga = ice.fpga(
    cdone=Pin(40),
    clock=Pin(21),
    creset=Pin(31),
    cram_cs=Pin(5),
    cram_mosi=Pin(4),
    cram_sck=Pin(6),
    frequency=12
)
fpga.start()

def load_bitstream(filename):
    with open(filename, "rb") as f:
        fpga.cram(f)
    time.sleep_ms(100)
    print("Loaded", filename)

def run_test(label, filename, patterns):
    load_bitstream(filename)
    total = 0
    matches = 0
    print("BEGIN,", label)
    print("DATA,mode,A,B,expected,measured,match")
    for av, bv in patterns:
        a.value(av)
        b.value(bv)
        time.sleep_ms(20)
        expected = av if label == "A_FOLLOW" else (bv if label == "B_FOLLOW" else (av ^ bv))
        measured = y.value()
        match = int(expected == measured)
        total += 1
        matches += match
        print("DATA,{},{},{},{},{},{}".format(
            label, av, bv, expected, measured, match
        ))
        time.sleep_ms(30)
    print("RESULT,{},{},{},{}".format(label, matches, total, total - matches))
    return matches, total

patterns = [(0, 0), (0, 1), (1, 0), (1, 1)] * 5

print("Starting FPGA wiring diagnostics.")
print("Assumes RP GPIO2->FPGA A, GPIO3->FPGA B, FPGA Y->RP GPIO33.")
results = []
try:
    results.append(run_test("A_FOLLOW", "diag_a.bin", patterns))
    results.append(run_test("B_FOLLOW", "diag_b.bin", patterns))
    results.append(run_test("XOR", "xor.bin", patterns))
finally:
    a.value(0)
    b.value(0)

print("SUMMARY")
for label, result in zip(("A_FOLLOW", "B_FOLLOW", "XOR"), results):
    good, total = result
    print("{},{}/{},mismatches={}".format(label, good, total, total - good))
print("DIAGNOSTICS_COMPLETE")
