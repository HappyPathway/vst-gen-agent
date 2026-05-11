/**
 * VST Gen — Tools Runner
 *
 * Resolves the path to Python tool scripts and runs them in a VS Code
 * terminal. Tools are first looked up in the user-configured toolsPath
 * setting, then in the extension's bundled assets/tools/ directory.
 *
 * The terminal is reused across calls to avoid cluttering the UI.
 */

import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";

let sharedTerminal: vscode.Terminal | undefined;

function getOrCreateTerminal(): vscode.Terminal {
  if (!sharedTerminal || sharedTerminal.exitStatus !== undefined) {
    sharedTerminal = vscode.window.createTerminal({
      name: "VST Gen",
      iconPath: new vscode.ThemeIcon("circuit-board"),
    });
  }
  return sharedTerminal;
}

export interface ToolsRunner {
  /** Resolve path to a Python tool script (e.g. "midi_capture.py") */
  resolveTool(name: string): string;
  /** Run a shell command in the shared VST Gen terminal */
  run(command: string, show?: boolean): void;
  /** Run a named Python tool with args */
  runTool(scriptName: string, args: string, show?: boolean): void;
}

export function getToolsRunner(
  extensionPath: string,
  workspaceRoot: string | undefined
): ToolsRunner {
  const config = vscode.workspace.getConfiguration("vstGen");
  const customToolsPath = config.get<string>("toolsPath", "");
  const bundledToolsPath = path.join(extensionPath, "assets", "tools");

  function resolveTool(name: string): string {
    // 1. User-configured path takes priority
    if (customToolsPath) {
      const candidate = path.join(customToolsPath, name);
      if (fs.existsSync(candidate)) {
        return candidate;
      }
    }
    // 2. Bundled copy
    const bundled = path.join(bundledToolsPath, name);
    if (fs.existsSync(bundled)) {
      return bundled;
    }
    // 3. Fallback — let Python find it on PATH (unlikely but graceful)
    return name;
  }

  function run(command: string, show = true): void {
    const terminal = getOrCreateTerminal();
    if (show) {
      terminal.show(true);
    }
    terminal.sendText(command);
  }

  function runTool(scriptName: string, args: string, show = true): void {
    const scriptPath = resolveTool(scriptName);
    const cwd = workspaceRoot ?? process.cwd();
    run(`cd "${cwd}" && python3 "${scriptPath}" ${args}`, show);
  }

  return { resolveTool, run, runTool };
}
