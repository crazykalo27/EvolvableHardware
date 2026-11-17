// Drive every shared-bank output HIGH.
// RP reads the matching GPIOs to verify FPGA → RP output paths.
module top (
    output wire out0,
    output wire out1,
    output wire out2,
    output wire out3
);
    assign out0 = 1'b1;
    assign out1 = 1'b1;
    assign out2 = 1'b1;
    assign out3 = 1'b1;
endmodule
