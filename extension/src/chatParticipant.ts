/**
 * VST Gen — Chat Participant
 *
 * Registers the @vst-gen chat participant. The system prompt and skill
 * content are bundled inside the extension under assets/ — no vst-gen-agent
 * repo needs to be present in the workspace.
 *
 * Slash commands:
 *   /new-device  — full guided capture → scaffold workflow
 *   /login       — GitHub device flow registration
 */

import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import { getToolsRunner } from "./tools";

// ---------------------------------------------------------------------------
// Asset loading — reads bundled markdown files from extension/assets/
// ---------------------------------------------------------------------------

function readAsset(extensionPath: string, ...segments: string[]): string {
  const fullPath = path.join(extensionPath, "assets", ...segments);
  try {
    return fs.readFileSync(fullPath, "utf-8");
  } catch {
    return "";
  }
}

/** Strip YAML frontmatter (--- ... ---\n) from a .md file */
function stripFrontmatter(content: string): string {
  return content.replace(/^---[\s\S]*?---\n?/, "").trim();
}

function loadSystemPrompt(extensionPath: string): string {
  const raw = readAsset(extensionPath, "system-prompt.md");
  return raw ? stripFrontmatter(raw) : "You are an expert VST plugin developer. Help the user build MIDI controller plugins for their hardware synthesizers.";
}

function loadSkill(extensionPath: string, skillName: string): string {
  const raw = readAsset(extensionPath, "skills", `${skillName}.md`);
  return raw ? stripFrontmatter(raw) : "";
}

// ---------------------------------------------------------------------------
// Context helpers
// ---------------------------------------------------------------------------

function getWorkspaceRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function getConfig(): vscode.WorkspaceConfiguration {
  return vscode.workspace.getConfiguration("vstGen");
}

/** Detect which slash command was used, if any */
function detectCommand(request: vscode.ChatRequest): string | undefined {
  return request.command;
}

/** Build prior conversation history for multi-turn context */
function buildHistory(
  history: readonly (vscode.ChatRequestTurn | vscode.ChatResponseTurn)[]
): vscode.LanguageModelChatMessage[] {
  const messages: vscode.LanguageModelChatMessage[] = [];
  for (const turn of history) {
    if (turn instanceof vscode.ChatRequestTurn) {
      messages.push(vscode.LanguageModelChatMessage.User(turn.prompt));
    } else if (turn instanceof vscode.ChatResponseTurn) {
      const text = turn.response
        .filter((p): p is vscode.ChatResponseMarkdownPart =>
          p instanceof vscode.ChatResponseMarkdownPart
        )
        .map((p) => p.value.value)
        .join("");
      if (text) {
        messages.push(vscode.LanguageModelChatMessage.Assistant(text));
      }
    }
  }
  return messages;
}

// ---------------------------------------------------------------------------
// Skill injection based on command / intent keywords
// ---------------------------------------------------------------------------

const SKILL_KEYWORDS: Record<string, string[]> = {
  "midi-capture": ["capture", "nrpn", "midi", "knob", "hardware", "cc ", "cc,"],
  "extract-params": ["manual", "pdf", "parameter", "extract", "chart", "implementation"],
  "vision-to-coords": ["panel", "image", "photo", "screenshot", "knob position", "detect", "coord"],
  "scaffold-vst": ["scaffold", "generate", "juce", "cmake", "plugin", "template", "boilerplate"],
  "share-device": ["push", "registry", "share", "contribute", "publish", "pull", "community"],
};

function detectRelevantSkills(prompt: string, command?: string): string[] {
  const lower = prompt.toLowerCase();
  const skills: string[] = [];

  // /new-device always loads all five skills
  if (command === "new-device") {
    return Object.keys(SKILL_KEYWORDS);
  }

  // /login only needs share-device
  if (command === "login") {
    return ["share-device"];
  }

  for (const [skill, keywords] of Object.entries(SKILL_KEYWORDS)) {
    if (keywords.some((kw) => lower.includes(kw))) {
      skills.push(skill);
    }
  }
  return skills;
}

// ---------------------------------------------------------------------------
// Terminal command helper — surface runnable commands to the user
// ---------------------------------------------------------------------------

function buildTerminalHints(
  extensionPath: string,
  workspaceRoot: string | undefined
): string {
  const config = getConfig();
  const customToolsPath = config.get<string>("toolsPath", "");
  const outputFolder = config.get<string>("outputFolder", "devices");
  const registryUrl = config.get<string>("registryUrl", "");

  const toolsPath = customToolsPath ||
    path.join(extensionPath, "assets", "tools");

  return [
    "",
    "---",
    "## Runtime Context",
    `Tools path: \`${toolsPath}\``,
    `Output folder: \`${outputFolder}/\``,
    workspaceRoot ? `Workspace: \`${workspaceRoot}\`` : "No workspace open.",
    registryUrl ? `Registry: ${registryUrl}` : "",
  ].filter(Boolean).join("\n");
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

export function registerVstGenParticipant(context: vscode.ExtensionContext): void {
  const { extensionPath } = context;
  const systemPrompt = loadSystemPrompt(extensionPath);

  const handler: vscode.ChatRequestHandler = async (
    request,
    chatContext,
    stream,
    token
  ) => {
    const command = detectCommand(request);
    const workspaceRoot = getWorkspaceRoot();
    const relevantSkills = detectRelevantSkills(request.prompt, command);

    // Build skill injection block
    const skillBlocks = relevantSkills
      .map((s) => {
        const content = loadSkill(extensionPath, s);
        return content ? `\n---\n## Skill: ${s}\n\n${content}` : "";
      })
      .filter(Boolean)
      .join("\n");

    const terminalHints = buildTerminalHints(extensionPath, workspaceRoot);

    // Compose full system block
    const systemBlock = [
      systemPrompt,
      skillBlocks,
      terminalHints,
    ].filter(Boolean).join("\n");

    // Select model — prefer claude-sonnet for code-heavy workflows
    let models = await vscode.lm.selectChatModels({
      vendor: "copilot",
      family: "claude-sonnet-4-5",
    });
    if (!models.length) {
      models = await vscode.lm.selectChatModels({ vendor: "copilot" });
    }
    const model = models[0];
    if (!model) {
      stream.markdown("**VST Gen**: No language model available. Make sure GitHub Copilot is signed in.");
      return;
    }

    const messages: vscode.LanguageModelChatMessage[] = [
      vscode.LanguageModelChatMessage.User(systemBlock),
      ...buildHistory(chatContext.history),
      vscode.LanguageModelChatMessage.User(request.prompt),
    ];

    // Surface a "Run in terminal" button when the agent generates shell commands
    const runner = getToolsRunner(extensionPath, workspaceRoot);
    stream.button({
      command: "vst-gen.openSettings",
      title: "$(settings-gear) VST Gen Settings",
    });

    try {
      const response = await model.sendRequest(messages, {}, token);
      for await (const chunk of response.text) {
        stream.markdown(chunk);
      }
    } catch (err) {
      if (err instanceof vscode.LanguageModelError) {
        stream.markdown(`**VST Gen** error: ${err.message} (${err.code})`);
        return;
      }
      throw err;
    }

    // After /new-device introduction, offer quick actions
    if (command === "new-device") {
      stream.button({
        command: "vst-gen.newDevice",
        title: "$(play) Start New Device Workflow",
      });
    }
    if (command === "login") {
      stream.button({
        command: "vst-gen.login",
        title: "$(account) Login to Registry",
      });
    }
  };

  const participant = vscode.chat.createChatParticipant("vst-gen.agent", handler);
  participant.iconPath = new vscode.ThemeIcon("circuit-board");
  participant.followupProvider = {
    provideFollowups(
      _request: vscode.ChatRequest,
      _context: vscode.ChatContext,
      _result: vscode.ChatResult,
      _token: vscode.CancellationToken
    ): vscode.ChatFollowup[] {
      return [
        {
          prompt: "/new-device ",
          label: "$(add) Start a new device",
          command: "new-device",
        },
        {
          prompt: "List devices in the community registry",
          label: "$(list-unordered) Browse registry",
        },
      ];
    },
  };

  context.subscriptions.push(participant);
}
