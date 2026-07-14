#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { Codex } from "@openai/codex-sdk";

async function main() {
  const raw = readFileSync(0, "utf8").trim();
  if (!raw) throw new Error("missing Codex runner request");
  const input = JSON.parse(raw);
  const apiKey = process.env.CATALYST_CODEX_API_KEY || process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("OPENAI_API_KEY or CATALYST_CODEX_API_KEY is required for Codex");
  if (!input.projectPath || !input.prompt) throw new Error("projectPath and prompt are required");

  const options = {
    model: input.model || process.env.CATALYST_CODEX_MODEL || "gpt-5.4-mini",
    modelReasoningEffort: input.reasoningEffort || "medium",
    workingDirectory: input.projectPath,
    skipGitRepoCheck: true,
    // Catalyst tools own writes and UI actions. Chat-mode Codex cannot mutate files itself.
    sandboxMode: "read-only",
    networkAccessEnabled: false,
    webSearchMode: "disabled",
    approvalPolicy: "never",
  };
  const codex = new Codex({ apiKey, env: { ...process.env, CODEX_API_KEY: apiKey } });
  const thread = input.threadId ? codex.resumeThread(input.threadId, options) : codex.startThread(options);
  const result = await thread.run(input.prompt);
  if (!result?.finalResponse) throw new Error("Codex returned no final response");
  process.stdout.write(JSON.stringify({ threadId: thread.id, finalResponse: result.finalResponse, usage: result.usage || {} }));
}

main().catch((error) => {
  process.stderr.write(`${error?.stack || String(error)}\n`);
  process.exitCode = 1;
});
