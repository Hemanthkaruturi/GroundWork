# Quick install: GroundWork for Devin, without plugins

Open Devin in your project and paste this prompt:

```
Install GroundWork into this project. From this project's root, run this as one command, exactly as written:

( GW_TMP=$(mktemp -d) && git clone -q https://github.com/Hemanthkaruturi/GroundWork.git "$GW_TMP/GroundWork" && bash "$GW_TMP/GroundWork/setup/install.sh"; rc=$?; rm -rf "$GW_TMP"; exit $rc )

Do every step yourself; don't ask me to run anything. If it fails, show me its error and stop there. Don't try to install GroundWork another way. If it succeeds, tell me only that GroundWork is installed and to start a new Devin session in this project.
```

Devin installs GroundWork and the script checks the install. Then start a new Devin session: GroundWork loads at session start and leads the way from there. Commit the `.devin/` folder so your team gets GroundWork too. To update, paste the same prompt again.

The steps the agent follows, and what the script changes, are in [BOOTSTRAP.md](BOOTSTRAP.md).
