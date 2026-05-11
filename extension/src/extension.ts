/**
 * VST Gen — VS Code Extension Entry Point
 *
 * Registers the @vst-gen chat participant and the command palette commands.
 * The participant is available in any workspace — no vst-gen-agent repo needed.
 */

import * as vscode from "vscode";
import { registerVstGenParticipant } from "./chatParticipant";

export function activate(context: vscode.ExtensionContext): void {
  registerVstGenParticipant(context);

  // Command palette shortcuts that open the chat panel pre-populated
  context.subscriptions.push(
    vscode.commands.registerCommand("vst-gen.newDevice", () => {
      vscode.commands.executeCommand(
        "workbench.action.chat.open",
        { query: "@vst-gen /new-device " }
      );
    }),
    vscode.commands.registerCommand("vst-gen.login", () => {
      vscode.commands.executeCommand(
        "workbench.action.chat.open",
        { query: "@vst-gen /login " }
      );
    }),
    vscode.commands.registerCommand("vst-gen.openSettings", () => {
      vscode.commands.executeCommand(
        "workbench.action.openSettings",
        "vstGen"
      );
    })
  );
}

export function deactivate(): void {
  // nothing to clean up
}
