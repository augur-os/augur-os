/** @jest-environment node */

import { EventEmitter } from "events";

import {
  buildNativeTerminalCommand,
  launchNativeTerminal,
} from "@/lib/server/nativeTerminal";

describe("native terminal launcher", () => {
  it("builds a macOS Terminal.app osascript command", () => {
    const result = buildNativeTerminalCommand({
      platform: "darwin",
      cwd: "/Users/Test User/Projects/Augur",
      argv: ["xa", "--handoff-file", "/tmp/handoff payload.json"],
      hasWindowsTerminal: false,
    });

    expect(result.command).toBe("osascript");
    expect(result.args.join("\n")).toContain('tell application "Terminal" to do script');
    expect(result.args.join("\n")).toContain("cd '/Users/Test User/Projects/Augur'");
    expect(result.args.join("\n")).toContain("'xa' '--handoff-file' '/tmp/handoff payload.json'");
  });

  it("quotes embedded single quotes for macOS shell commands", () => {
    const result = buildNativeTerminalCommand({
      platform: "darwin",
      cwd: "/Users/Test User/O'Neil/Augur",
      argv: ["xa", "--label", "O'Neil handoff"],
      hasWindowsTerminal: false,
    });

    const shellLine = JSON.parse(
      result.args[1].replace('tell application "Terminal" to do script ', ""),
    );
    expect(shellLine).toContain("cd '/Users/Test User/O'\\''Neil/Augur'");
    expect(shellLine).toContain("'xa' '--label' 'O'\\''Neil handoff'");
  });

  it("builds a Windows Terminal command when wt.exe is available", () => {
    const result = buildNativeTerminalCommand({
      platform: "win32",
      cwd: "C:\\Users\\Test User\\Projects\\Augur",
      argv: ["ca", "--handoff-file", "C:\\Temp\\handoff payload.json"],
      hasWindowsTerminal: true,
    });

    expect(result.command).toBe("wt.exe");
    expect(result.args).toEqual([
      "-d",
      "C:\\Users\\Test User\\Projects\\Augur",
      "powershell.exe",
      "-NoExit",
      "-Command",
      "Set-Location -LiteralPath 'C:\\Users\\Test User\\Projects\\Augur'; & 'ca' '--handoff-file' 'C:\\Temp\\handoff payload.json'",
    ]);
  });

  it("falls back to PowerShell when Windows Terminal is unavailable", () => {
    const result = buildNativeTerminalCommand({
      platform: "win32",
      cwd: "C:\\Augur",
      argv: ["ga", "--handoff-file", "C:\\Temp\\handoff.json"],
      hasWindowsTerminal: false,
    });

    expect(result.command).toBe("powershell.exe");
    expect(result.args).toEqual([
      "-NoExit",
      "-Command",
      "Set-Location -LiteralPath 'C:\\Augur'; & 'ga' '--handoff-file' 'C:\\Temp\\handoff.json'",
    ]);
  });

  it("quotes embedded single quotes for PowerShell commands", () => {
    const result = buildNativeTerminalCommand({
      platform: "win32",
      cwd: "C:\\Users\\O'Neil\\Augur",
      argv: ["ca", "--label", "O'Neil handoff"],
      hasWindowsTerminal: false,
    });

    expect(result.args).toEqual([
      "-NoExit",
      "-Command",
      "Set-Location -LiteralPath 'C:\\Users\\O''Neil\\Augur'; & 'ca' '--label' 'O''Neil handoff'",
    ]);
  });

  it("rejects relative Windows cwd values", () => {
    expect(() =>
      buildNativeTerminalCommand({
        platform: "win32",
        cwd: "Augur",
        argv: ["ca"],
        hasWindowsTerminal: false,
      }),
    ).toThrow("Native terminal cwd must be absolute");
  });

  it("rejects unsupported platforms", () => {
    expect(() =>
      buildNativeTerminalCommand({
        platform: "linux",
        cwd: "/tmp/augur",
        argv: ["xa"],
        hasWindowsTerminal: false,
      }),
    ).toThrow("Native terminal handoff is not supported on linux");
  });

  it("rejects empty argv lists", () => {
    expect(() =>
      buildNativeTerminalCommand({
        platform: "darwin",
        cwd: "/tmp/augur",
        argv: [],
        hasWindowsTerminal: false,
      }),
    ).toThrow("Native terminal argv must be non-empty");
  });

  it("rejects empty argv entries", () => {
    expect(() =>
      buildNativeTerminalCommand({
        platform: "darwin",
        cwd: "/tmp/augur",
        argv: [""],
        hasWindowsTerminal: false,
      }),
    ).toThrow("Native terminal argv entries must be non-empty strings");
  });

  it("spawns detached native terminal processes", async () => {
    const child = new EventEmitter() as EventEmitter & { unref: jest.Mock };
    child.unref = jest.fn();
    const spawn = jest.fn(() => child);

    await launchNativeTerminal(
      {
        platform: "darwin",
        cwd: "/tmp/augur",
        argv: ["xa", "--handoff-file", "/tmp/handoff.json"],
      },
      {
        spawn: spawn as any,
        commandExists: async () => false,
      },
    );

    expect(spawn).toHaveBeenCalledWith(
      "osascript",
      expect.any(Array),
      expect.objectContaining({ detached: true, stdio: "ignore" }),
    );
    expect(child.unref).toHaveBeenCalledTimes(1);
  });

  it("rejects safely when the native terminal process cannot spawn", async () => {
    const child = new EventEmitter() as EventEmitter & { unref: jest.Mock };
    child.unref = jest.fn();
    const spawnError = new Error("spawn osascript ENOENT");
    const spawn = jest.fn(() => {
      process.nextTick(() => child.emit("error", spawnError));
      return child;
    });

    await expect(
      launchNativeTerminal(
        {
          platform: "darwin",
          cwd: "/tmp/augur",
          argv: ["xa", "--handoff-file", "/tmp/handoff.json"],
        },
        {
          spawn: spawn as any,
          commandExists: async () => false,
        },
      ),
    ).rejects.toThrow("spawn osascript ENOENT");
  });
});
