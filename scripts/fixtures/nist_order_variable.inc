{ Test-only former variable-time Montgomery routine, used as a negative control. }
procedure OrderMontMul(const C: TOrder; var Z: TNat; const A, B: TNat);
var
  t: TNatWide;
  d: TNat;
  i, j, L, cc, hi, lo, m, k, bw: Integer;
begin
  L := C.L;
  for j := 0 to L + 1 do
    t[j] := 0;
  for i := 0 to L - 1 do
  begin
    { t += A[i] * B }
    cc := 0;
    for j := 0 to L - 1 do
    begin
      Mul128(A[i], B[j], hi, lo);
      lo := AddCarry(lo, t[j], 0, k);
      hi := hi + k;
      lo := AddCarry(lo, cc, 0, k);
      hi := hi + k;
      t[j] := lo;
      cc := hi;
    end;
    t[L] := AddCarry(t[L], cc, 0, k);
    t[L + 1] := k;
    { t = (t + m n) / 2^64, m making the low word zero }
    m := t[0] * C.N0;
    Mul128(m, C.N[0], hi, lo);
    lo := AddCarry(lo, t[0], 0, k);
    cc := hi + k;
    for j := 1 to L - 1 do
    begin
      Mul128(m, C.N[j], hi, lo);
      lo := AddCarry(lo, t[j], 0, k);
      hi := hi + k;
      lo := AddCarry(lo, cc, 0, k);
      hi := hi + k;
      t[j - 1] := lo;
      cc := hi;
    end;
    t[L - 1] := AddCarry(t[L], cc, 0, k);
    t[L] := t[L + 1] + k;
  end;
  bw := 0;
  for j := 0 to L - 1 do
    d[j] := SubBorrow(t[j], C.N[j], bw, bw);
  for j := 0 to 5 do
    Z[j] := 0;
  if (t[L] <> 0) or (bw = 0) then
    for j := 0 to L - 1 do
      Z[j] := d[j]
  else
    for j := 0 to L - 1 do
      Z[j] := t[j];
end;
