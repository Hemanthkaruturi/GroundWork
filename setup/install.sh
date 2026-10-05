#!/bin/bash
# Install GroundWork into the current project for Devin, without Devin's plugin system.
#
# Run it from the root of the project you want GroundWork in:
#   bash <path to a GroundWork clone>/setup/install.sh
#
# It installs into the project's .devin/ folder:
#   .devin/groundwork/          the engine, templates and STANDARD.md
#   .devin/skills/<name>/       one Devin project skill per GroundWork skill and command
#   .devin/hooks.v1.json        the GroundWork hooks (other hooks in the file are kept)
#   .devin/groundwork-version   which GroundWork commit was installed
# Running it again updates an existing install.

set -euo pipefail

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN="$SRC_ROOT/plugins/groundwork-specflow"
TARGET="$(pwd)"

if [ ! -f "$PLUGIN/engine/groundwork.py" ]; then
    echo "error: $SRC_ROOT is not a GroundWork checkout (no plugins/groundwork-specflow/engine/groundwork.py)." >&2
    exit 1
fi
case "$TARGET/" in
    "$SRC_ROOT"/*) echo "error: run this from your project's root, not from inside the GroundWork clone." >&2; exit 1 ;;
esac
PY=$(command -v python3 || command -v python) || { echo "error: GroundWork needs Python 3.10 or newer." >&2; exit 1; }
if ! git -C "$TARGET" rev-parse --git-dir > /dev/null 2>&1; then
    echo "Not a git repository yet; running git init."
    git -C "$TARGET" init -q
fi

GW_SHA=$(git -C "$SRC_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)
GW_VERSION=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$PLUGIN/.claude-plugin/plugin.json")

"$PY" - "$PLUGIN" "$TARGET" <<'EOF'
import json, re, shutil, sys
from pathlib import Path

plugin, target = Path(sys.argv[1]), Path(sys.argv[2])
devin = target / ".devin"
home = devin / "groundwork"
skills = devin / "skills"
MARKER = ".groundwork-installed"   # marks a skill folder this script owns

sources = sorted((plugin / "skills").iterdir()) + sorted((plugin / "devin" / "commands").iterdir())
taken = [s.name for s in sources if (skills / s.name).exists() and not (skills / s.name / MARKER).exists()]
if taken:
    sys.exit(f"error: .devin/skills/ already has {', '.join(taken)}, not installed by GroundWork. "
             "Rename or remove them, then run this again. Nothing was changed.")

# 1. The engine, templates and standard. Replaced wholesale on update.
if home.exists():
    shutil.rmtree(home)
home.mkdir(parents=True)
shutil.copytree(plugin / "engine", home / "engine", ignore=shutil.ignore_patterns("__pycache__"))
shutil.copytree(plugin / "templates", home / "templates")
shutil.copy2(plugin / "STANDARD.md", home / "STANDARD.md")

# 2. Skills and commands as Devin project skills. Paths point at .devin/groundwork, and commands
#    are /approve, /bypass and /status rather than /groundwork-specflow:approve and so on.
def adapt(text: str) -> str:
    return text.replace("${CLAUDE_PLUGIN_ROOT}", ".devin/groundwork").replace("/groundwork-specflow:", "/")

for old in skills.glob(f"*/{MARKER}"):          # drop skills an earlier version installed
    shutil.rmtree(old.parent)
for src in sources:
    dest = skills / src.name
    dest.mkdir(parents=True)
    for f in src.iterdir():
        (dest / f.name).write_text(adapt(f.read_text()))
    (dest / MARKER).write_text("Installed by GroundWork's setup/install.sh. Running it again replaces this folder.\n")

# 3. Hooks. Same hooks as the plugin, in Devin's project format (event names at the top level).
engine = '"${DEVIN_PROJECT_DIR:-.}/.devin/groundwork/engine/groundwork.py"'
ours = json.loads((plugin / "hooks" / "hooks.json").read_text())["hooks"]
for groups in ours.values():
    for group in groups:
        for hook in group["hooks"]:
            hook["command"] = hook["command"].replace('"${CLAUDE_PLUGIN_ROOT}/engine/groundwork.py"', engine)
hooks_file = devin / "hooks.v1.json"
config = json.loads(hooks_file.read_text()) if hooks_file.exists() else {}
mine = lambda group: any(".devin/groundwork/engine/groundwork.py" in h.get("command", "") for h in group.get("hooks", []))
for event in list(config):
    config[event] = [g for g in config[event] if not mine(g)]
    if not config[event]:
        del config[event]
for event, groups in ours.items():
    config.setdefault(event, []).extend(groups)
hooks_file.write_text(json.dumps(config, indent=2) + "\n")

# 4. Undo the earlier bootstrap layout: a plugin copy under .devin/skills listed in requiredPlugins.
legacy = skills / "groundwork-specflow"
if (legacy / "engine" / "groundwork.py").exists():
    shutil.rmtree(legacy)
cfg_file = devin / "config.json"
if cfg_file.exists():
    cfg = json.loads(cfg_file.read_text())
    required = cfg.get("requiredPlugins")
    if isinstance(required, list) and ".devin/skills/groundwork-specflow" in required:
        cfg["requiredPlugins"] = [p for p in required if p != ".devin/skills/groundwork-specflow"]
        cfg_file.write_text(json.dumps(cfg, indent=2) + "\n")
legacy_readme = devin / "groundwork-README.md"
if legacy_readme.exists():
    legacy_readme.unlink()

print(f"Installed {len(sources)} skills and the hooks into .devin/.")
EOF

cat > "$TARGET/.devin/groundwork-version" <<EOF
# Written by GroundWork's setup/install.sh. Run it again to update.
source=https://github.com/Hemanthkaruturi/GroundWork.git
version=${GW_VERSION}
commit=${GW_SHA}
installed=$(date +%Y-%m-%d)
EOF

echo ""
echo "GroundWork ${GW_VERSION} is installed in .devin/. Commit the .devin/ folder so your team gets it too."
echo ""
echo "Next steps:"
echo "1. Start a new Devin session in this project and run /hooks. The groundwork hooks should be listed."
echo "2. Run /bootstrap to set up the project documents. Approve documents with /approve."
