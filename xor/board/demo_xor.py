from machine import Pin
import time

# RP2350 GPIOs connected to FPGA inputs A and B
a = Pin(2, Pin.OUT)
b = Pin(3, Pin.OUT)

# RP2350 GPIO connected to FPGA output Y
y = Pin(33, Pin.IN)

print("DATA,ms,A,B,expected,Y,match")

start = time.ticks_ms()
patterns = [(0, 0), (0, 1), (1, 0), (1, 1)]

# Run 20 cycles, then stop automatically
for cycle in range(20):
    for av, bv in patterns:
        a.value(av)
        b.value(bv)

        # Allow the signals to settle
        time.sleep_ms(20)

        expected = av ^ bv
        measured = y.value()
        elapsed = time.ticks_diff(time.ticks_ms(), start)

        print("DATA,{},{},{},{},{},{}".format(
            elapsed, av, bv, expected, measured,
            int(expected == measured)
        ))

        time.sleep_ms(180)

a.value(0)
b.value(0)
print("TEST_COMPLETE")
