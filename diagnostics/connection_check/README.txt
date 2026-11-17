Shared RP-ICE connection check
==============================

Checks the on-board RP2350 ↔ iCE40 pairs used for future adder/parity work.
No breadboard jumpers are required for this bank.

  IN0  ICE_27 <-> GPIO20
  IN1  ICE_26 <-> GPIO24
  IN2  ICE_25 <-> GPIO30
  IN3  ICE_23 <-> GPIO25
  OUT0 ICE_20 <-> GPIO22
  OUT1 ICE_19 <-> GPIO23
  OUT2 ICE_18 <-> GPIO27
  OUT3 ICE_21 <-> GPIO26

Build (from this directory):

  ./build.sh

Upload and run:

  mpremote connect /dev/cu.usbmodem1101 fs cp wirecheck_high.bin :wirecheck_high.bin
  mpremote connect /dev/cu.usbmodem1101 fs cp wirecheck_follow.bin :wirecheck_follow.bin
  mpremote connect /dev/cu.usbmodem1101 fs cp check_connections.py :check_connections.py
  mpremote connect /dev/cu.usbmodem1101 exec "import check_connections; check_connections.run()"

Tests:
  1. OUTPUT_HIGH — FPGA forces all OUTs to 1
  2. FOLLOW      — each OUT follows its matching IN
  3. ONE_HOT     — only the driven channel should go high

OVERALL,PASS means the shared bank is ready for the 2-bit adder.
