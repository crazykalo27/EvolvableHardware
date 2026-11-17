// 2-bit adder: {cout, s1, s0} = {a1, a0} + {b1, b0}
module top (
    input  wire a0,
    input  wire a1,
    input  wire b0,
    input  wire b1,
    output wire s0,
    output wire s1,
    output wire cout
);
    wire [2:0] sum = {1'b0, a1, a0} + {1'b0, b1, b0};
    assign s0 = sum[0];
    assign s1 = sum[1];
    assign cout = sum[2];
endmodule
