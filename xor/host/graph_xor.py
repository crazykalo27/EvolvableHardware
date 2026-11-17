import subprocess
import matplotlib.pyplot as plt
from pathlib import Path

# Project root is two levels up from xor/host/
ROOT = Path(__file__).resolve().parents[2]
MPREMOTE = ROOT / ".venv" / "bin" / "mpremote"

cmd = [
    str(MPREMOTE), "connect", "/dev/cu.usbmodem1101",
    "exec", "import demo_xor"
]

times = []
signals = {"A": [], "B": [], "Expected Y": [], "Measured Y": []}

plt.ion()
fig, ax = plt.subplots(figsize=(10, 5))
lines = {
    name: ax.step([], [], where="post", label=name)[0]
    for name in signals
}
ax.set_title("Live FPGA XOR Test")
ax.set_xlabel("Time (ms)")
ax.set_ylabel("Logic level")
ax.set_ylim(-0.2, 1.2)
ax.grid(True)
ax.legend()

try:
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )

    for raw in process.stdout:
        line = raw.strip()

        if line == "TEST_COMPLETE":
            break

        if not line.startswith("DATA,"):
            print(line)
            continue

        try:
            _, ms, a, b, expected, measured, match = line.split(",")
            ms, a, b, expected, measured, match = map(
                int, (ms, a, b, expected, measured, match)
            )
        except ValueError:
            continue

        times.append(ms)
        for name, value in zip(
            signals, [a, b, expected, measured]
        ):
            signals[name].append(value)
            lines[name].set_data(times, signals[name])

        ax.set_xlim(0, max(100, ms))
        fig.canvas.draw_idle()
        fig.canvas.flush_events()
        plt.pause(0.01)

    process.wait()

finally:
    plt.ioff()
    if times:
        matches = sum(
            e == m for e, m in zip(
                signals["Expected Y"], signals["Measured Y"]
            )
        )
        print(f"\nSamples: {len(times)}")
        print(f"Matches: {matches}")
        print(f"Mismatches: {len(times) - matches}")
    plt.show()
