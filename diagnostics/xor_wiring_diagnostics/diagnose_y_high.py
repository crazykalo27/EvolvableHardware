from machine import Pin
import time
import ice

y = Pin(33, Pin.IN)
cdone = Pin(40, Pin.IN)

fpga = ice.fpga(
    cdone=cdone,
    clock=Pin(21),
    creset=Pin(31),
    cram_cs=Pin(5),
    cram_mosi=Pin(4),
    cram_sck=Pin(6),
    frequency=12
)
fpga.start()

with open("diag_y_high.bin", "rb") as f:
    fpga.cram(f)

time.sleep_ms(100)
print("Loaded diag_y_high.bin")
print("CDONE,", cdone.value())
print("DATA,sample,Y")

ones = 0
zeros = 0
samples = 20
for i in range(samples):
    measured = y.value()
    ones += measured
    zeros += (1 - measured)
    print("DATA,{},{}".format(i, measured))
    time.sleep_ms(50)

print("RESULT,ones={},zeros={},total={}".format(ones, zeros, samples))
if ones == samples:
    print("INTERPRETATION,output_path_ok")
elif zeros == samples:
    print("INTERPRETATION,no_high_seen_check_config_then_ICE4_to_GPIO33")
else:
    print("INTERPRETATION,unstable_output")
print("Y_HIGH_TEST_COMPLETE")
