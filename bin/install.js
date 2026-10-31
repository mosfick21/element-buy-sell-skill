#!/usr/bin/env node
// Copies this skill into an agent skills folder and installs the Python deps.
// Usage: npx github:mosfick21/element-buy-sell-skill [target-dir]
const fs = require("fs"), path = require("path"), os = require("os"), { spawnSync } = require("child_process");

const home = os.homedir();
const guess = [
  [path.join(home, ".hermes", "skills"), "element-market"],
  [path.join(home, ".claude", "skills"), "element-market"],
].find(([d]) => fs.existsSync(d));
const target = process.argv[2]
  ? path.resolve(process.argv[2])
  : guess ? path.join(...guess) : path.resolve("element-market");

const src = path.resolve(__dirname, "..");
for (const f of ["SKILL.md", "scripts", "README.md"]) {
  fs.cpSync(path.join(src, f), path.join(target, f), { recursive: true });
}
console.log("skill installed ->", target);

const pip = spawnSync("python3", ["-m", "pip", "install", "-q", "eth-account", "eth-abi", "eth-utils"], { stdio: "inherit" });
if (pip.status !== 0) console.log("pip failed, run: pip install eth-account eth-abi eth-utils");

const cfg = path.join(home, ".config", "element-market", "wallets.json");
if (!fs.existsSync(cfg)) {
  fs.mkdirSync(path.dirname(cfg), { recursive: true });
  fs.writeFileSync(cfg, JSON.stringify({ main: "0x0000000000000000000000000000000000000000" }, null, 1) + "\n");
  console.log("edit your wallet address ->", cfg);
}
