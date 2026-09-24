// Line diff (longest-common-subsequence). Returns rows: {type: "same"|"add"|"del", text, oldNo?, newNo?}
export function diffLines(oldText = "", newText = "") {
  const a = oldText.split("\n");
  const b = newText.split("\n");
  const n = a.length, m = b.length;
  if (n * m > 4_000_000) return b.map((t, i) => ({ type: "add", text: t, newNo: i + 1 })); // safety valve for huge inputs

  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);

  const rows = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { rows.push({ type: "same", text: a[i], oldNo: i + 1, newNo: j + 1 }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { rows.push({ type: "del", text: a[i], oldNo: i + 1 }); i++; }
    else { rows.push({ type: "add", text: b[j], newNo: j + 1 }); j++; }
  }
  while (i < n) { rows.push({ type: "del", text: a[i], oldNo: i + 1 }); i++; }
  while (j < m) { rows.push({ type: "add", text: b[j], newNo: j + 1 }); j++; }
  return rows;
}
