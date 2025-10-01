# Spinner-Cogs Repository Instructions

This file explains how to **add your Spinner-Cogs GitHub repo** to Redbot and install individual cogs from it.

---

## Adding Your GitHub Repo

1. Open your Discord server where your Redbot is running.
2. Use the following command to add your GitHub repository:

```bash
[p]repo add spinner-cogs https://github.com/FreeSpinner/Spinner-Cogs
```

- Replace `spinner-cogs` with any friendly name for your repo.
- Replace the URL with your actual GitHub repository URL.

3. Once added, you can list all repositories:

```bash
[p]repo list
```

This confirms your repo has been added.

---

## Installing Individual Cogs

1. To install a cog from your repository, run:

```bash
[p]cog install spinner-cogs <cog_name>
```

- Example: If your cog is named `mc_sync`, use:

```bash
[p]cog install spinner-cogs mc_sync
```

2. Once installed, load the cog:

```bash
[p]load mc_sync
```

3. You can also update your cogs when you push new changes:

```bash
[p]cog update mc_sync
```

---

## Notes

- Each cog in your repository should have a **unique name** and an `info.json` file describing it.
- Make sure your `__init__.py` properly imports the cog and calls `setup(bot)`.
- To remove a cog:

```bash
[p]cog unload <cog_name>
[p]cog delete <cog_name>
```

- To remove the repository entirely if needed:

```bash
[p]repo remove spinner-cogs
```

- Keep your GitHub repo organized: each cog should be in its own folder with its own `mc_sync.py` (or relevant name), `__init__.py`, and `info.json` for proper installation.

