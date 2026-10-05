# Quick Install: GroundWork

> **Last updated:** 2026-10-05
> **Initiated by:** terminator
> **Model:** claude-sonnet

---

## One-line installation

To install GroundWork without using the plugin marketplace, run this command in your project:

```bash
git clone https://github.com/Hemanthkaruturi/GroundWork.git .tmp-groundwork && .tmp-groundwork/setup/install.sh
```

This will:
1. Clone the GroundWork repository to a temporary directory
2. Copy the plugin to `.devin/skills/groundwork-specflow/`
3. Configure `.devin/config.json` to auto-load the plugin
4. Record version information for future updates
5. Clean up the temporary directory

## After installation

Once installed, bootstrap your project:

```bash
python3 .devin/skills/groundwork-specflow/engine/groundwork.py bootstrap
```

Or in Devin:

```
/hooks
/groundwork-specflow:bootstrap
```

## Manual installation

If you prefer to follow the steps manually, see [BOOTSTRAP.md](BOOTSTRAP.md) for detailed instructions.
