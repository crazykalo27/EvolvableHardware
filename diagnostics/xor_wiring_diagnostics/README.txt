Pico2-ice XOR wiring diagnostics
================================

Purpose
-------
Builds three FPGA configurations using the SAME package pin assignments as the
current XOR design, then tests whether each input can propagate to the measured
output:
  diag_a.bin : FPGA output Y follows input A
  diag_b.bin : FPGA output Y follows input B
  xor.bin    : normal XOR behavior

Important limitation
--------------------
These tests can help distinguish the A path from the B path, but they cannot
prove the output wire is good if BOTH tests fail. Both tests share the output
path, and a wrong PCF/package-pin-to-board-header mapping can mimic bad wiring.
The PCF currently uses package pins 2, 3, and 4, matching the current setup;
that mapping still needs verification against the official pico2-ice pinout.

Current assumed RP2350 GPIOs:
  GPIO2  drives FPGA input A
  GPIO3  drives FPGA input B
  GPIO33 reads FPGA output Y

Safety:
- Keep signals at 3.3 V logic.
- Unplug USB before changing any physical wires.
- Do not connect RP2350 GPIOs to 5 V.

Build on the Mac
----------------
From your PicoIceProj directory, with yosys, nextpnr-ice40, and icepack installed:

1. Unzip this folder into PicoIceProj (or copy its files there).
2. Run:
       bash build_diagnostics.sh
3. Upload the generated bitstreams and the board test:
       mpremote connect /dev/cu.usbmodem1101 fs cp diag_a.bin :diag_a.bin
       mpremote connect /dev/cu.usbmodem1101 fs cp diag_b.bin :diag_b.bin
       mpremote connect /dev/cu.usbmodem1101 fs cp xor.bin :xor.bin
       mpremote connect /dev/cu.usbmodem1101 fs cp diagnose_wiring.py :diagnose_wiring.py
4. Run the board-side test from the Mac:
       mpremote connect /dev/cu.usbmodem1101 exec "import diagnose_wiring"

The script prints results for A-follow, B-follow, and XOR modes. It finishes
by leaving the normal XOR bitstream loaded.

Reading the results
-------------------
- A-follow passes, B-follow passes, XOR passes:
    Both input paths and the output path behave as expected under this mapping.
- A-follow passes, B-follow fails:
    Investigate the B path first (RP3 -> ICE3, or the B FPGA pin mapping).
- A-follow fails, B-follow passes:
    Investigate the A path first (RP2 -> ICE2, or the A FPGA pin mapping).
- Both follow tests fail:
    Cannot identify a single bad wire from this result. Check ICE4 -> RP33,
    FPGA output pin mapping, FPGA configuration success, and shared ground/
    header assumptions. Confirm the PCF mappings before rewiring.
- Follow tests pass but XOR fails:
    Suspect the XOR bitstream/build/configuration rather than either input path.

The script reports sample counts and mismatches. A passing result requires all
samples in that mode to match.
