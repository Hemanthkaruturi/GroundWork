# Quick install: GroundWork for Devin, without plugins

Open Devin in your project and paste this prompt:

```
Install GroundWork into this project. Clone https://github.com/Hemanthkaruturi/GroundWork.git into a new temporary folder outside this project, then run `bash <that folder>/setup/install.sh` from this project's root. If the script fails, show me its error and stop. Otherwise delete the temporary folder, show me what the script printed, and tell me to start a new Devin session.
```

Then start a new Devin session, run `/hooks` to check the groundwork hooks are listed, and run `/bootstrap`. Commit the `.devin/` folder so your team gets GroundWork too. To update, paste the same prompt again.

The steps the agent follows, and what the script changes, are in [BOOTSTRAP.md](BOOTSTRAP.md).
