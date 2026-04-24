#!/usr/bin/env python3
"""Create a minimal Slay the Spire 2 C# DLL mod skeleton."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_GAME_APP = (
    Path.home()
    / "Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app"
)


def normalize_mod_id(value: str) -> str:
    mod_id = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    if not mod_id:
        raise SystemExit("mod id cannot be empty")
    if not re.match(r"^[a-z_][a-z0-9_]*$", mod_id):
        raise SystemExit("mod id must start with a letter or underscore and contain only letters, digits, underscores")
    return mod_id


def class_name_from_mod_id(mod_id: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in mod_id.split("_") if part) or "Sts2Mod"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-id", required=True, help="Mod id, e.g. reward_runtime_probe")
    parser.add_argument("--out", default="runtime_mod", help="Output parent directory")
    parser.add_argument("--game-app", default=str(DEFAULT_GAME_APP), help="Path to SlayTheSpire2.app")
    parser.add_argument("--name", help="Human-readable mod name")
    parser.add_argument("--description", default="Slay the Spire 2 C# DLL mod.", help="Manifest description")
    parser.add_argument("--author", default="Codex", help="Manifest author")
    parser.add_argument("--affects-gameplay", action="store_true", help="Set manifest affects_gameplay=true")
    args = parser.parse_args()

    mod_id = normalize_mod_id(args.mod_id)
    mod_name = args.name or mod_id.replace("_", " ").title()
    class_name = class_name_from_mod_id(mod_id)
    output_root = Path(args.out).expanduser().resolve()
    game_app = Path(args.game_app).expanduser().resolve()
    game_data = game_app / "Contents/Resources/data_sts2_macos_arm64"
    project_dir = output_root / mod_id

    manifest = {
        "id": mod_id,
        "name": mod_name,
        "author": args.author,
        "description": args.description,
        "version": "0.1.0",
        "has_pck": False,
        "has_dll": True,
        "affects_gameplay": bool(args.affects_gameplay),
        "dependencies": [],
    }

    csproj = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>enable</Nullable>
    <LangVersion>latest</LangVersion>
    <AssemblyName>{mod_id}</AssemblyName>
    <RootNamespace>{mod_id}</RootNamespace>
  </PropertyGroup>

  <ItemGroup>
    <Reference Include="sts2">
      <HintPath>{game_data / "sts2.dll"}</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="GodotSharp">
      <HintPath>{game_data / "GodotSharp.dll"}</HintPath>
      <Private>false</Private>
    </Reference>
    <Reference Include="0Harmony">
      <HintPath>{game_data / "0Harmony.dll"}</HintPath>
      <Private>false</Private>
    </Reference>
  </ItemGroup>
</Project>
"""

    source = f"""using System.Reflection;
using HarmonyLib;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Modding;

namespace {mod_id};

[ModInitializer("Init")]
public static class {class_name}
{{
    private const string ModId = "{mod_id}";
    private static readonly Harmony HarmonyInstance = new($"{{ModId}}.harmony");

    public static void Init()
    {{
        Log.Info($"[{{ModId}}] Initializing");
        HarmonyInstance.PatchAll(Assembly.GetExecutingAssembly());
    }}
}}
"""

    installer = f"""#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
MOD_ID="{mod_id}"
PROJECT_DIR="$ROOT_DIR/$MOD_ID"
GAME_APP="${{STS2_GAME_APP:-{game_app}}}"
MOD_DEST="$GAME_APP/Contents/MacOS/mods/$MOD_ID"

export DOTNET_ROOT="${{DOTNET_ROOT:-$HOME/.dotnet}}"
export PATH="$PATH:$DOTNET_ROOT:$DOTNET_ROOT/tools"

dotnet build "$PROJECT_DIR/$MOD_ID.csproj" -c Release

mkdir -p "$MOD_DEST"
cp "$PROJECT_DIR/$MOD_ID.json" "$MOD_DEST/$MOD_ID.json"
cp "$PROJECT_DIR/bin/Release/net9.0/$MOD_ID.dll" "$MOD_DEST/$MOD_ID.dll"

if [[ -f "$PROJECT_DIR/bin/Release/net9.0/$MOD_ID.pdb" ]]; then
  cp "$PROJECT_DIR/bin/Release/net9.0/$MOD_ID.pdb" "$MOD_DEST/$MOD_ID.pdb"
fi

printf 'Installed %s to %s\\n' "$MOD_ID" "$MOD_DEST"
"""

    write_text(project_dir / f"{mod_id}.csproj", csproj)
    write_text(project_dir / f"{mod_id}.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    write_text(project_dir / f"{class_name}.cs", source)
    install_path = output_root / f"install_{mod_id}.sh"
    write_text(install_path, installer)
    install_path.chmod(0o755)

    print(f"Created {mod_id} in {project_dir}")
    print(f"Installer: {install_path}")


if __name__ == "__main__":
    main()
