
Thesis: Exploring evolutionary reconfiguration success for restoring FPGA circuit functionality on real hardware after injected configuration faults. 

Thesis: Exploring evolutionary reconfiguration success for restoring FPGA circuit functionality on real hardware after injected configuration faults.
Body: Pico2-ICE — RP2350B + iCE40UP5K FPGA. Product page. Found through the Evolvable Hardware project.
Brain: A simple digital or analog circuit implemented on the FPGA, with a defined function and test inputs/outputs. Injected configuration faults will cause incorrect behavior, requiring evolution to find a configuration that restores the original functionality.
Evolutionary Algorithm: Use an evolutionary algorithm to mutate FPGA configuration bits and evaluate each candidate on the physical hardware. Fitness will be based on how closely the circuit's outputs match the original expected outputs across a set of test cases.
Milestones:
Week 1: Set up the Pico2-ICE and run an existing bitstream evolution example.
Week 2: Implement a simple digital circuit and automate hardware testing and fitness evaluation.
Week 3: Inject configuration faults and test whether evolution can restore circuit functionality across multiple trials.
Week 4: Analyze recovery success, number of evaluations required, and the effect of fault severity. Compare results against a baseline.


Your fault-recovery framing is a good choice because it mirrors damage recovery in robots: the configured circuit plays the role of the body, the injected faults are the "damage," and evolution has to find a new configuration that restores the behavior. Doing it intrinsically on real silicon is ambitious and exciting.

My feedback is mostly about fitting it into two weeks and making sure the result answers a question. Compress the timeline. Your milestones span 4 weeks, but you have about 2. Roughly:

 Days 1–3: Get the Pico2-ICE toolchain working and run an existing iCE40 bitstream-evolution example end to end. This is your biggest risk, so tackle it first. 
Days 4–6: Implement your target circuit, automate the upload → test → score loop, and time one evaluation. That number sets your whole budget (population × generations × trials).
 Days 7–11: Fault injection and recovery experiments. 
Days 12–14: Analysis and writeup. 

Keep the circuit small. Use something like a 2-bit adder or 4-bit parity that fits in a handful of LUTs. Fitness is the fraction of truth-table rows correct, which gives a smooth gradient. You can always scale up later. Sharpen the question and name the baseline. "Compare against a baseline" needs to be concrete. A strong version: "How does fault severity (1, 2, 4, 8 flipped configuration bits) affect recovery success and the number of evaluations needed, and does evolving from the damaged configuration recover faster than evolving from a random one?" The random-start condition, plus perhaps a random-search control at the same evaluation budget, is the baseline that shows evolution is doing real work. Run multiple trials for each severity level: recovery rate and evaluations-to-recovery need a distribution, not a single run. Restrict what you mutate. Limit mutation and fault injection to LUT contents (well documented via Project IceStorm), and keep routing fixed. This keeps the search space manageable and avoids writing configurations that could create internal contention on the chip. Have a simulation fallback. If the hardware loop isn't working by about day 5, simulate the same fixed-routing LUT grid in Python and run the identical experiment extrinsically. You'll still answer the question, and a sim-vs-hardware comparison could become your stretch goal (your "reality gap" idea). Your "Other Ideas" list is great material for the future-work section of your report.

