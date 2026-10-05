# Quick install: GroundWork for Devin, without plugins

Open Devin in your project and paste this prompt:

```
Install GroundWork into this project. From this project's root, run these two commands, one after the other, exactly as written. They work in any shell, on Linux, macOS, Windows and WSL:

git clone -q --depth 1 https://github.com/Hemanthkaruturi/GroundWork.git .groundwork-install
python3 .groundwork-install/setup/install.py

If `python3` isn't found or opens the Microsoft Store message (common on Windows), run the second command with `py -3` instead, or `python`. If a .groundwork-install folder is already there from an earlier attempt, delete it first. The installer deletes it when it finishes.

Do every step yourself; don't ask me to run anything. If a command fails, show me its error and stop there. Don't try to install GroundWork another way. If it succeeds, tell me only that GroundWork is installed and to start a new Devin session in this project.
```

Devin installs GroundWork and the script checks the install. Then start a new Devin session: GroundWork loads at session start and leads the way from there. Commit the `.devin/` folder so your team gets GroundWork too. To update, paste the same prompt again.

The steps the agent follows, and what the script changes, are in [BOOTSTRAP.md](BOOTSTRAP.md).
