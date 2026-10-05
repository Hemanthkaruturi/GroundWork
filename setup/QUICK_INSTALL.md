# Quick install: GroundWork for Devin, without plugins

Open Devin in your project and paste this prompt:

```
Install GroundWork into this project. From this project's root, run this as one command, exactly as written, and show me its full output:

( GW_TMP=$(mktemp -d) && git clone -q https://github.com/Hemanthkaruturi/GroundWork.git "$GW_TMP/GroundWork" && bash "$GW_TMP/GroundWork/setup/install.sh"; rc=$?; rm -rf "$GW_TMP"; exit $rc )

If it fails, stop there and don't try to install GroundWork another way. Otherwise tell me to start a new Devin session.
```

Then start a new Devin session, run `/hooks` to check the groundwork hooks are listed, and run `/bootstrap`. Commit the `.devin/` folder so your team gets GroundWork too. To update, paste the same prompt again.

The steps the agent follows, and what the script changes, are in [BOOTSTRAP.md](BOOTSTRAP.md).
