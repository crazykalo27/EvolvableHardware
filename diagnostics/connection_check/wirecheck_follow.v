// Route each shared-bank input to the matching output.
// RP drives IN GPIOs and reads OUT GPIOs to verify full RP ↔ FPGA paths.
module top (
    input  wire in0,
    input  wire in1,
    input  wire in2,
    input  wire in3,
    output wire out0,
    output wire out1,
    output wire out2,
    output wire out3
);
    assign out0 = in0;
    assign out1 = in1;
    assign out2 = in2;
    assign out3 = in3;
endmodule
