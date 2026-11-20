#!/usr/bin/env bash
# Fetch the LDD posit decoder (Github JSCooode/LDD_Posit_Decoder, pinned commit) and
# configure one comparison design into build/ext/<design>/ with a wrapper named <design>.
#   ldd_32_2: the parameterised LDD_64_4 sources set to n = 32, es = 2, rs = 6, with and32
#             in LDD.v (the procedure in the upstream README)
#   ldd_32_3: the upstream LDD_32_3 sources, unchanged
#   lod_32_2: the upstream LOD_32_3 sources with the exponent and fraction widths set to es = 2
#   percival_32_2: Verilog transcription of the PERCIVAL decoder (src/ext/percival_32_2.v)
# Usage: cmp_prepare.sh <design>
set -euo pipefail
D=$1
if [ "$D" = "percival_32_2" ]; then        # Verilog transcription kept in src/ext
  rm -rf "build/ext/$D"; mkdir -p "build/ext/$D"
  cp src/ext/percival_32_2.v "build/ext/$D/"
  echo "$D: transcription of PERCIVAL PositFastDecoder_32_2"; exit 0
fi
REPO=https://github.com/JSCooode/LDD_Posit_Decoder.git
PIN=6bef4f3c2563ee7f7d6b3829a51c5db6bbb0bea2
EXT=build/ext/LDD_Posit_Decoder
if [ ! -d "$EXT/.git" ]; then
  git clone -q "$REPO" "$EXT"
  git -C "$EXT" checkout -q "$PIN"
fi
OUT=build/ext/$D
rm -rf "$OUT"
mkdir -p "$OUT"
case "$D" in
  ldd_32_2)
    for f in decoder twoscom LDD LDDShifter and4 and8 and16 and32; do cp "$EXT/LDD_64_4/$f.v" "$OUT/"; done
    sed -i -E 's/parameter n = 64;/parameter n = 32;/; s/parameter es = 4;/parameter es = 2;/; s/parameter rs = 7;/parameter rs = 6;/' "$OUT"/*.v
    sed -i 's/and64 a0/and32 a0/' "$OUT/LDD.v"
    ES=2 ;;
  ldd_32_3)
    cp "$EXT"/LDD_32_3/*.v "$OUT/"
    ES=3 ;;
  lod_32_2)
    # LOD_32_3 with its es-dependent parts set to es = 2: port widths in decoder.v and
    # the exponent/fraction selection in shift.v (same structure as the upstream file).
    cp "$EXT"/LOD_32_3/*.v "$OUT/"
    sed -i 's/output \[2:0\] expo;/output [1:0] expo;/; s/output \[25:0\] frac;/output [26:0] frac;/' "$OUT/decoder.v"
    cat > "$OUT/shift.v" <<'SV'
module shift(expo, frac, xin, k);
input [30:0] xin;
input [4:0] k;

output reg [1:0] expo;
output [26:0] frac;

wire [30:0] sh0;

left_shifter s0(sh0, xin, k);

always @(xin, sh0, k) begin
if (k < 29)
	expo = sh0[30:29];
else if (k == 29) begin
	expo[1] = 0;
	expo[0] = sh0[30];
	end
else
	expo = 0;
end

assign frac = sh0[28:2];

endmodule
SV
    ES=2 ;;
  *) echo "unknown design $D" >&2; exit 1 ;;
esac
FS=$((32 - ES - 3))
cat > "$OUT/$D.v" <<V
// Wrapper with a unique top name; it adds no logic.
module $D (
    input  wire [31:0]     in,
    output wire            sign,
    output wire [5:0]      regi,
    output wire [$((ES-1)):0] expo,
    output wire [$((FS-1)):0] frac,
    output wire            allone,
    output wire            allzero
);
    decoder u_dec (.sign(sign), .regi(regi), .expo(expo), .frac(frac), .allone(allone), .allzero(allzero), .in(in));
endmodule
V
case "$D" in
  lod_*) diff -ru "$EXT/LOD_32_3" "$OUT" > "$OUT.changes.diff" 2>/dev/null || true ;;
  *) diff -ru "$EXT/LDD_64_4" "$OUT" > "$OUT.changes.diff" 2>/dev/null || true ;;
esac
echo "$D: es=$ES fs=$FS from $PIN"; ls "$OUT"
