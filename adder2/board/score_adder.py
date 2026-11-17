"""Score the 2-bit adder on the shared RP-ICE pins."""

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

fpga = ice.fpga(
    cdone=Pin(40),
    clock=Pin(21),
    creset=Pin(31),
    cram_cs=Pin(5),
    cram_mosi=Pin(4),
    cram_sck=Pin(6),
    frequency=12,
)
fpga.start()
with open("adder2.bin", "rb") as f:
    fpga.cram(f)
time.sleep_ms(100)
print("CDONE,{}".format(Pin(40, Pin.IN).value()))

matches = 0
total = 0
print("DATA,a1,a0,b1,b0,exp_cout,exp_s1,exp_s0,got_cout,got_s1,got_s0,match")
for av1 in (0, 1):
    for av0 in (0, 1):
        for bv1 in (0, 1):
            for bv0 in (0, 1):
                a1.value(av1)
                a0.value(av0)
                b1.value(bv1)
                b0.value(bv0)
                time.sleep_ms(20)
                total_sum = (av1 << 1 | av0) + (bv1 << 1 | bv0)
                exp = ((total_sum >> 2) & 1, (total_sum >> 1) & 1, total_sum & 1)
                got = (cout.value(), s1.value(), s0.value())
                ok = int(exp == got)
                matches += ok
                total += 1
                print(
                    "DATA,{},{},{},{},{},{},{},{},{},{},{}".format(
                        av1, av0, bv1, bv0, exp[0], exp[1], exp[2], got[0], got[1], got[2], ok
                    )
                )

a0.value(0)
a1.value(0)
b0.value(0)
b1.value(0)
print("RESULT,adder2,{},{},{}".format(matches, total, matches / total))
