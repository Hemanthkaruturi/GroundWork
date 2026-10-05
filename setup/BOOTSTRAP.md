# Bootstrap: install GroundWork into a project for Devin

These are instructions for a **coding agent**. A person only needs the prompt in the [README](../README.md#using-devin-instead).

The bootstrap installs GroundWork into one project's `.devin/` folder as Devin project skills and hooks, without Devin's plugin system. Use it when the plugin can't be installed, for example because the company has turned Devin plugins off.

## Procedure

1. Work from the root of the target project, not from a GroundWork clone.
2. Run these two commands, one after the other. They contain no shell variables or operators, so they work the same in bash, zsh, PowerShell and cmd:
   ```
   git clone -q --depth 1 https://github.com/Hemanthkaruturi/GroundWork.git .groundwork-install
   python3 .groundwork-install/setup/install.py
   ```
   On Windows, `python3` is often missing or opens a Microsoft Store message. Then run the second command with `py -3`, or `python`. If `.groundwork-install` already exists from an earlier attempt, delete it first. The installer deletes it when it finishes, whether or not the install worked. If a command fails, report its error to the user and stop. Don't work around the error by copying files yourself.
3. Do every step yourself and don't ask the user to run anything. The script checks the install by running GroundWork's session-start hook. When it succeeds, tell the user that GroundWork is installed, and that to start using it they open a new Devin session in this project and type `/bootstrap`. GroundWork loads at session start, and `/bootstrap` runs `groundwork init` and writes the project documents with them. `init` also writes `CODEMAP.md` (where each kind of code lives). For a repo that already has code, `/bootstrap` asks whether to migrate it to the standard code layout or keep its current structure, and moves nothing either way.

Don't commit anything. The user decides when to commit the `.devin/` folder.

## What the script changes

| Path | What it is |
|---|---|
| `.devin/groundwork/` | The engine (including the code layout and code map modules), templates and `STANDARD.md`. Replaced on every run. |
| `.devin/skills/<name>/` | One project skill per GroundWork skill and command (`code-layout` among them), marked with a `.groundwork-installed` file. The script stops without changing anything if one of these names is already taken by a skill it didn't install. |
| `.devin/hooks.v1.json` | The GroundWork hooks. Hooks already in the file are kept. |
| `.devin/groundwork-version` | The GroundWork version and commit that was installed. |

The hooks find the engine in the project folder or the nearest folder above it. If it's missing, they warn and let the prompt through rather than block it. The script refuses to install into the home folder, whose `.devin/` holds Devin's settings for every project. `install.py --uninstall` removes GroundWork from the current folder's `.devin/` and keeps everything else.

It also cleans up the earlier bootstrap layout: a plugin copy in `.devin/skills/groundwork-specflow/`, its `requiredPlugins` entry in `.devin/config.json`, and `.devin/groundwork-README.md`.

Commands have no prefix in this install: `/bootstrap`, `/approve`, `/bypass` and `/status`. Approving and bypassing stay human acts: the hooks only accept them when the user types them.

## Updating

Run the same procedure again. The script replaces its own files and leaves everything else alone.
