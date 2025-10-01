# McSync Cog

A Red Discord Bot cog that syncs Minecraft usernames with Discord users via a **2-step auth code**,  
confirms their presence online via RCON, and rewards them with configurable commands.

---

## Features

- Two-step auth code sync:
  - `!sync <username>` → Sends code in-game via RCON
  - `!sync <username> <code>` → Confirms sync and executes rewards
- Rewards executed via RCON with `{user}` replaced by Minecraft username
- Admins can configure RCON per guild (`!rcon set <host> <port> <password>`)
- Role-based permission system for checking link status
- Admin commands: `unsyncmc`, `setcheckerroles`, `setreward`, `rcon test/clear`
- Secure: original RCON messages deleted on setup, temporary auth codes stored in memory

---

## Commands

### User Commands

| Command | Description |
|---------|-------------|
| `!sync <username>` | Sends an auth code to the Minecraft username in-game |
| `!sync <username> <code>` | Confirms sync and executes reward commands |
| `!checklink [member]` | Check a user's link status (admins/allowed roles only) |

### Admin Commands

| Command | Description |
|---------|-------------|
| `!unsyncmc <member>` | Reset a user's Minecraft link |
| `!setcheckerroles <roles...>` | Set roles allowed to check link status |
| `!setreward` | Configure reward commands with `{user}` placeholder |
| `!rcon set <host> <port> <password>` | Set RCON connection (original message deleted) |
| `!rcon test` | Test current RCON connection |
| `!rcon clear` | Clear saved RCON configuration |

---

## Installation

1. Clone this repo into your Red cog folder:

```bash
[p]repo add spinner-cogs https://github.com/FreeSpinner/Spinner-Cogs main
[p]cog install spinner-cogs McSync
[p]load McSync
```

2. Configure RCON for your server:

```bash
[p]rcon set <host> <port> <password>
```

3. Set up reward commands:

```bash
[p]setreward
```

4. Users can now sync via:

```bash
!sync <username>
```

- Receives an auth code in-game  
```bash
!sync <username> <code>
```
- Confirms sync and executes rewards

---

## Notes

- Reward commands support `{user}` placeholder to automatically insert the Minecraft username.
- Auth codes are stored **temporarily in memory**, and expire if the bot restarts.
- Only admins or designated roles may check other users' link status.
- Original RCON messages during setup are deleted to protect sensitive information.

---

Enjoy syncing your Minecraft players with Discord easily! 🎉