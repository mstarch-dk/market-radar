// Compile every formula in the guide's chapters with KaTeX, the way the Guide page renders them, and list the ones
// that fail. Run: uv run python -c "…" | node web/scripts/check-math.mjs  (reads JSON {name: markdown} on stdin).
import katex from "katex";

const input = await new Promise((resolve) => {
  let s = "";
  process.stdin.on("data", (d) => (s += d));
  process.stdin.on("end", () => resolve(s));
});
const chapters = JSON.parse(input);
let bad = 0, total = 0;
for (const [name, md] of Object.entries(chapters)) {
  const text = md.replace(/```[\s\S]*?```/g, "").replace(/`[^`\n]*`/g, "");
  const blocks = [...text.matchAll(/\$\$([\s\S]+?)\$\$/g)].map((m) => [m[1], true]);
  const inline = [...text.replace(/\$\$[\s\S]+?\$\$/g, "").matchAll(/\$([^$\n]+?)\$/g)].map((m) => [m[1], false]);
  for (const [tex, display] of [...blocks, ...inline]) {
    total++;
    try {
      katex.renderToString(tex, { displayMode: display, throwOnError: true, strict: "ignore" });
    } catch (e) {
      bad++;
      console.log(`${name}: ${String(e.message).split("\n")[0]}\n    ${tex.trim().slice(0, 140)}`);
    }
  }
}
console.log(`${total} formulas, ${bad} failed`);
process.exit(bad ? 1 : 0);
