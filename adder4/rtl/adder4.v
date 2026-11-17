// 4-bit adder: {cout, s3, s2, s1, s0} = {a3, a2, a1, a0} + {b3, b2, b1, b0}
module top (
    input  wire a0,
    input  wire a1,
    input  wire a2,
    input  wire a3,
    input  wire b0,
    input  wire b1,
    input  wire b2,
    input  wire b3,
    output wire s0,
    output wire s1,
    output wire s2,
    output wire s3,
    output wire cout
);
    wire [4:0] sum = {1'b0, a3, a2, a1, a0} + {1'b0, b3, b2, b1, b0};
    assign s0 = sum[0];
    assign s1 = sum[1];
    assign s2 = sum[2];
    assign s3 = sum[3];
    assign cout = sum[4];
endmodule
