---
name: slay-the-spire-2-mod
description: Create, inspect, build, and debug Slay the Spire 2 C# DLL mods on macOS. Use when Codex needs to write an STS2 mod, add runtime probes, patch game classes with Harmony, overlay UI inside the game, export runtime state, install a mod into SlayTheSpire2.app, or troubleshoot STS2 mod loading, Godot C# UI, fonts, logs, and decompiled game APIs.
---

# Slay the Spire 2 Mod

## Core Rule

Prefer the in-process C# DLL mod path when the user needs live game state or game UI. Save-file polling is insufficient for transient screens that exist only in runtime objects.

Use three decision buckets:

- **Read runtime state**: patch or observe the class that owns the data, then export JSON or logs.
- **Show in-game UI**: attach Godot `Control` nodes to the owning screen or card holder; avoid changing gameplay data.
- **Change behavior**: use Harmony patches only after proving the target method and side effects from decompiled code.

## Setup Checks

Start every STS2 mod task by verifying the real local paths:

```bash
GAME_APP="${STS2_GAME_APP:-$HOME/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app}"
GAME_DATA="$GAME_APP/Contents/Resources/data_sts2_macos_arm64"
ls "$GAME_DATA"/{sts2.dll,GodotSharp.dll,0Harmony.dll}
```

Use `.NET` from `~/.dotnet` if needed:

```bash
export DOTNET_ROOT="$HOME/.dotnet"
export PATH="$PATH:$DOTNET_ROOT:$DOTNET_ROOT/tools"
```

If creating a new mod skeleton, run:

```bash
python3 /Users/lzw/.codex/skills/slay-the-spire-2-mod/scripts/create_sts2_mod.py \
  --mod-id my_sts2_mod \
  --out runtime_mod
```

Then build and install with the generated `install_<mod-id>.sh`.

## DLL Mod Shape

Every minimal C# DLL mod needs:

- `<mod-id>.json` manifest with `"has_dll": true`.
- `<mod-id>.csproj` targeting the same compatible .NET line used by the game; `net9.0` worked in this environment.
- References to `sts2.dll`, `GodotSharp.dll`, and `0Harmony.dll` with `<Private>false</Private>`.
- A static class with `[ModInitializer("Init")]`.
- A unique Harmony id and `Harmony.PatchAll(Assembly.GetExecutingAssembly())`.
- Game restart after every reinstall; STS2 does not hot-load updated DLLs into an already running process.

## Reverse First

Before patching, find the runtime owner:

```bash
export DOTNET_ROOT="$HOME/.dotnet"
export PATH="$PATH:$DOTNET_ROOT:$DOTNET_ROOT/tools"
ilspycmd -p -o /tmp/sts2-decompiled "$GAME_DATA/sts2.dll"
rg -n "ClassOrMethodName|FieldName" /tmp/sts2-decompiled -g '*.cs'
```

For live card rewards, the verified owner is `NCardRewardSelectionScreen._options`, populated in `RefreshOptions(...)`. The card UI row is `UI/CardRow`, containing `NGridCardHolder` children.

Read `references/modding-notes.md` when working on reward screens, runtime export, UI overlays, fonts, or troubleshooting.

## UI Pattern

For in-game overlays:

- Attach UI after the target screen has created child nodes, usually in a postfix patch on a refresh or ready method.
- Set `MouseFilter = Control.MouseFilterEnum.Ignore` for informational overlays so they do not break clicks.
- Use `MegaLabel`, not raw Godot `Label`, for Chinese or localized text.
- Add `ThemeConstants.Label.Font` override, preferably copied from an existing game label such as a card title.
- Remove prior injected nodes by stable `Name` before reattaching to avoid duplicate labels.

Minimal reward-screen hook:

```csharp
[HarmonyPatch(typeof(NCardRewardSelectionScreen), nameof(NCardRewardSelectionScreen.RefreshOptions))]
public static class CardRewardRefreshOptionsPatch
{
    public static void Postfix(NCardRewardSelectionScreen __instance)
    {
        Control? cardRow = __instance.GetNodeOrNull<Control>("UI/CardRow");
        // Iterate cardRow.GetChildren().OfType<NGridCardHolder>() and attach UI.
    }
}
```

## Runtime Export Pattern

For exporting data:

- Reflect private fields only after confirming field names in decompiled source.
- Export to `Path.Combine(OS.GetUserDataDir(), "<file>.json")`.
- Include `active`, `screen`, `trigger`, timestamp, and a stable list of logical ids.
- Also write `active=false` when the overlay closes, so consumers do not show stale state.

## Install And Verify

Install location:

```bash
"$GAME_APP/Contents/MacOS/mods/<mod-id>/"
```

Expected files:

- `<mod-id>.json`
- `<mod-id>.dll`
- Optional `<mod-id>.pdb`

Validate in this order:

```bash
dotnet build path/to/<mod-id>.csproj -c Release
./install_<mod-id>.sh
rg "<mod-id>|Initializing|Attached|Wrote" "$HOME/Library/Application Support/SlayTheSpire2/godot.log"
```

If the mod writes runtime JSON, inspect:

```bash
ls -l "$HOME/Library/Application Support/SlayTheSpire2"
```

## Common Failure Modes

- **No effect after install**: restart the game; updated DLL is not hot-loaded.
- **Mod loads but save path changed**: enabling mods may move runs to `steam/<id>/modded/profile1/saves/current_run.save`.
- **Chinese text is garbled**: raw `Label` lacks the game font path. Use `MegaLabel` and a `ThemeConstants.Label.Font` override.
- **Early startup null reference**: do not assume singletons are initialized in `Init`; patch `_Ready` or use a stored observed instance.
- **UI blocks card clicks**: set `MouseFilter.Ignore` on every injected informational `Control`.
- **Patch compiles but runtime class differs**: re-open decompiled source and patch the method that actually owns the data or child nodes.
