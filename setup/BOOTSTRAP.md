# Bootstrap: install GroundWork into a project for Devin

These are instructions for a **coding agent**. A person only needs the prompt in the [README](../README.md#using-devin-instead).

The bootstrap installs GroundWork into one project's `.devin/` folder as Devin project skills and hooks, without Devin's plugin system. Use it when the plugin can't be installed, for example because the company has turned Devin plugins off.

## Procedure

1. Work from the root of the target project, not from a GroundWork clone.
2. Run this as **one** command. Shell variables may not survive between separate commands, so don't split it up:
   ```bash
   ( GW_TMP=$(mktemp -d) && git clone -q https://github.com/Hemanthkaruturi/GroundWork.git "$GW_TMP/GroundWork" && bash "$GW_TMP/GroundWork/setup/install.sh"; rc=$?; rm -rf "$GW_TMP"; exit $rc )
   ```
   It clones GroundWork into a temporary folder outside the project, runs the install script, and deletes the folder again. If it fails, report its error to the user and stop. Don't work around the error by copying files yourself.
3. Show the user what the script printed, and tell them to start a new Devin session, run `/hooks` to check the groundwork hooks are listed, then run `/bootstrap`.

Don't commit anything. The user decides when to commit the `.devin/` folder.

## What the script changes

| Path | What it is |
|---|---|
| `.devin/groundwork/` | The engine, templates and `STANDARD.md`. Replaced on every run. |
| `.devin/skills/<name>/` | One project skill per GroundWork skill and command, marked with a `.groundwork-installed` file. The script stops without changing anything if one of these names is already taken by a skill it didn't install. |
| `.devin/hooks.v1.json` | The GroundWork hooks. Hooks already in the file are kept. |
| `.devin/groundwork-version` | The GroundWork version and commit that was installed. |

It also cleans up the earlier bootstrap layout: a plugin copy in `.devin/skills/groundwork-specflow/`, its `requiredPlugins` entry in `.devin/config.json`, and `.devin/groundwork-README.md`.

Commands have no prefix in this install: `/bootstrap`, `/approve`, `/bypass` and `/status`. Approving and bypassing stay human acts: the hooks only accept them when the user types them.

## Updating

Run the same procedure again. The script replaces its own files and leaves everything else alone.
