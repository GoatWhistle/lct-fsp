import { execFileSync } from "node:child_process"
import fs from "node:fs"
import path from "node:path"

const ROOT = path.resolve(import.meta.dirname, "..")
const FRONTEND = path.resolve(ROOT, "..", "frontend")
const TARGET = path.join(ROOT, "src", "core", "css")

execFileSync(process.execPath, [path.join(FRONTEND, "scripts", "exportTokens.ts"), TARGET], { stdio: "inherit" })
fs.rmSync(path.join(TARGET, "tokens.json"), { force: true })
