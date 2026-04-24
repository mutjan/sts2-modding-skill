# Slay the Spire 2 Modding Notes

## Validated Environment

The verified macOS game app path is:

```text
~/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app
```

The verified managed assemblies live under:

```text
Contents/Resources/data_sts2_macos_arm64/
```

The minimum references that worked:

- `sts2.dll`
- `GodotSharp.dll`
- `0Harmony.dll`

The installed mod directory is:

```text
Contents/MacOS/mods/<mod-id>/
```

## Manifest

Use this shape for a DLL-only mod:

```json
{
  "id": "reward_runtime_probe",
  "name": "Reward Runtime Probe",
  "author": "Codex",
  "description": "Exports live runtime state.",
  "version": "0.1.0",
  "has_pck": false,
  "has_dll": true,
  "affects_gameplay": false,
  "dependencies": []
}
```

Keep `"affects_gameplay": false` only for probes and informational UI. Set it truthfully for behavior-changing mods.

## Project File

The tested project file pattern:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>enable</Nullable>
    <LangVersion>latest</LangVersion>
    <AssemblyName>reward_runtime_probe</AssemblyName>
    <RootNamespace>reward_runtime_probe</RootNamespace>
  </PropertyGroup>

  <ItemGroup>
    <Reference Include="sts2">
      <HintPath>/absolute/path/to/data_sts2_macos_arm64/sts2.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="GodotSharp">
      <HintPath>/absolute/path/to/data_sts2_macos_arm64/GodotSharp.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="0Harmony">
      <HintPath>/absolute/path/to/data_sts2_macos_arm64/0Harmony.dll</HintPath>
      <Private>false</Private>
    </Reference>
  </ItemGroup>
</Project>
```

## Minimal Mod Initializer

```csharp
using System.Reflection;
using HarmonyLib;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Modding;

namespace reward_runtime_probe;

[ModInitializer("Init")]
public static class RewardRuntimeProbe
{
    private const string ModId = "reward_runtime_probe";
    private static readonly Harmony HarmonyInstance = new($"{ModId}.harmony");

    public static void Init()
    {
        Log.Info($"[{ModId}] Initializing");
        HarmonyInstance.PatchAll(Assembly.GetExecutingAssembly());
    }
}
```

## Live Card Reward Findings

The live three-card reward is not in `current_run.save` before selection. The game saves before reward UI opens.

The verified runtime source is:

```text
NCardRewardSelectionScreen._options : IReadOnlyList<CardCreationResult>
```

`CardCreationResult.Card` is the displayed `CardModel`. Useful fields:

- `result.Card.Id`
- `result.Card.Title`
- `result.Card.CurrentUpgradeLevel`
- `result.Card.IsUpgraded`
- `result.originalCard.Id`
- `result.originalCard.Title`
- `result.HasBeenModified`
- `result.ModifyingRelics`

Patch target:

```csharp
[HarmonyPatch(typeof(NCardRewardSelectionScreen), nameof(NCardRewardSelectionScreen.RefreshOptions))]
public static class CardRewardRefreshOptionsPatch
{
    public static void Postfix(NCardRewardSelectionScreen __instance)
    {
        // Read _options via reflection or inspect UI children after refresh.
    }
}
```

## Reward UI Findings

`NCardRewardSelectionScreen.RefreshOptions(...)` creates:

```text
UI/CardRow
  NGridCardHolder
    NCard
```

Card spacing is based on `350f`. `NCard.defaultSize` is `300 x 422`.

Use this pattern for labels above cards:

```csharp
Control? cardRow = screen.GetNodeOrNull<Control>("UI/CardRow");
List<NGridCardHolder> holders = cardRow.GetChildren().OfType<NGridCardHolder>().ToList();
```

When adding informational UI:

```csharp
Control container = new()
{
    Name = "StableInjectedNodeName",
    MouseFilter = Control.MouseFilterEnum.Ignore,
    ZIndex = 4096
};
```

Remove existing injected children by `Name` before adding new ones.

## Chinese Font Fix

Raw `Godot.Label` can show Chinese as garbled boxes. Use `MegaLabel` from `MegaCrit.Sts2.addons.mega_text` and set a font override.

Working pattern:

```csharp
using MegaCrit.Sts2.addons.mega_text;

MegaLabel label = new()
{
    MouseFilter = Control.MouseFilterEnum.Ignore,
    HorizontalAlignment = HorizontalAlignment.Center,
    VerticalAlignment = VerticalAlignment.Center,
    AutowrapMode = TextServer.AutowrapMode.WordSmart,
    MinFontSize = 16,
    MaxFontSize = 22
};

MegaLabel? cardTitle = holder.CardNode?.GetNodeOrNull<MegaLabel>("%TitleLabel");
Font? font = cardTitle?.GetThemeFont(ThemeConstants.Label.Font, "Label")
    ?? holder.GetThemeFont(ThemeConstants.Label.Font, "Label");

if (font != null)
{
    label.AddThemeFontOverride(ThemeConstants.Label.Font, font);
}

label.AddThemeFontSizeOverride(ThemeConstants.Label.FontSize, 22);
label.AddThemeColorOverride(ThemeConstants.Label.FontColor, Colors.White);
label.AddThemeColorOverride(ThemeConstants.Label.FontOutlineColor, Colors.Black);
label.AddThemeConstantOverride(ThemeConstants.Label.OutlineSize, 4);
label.SetTextAutoSize("模拟推荐 82% · S\n优先拿：补伤害，过渡强");
```

`MegaLabel` can throw if no theme font override exists, so always provide a font override before it enters the tree.

## Overlay Stack Observer

For tracking current overlay:

```csharp
[HarmonyPatch(typeof(NOverlayStack), nameof(NOverlayStack._Ready))]
public static class OverlayStackReadyPatch
{
    public static void Postfix(NOverlayStack __instance)
    {
        // Store instance and subscribe to Changed.
    }
}
```

Avoid assuming `NOverlayStack.Instance` is valid during mod `Init`. Store the instance received from `_Ready` and use that for `Peek()`.

## Runtime JSON Export

Use `OS.GetUserDataDir()` so output lands in the game user data folder:

```csharp
string path = Path.Combine(OS.GetUserDataDir(), "runtime_reward.json");
Directory.CreateDirectory(Path.GetDirectoryName(path) ?? OS.GetUserDataDir());
File.WriteAllText(path, JsonSerializer.Serialize(snapshot, JsonOptions));
```

Include a false/empty snapshot when the screen disappears:

```json
{
  "source": "reward_runtime_probe",
  "active": false,
  "screen": null,
  "trigger": "overlay_changed",
  "cards": []
}
```

## Logs

Check:

```bash
rg "mod-id|Initializing|Attached|Wrote|Exception" "$HOME/Library/Application Support/SlayTheSpire2/godot.log"
```

Useful positive evidence:

- Found mod manifest.
- Loading assembly DLL.
- Calling initializer.
- `[mod-id] Initializing`.
- Custom log line from the patch.

## Save Path Caveat

After a mod loads, STS2 can use modded save paths:

```text
~/Library/Application Support/SlayTheSpire2/steam/<steam-id>/modded/profile1/saves/current_run.save
```

Do not assume the unmodded save path remains current.
