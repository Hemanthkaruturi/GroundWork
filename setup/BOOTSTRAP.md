# Bootstrap: GroundWork Plugin Installation

> **Last updated:** 2026-10-05
> **Initiated by:** terminator
> **Model:** claude-sonnet

---

This file contains instructions for a **coding agent** to install GroundWork into a target project. It is meant to be read and executed by the agent, not by a human.

If you are a human, see the [README.md](../README.md) for installation instructions.

---

## Context

**GroundWork** is a plugin for Claude Code and Devin that makes coding agents work from a shared, written plan instead of improvising. It includes:

- **Skills** for each step: bootstrap, interview, RFC, spec, plan, tasks, evals, implement, handover, resume, bug fixing, ownership and plain writing.
- **Commands** for approval, bypass, and status.
- **Hooks** that enforce the workflow before code edits.
- **A local command-line engine** that checks projects against the written standard.

Your job is to copy the plugin files from this cloned repository into the **target project** you are currently working in, so the plugin can be used without needing to install it through the plugin marketplace.

---

## Prerequisites

Before proceeding, verify:

1. **You are running inside the target project** -- your working directory is the target project's root, not the GroundWork clone.
2. **GroundWork has been cloned** to a temporary directory inside the target project (e.g. `.tmp-groundwork`). If it has not been cloned yet, clone it now:
   ```bash
   git clone https://github.com/Hemanthkaruturi/GroundWork.git .tmp-groundwork
   ```
3. **The target project is a git repository** (or will become one).

---

## Procedure

### Step 1: Copy plugin files to .devin/skills/

Copy the GroundWork plugin into the target project's `.devin/skills/` directory. This makes it available for Devin without requiring plugin marketplace installation.

**Commands** (assuming GroundWork was cloned to `.tmp-groundwork`):

```bash
# Create the skills directory
mkdir -p .devin/skills

# Copy the entire plugin directory
rm -rf .devin/skills/groundwork-specflow
cp -r .tmp-groundwork/plugins/groundwork-specflow .devin/skills/groundwork-specflow

# Copy the README to the project root for reference
cp .tmp-groundwork/README.md .devin/groundwork-README.md
```

### Step 2: Configure .devin/config.json (optional)

If you want GroundWork to be automatically loaded when the project is opened in Devin, add it to the project's `.devin/config.json`:

```bash
# Create or update .devin/config.json
if [ ! -f .devin/config.json ]; then
  echo '{"requiredPlugins": []}' > .devin/config.json
fi

# Add GroundWork to requiredPlugins if not already present
python3 << 'EOF'
import json
import os

config_path = '.devin/config.json'
with open(config_path, 'r') as f:
    config = json.load(f)

plugin_path = '.devin/skills/groundwork-specflow'
if 'requiredPlugins' not in config:
    config['requiredPlugins'] = []

if plugin_path not in config['requiredPlugins']:
    config['requiredPlugins'].append(plugin_path)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    print("Added GroundWork to requiredPlugins")
else:
    print("GroundWork already in requiredPlugins")
EOF
```

### Step 3: Version tracking

Record the GroundWork version for future update checks:

```bash
GW_SHA=$(cd .tmp-groundwork && git rev-parse HEAD)
GW_BRANCH=$(cd .tmp-groundwork && git rev-parse --abbrev-ref HEAD)
GW_DATE=$(date +%Y-%m-%d)
cat > .devin/groundwork-version << EOF
# GroundWork sync metadata -- do not edit manually
source=https://github.com/Hemanthkaruturi/GroundWork.git
branch=${GW_BRANCH}
commit=${GW_SHA}
synced=${GW_DATE}
EOF
```

### Step 4: Clean up

Remove the cloned GroundWork repository:

```bash
rm -rf .tmp-groundwork
```

### Step 5: Bootstrap the project

Now that GroundWork is installed, you can bootstrap the project:

```bash
# In Devin CLI/Desktop, run:
# /hooks
# Then run the bootstrap skill
```

Or use the Python engine directly:

```bash
python3 .devin/skills/groundwork-specflow/engine/groundwork.py bootstrap
```

---

## After Bootstrap

Once this procedure completes:

- The target project has GroundWork installed under `.devin/skills/groundwork-specflow/`
- The plugin is available for use in Devin without requiring marketplace installation
- The file `.devin/groundwork-version` tracks the synced version for future updates
- The cloned GroundWork directory has been removed -- it is no longer needed

---

## Usage

After installation, use GroundWork as follows:

1. **Bootstrap the project:** Run `/groundwork-specflow:bootstrap` or the Python engine
2. **Request features:** Describe what you want; the agent will interview you and write an RFC
3. **Approve when ready:** Run `/groundwork-specflow:approve` to approve the RFC and proceed
4. **Continue the workflow:** The agent will write specs, plans, and implement in steps

See the [README.md](../README.md) for complete usage instructions.

---

## Updates

To update GroundWork in the future:

1. Check for updates by comparing the current commit with the latest from GitHub
2. If a newer version exists, re-run this bootstrap procedure
3. The version tracking in `.devin/groundwork-version` will be updated

The update check can be automated similar to ca-standards by checking the latest commit from the GitHub repository.
