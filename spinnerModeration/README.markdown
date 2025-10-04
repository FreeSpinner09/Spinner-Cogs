# SpinnerModeration Cog for Red Discord Bot

## Overview

**SpinnerModeration** is a powerful and feature-rich moderation cog designed for the [Red Discord Bot](https://github.com/Cog-Creators/Red-DiscordBot) (v3.5+). It provides a comprehensive moderation system with point-based warnings, automated punishments, customizable roles, mod logging, DM notifications, and an interactive Discord UI for configuration. Built with modern async patterns and Discord.py 2.3+, this cog is designed for production-grade use, offering robust error handling, extensibility, and compatibility with hybrid commands (prefix and slash).

This cog is part of the **Spinner-Cogs** repository and is intended for Discord server administrators seeking a modular, user-friendly moderation solution.

---

## Features

### Warn System
- **Point-based Warnings**: Issue warnings with customizable points, durations, and permanence using `[p]warn <member> <reason>`.
- **Warning Management**: View active and expired warnings with `[p]warnings <member>` and clear them with `[p]clearwarns <member>` (includes confirmation).
- **Custom Warn Reasons**: Define reasons with points and durations using `[p]reason add <name> <points> [duration] [--perm]`, remove with `[p]reason remove <name>`, or list with `[p]reason list`.
- **Auto-Expiry**: Warnings expire automatically based on configured durations, checked on-demand without background loops.

### Automated Punishments
- **Threshold-based Actions**: Configure punishments (mute, kick, ban, warn) triggered when a user reaches a point threshold using `[p]punishments add <points> <action> [duration]`.
- **GUI Configuration**: Interactive setup with `[p]punishments gui`, featuring buttons and modals for adding, editing, or removing thresholds.
- **List and Remove**: View configured punishments with `[p]punishments list` and remove with `[p]punishments remove <points>`.

### Mute and Timeout System
- **Flexible Mutes**: Mute members with `[p]mute <member> [duration] [reason]`, applying a mute role and/or Discord timeout.
- **Interactive Mute Role**: Set or create a mute role with `[p]modset muterole [role]`, with an option to auto-create a role with proper permissions.
- **Unmute**: Remove mutes and timeouts with `[p]unmute <member>`.

### Kick, Ban, and Unban
- **Standard Moderation**: Kick with `[p]kick <member> [reason]`, ban with `[p]ban <member> [reason]`, and unban with `[p]unban <user_id or name#discrim>`.
- **Confirmation and Logging**: All actions include embed confirmations and modlog entries.

### Message Purge
- **Channel Cleanup**: Delete messages with `[p]purge <amount>`, restricted to moderators/administrators, with logging support.

### Moderation Setup
- **Role Management**: Add/remove moderator and admin roles with `[p]modset addmodrole <role>`, `[p]modset removemodrole <role>`, `[p]modset addadminrole <role>`, and `[p]modset removeadminrole <role>`.
- **Modlog Channel**: Set a logging channel with `[p]modset setlogchannel <channel>`.
- **DM Notifications**: Toggle DMs with `[p]modset toggledm` and customize the template via a modal with `[p]modset setdmtemplate`.
- **Permission Sync**: Optionally sync with Redbot’s mod/admin permissions using `[p]modset syncperms`.

### Logging
- **Modlog Embeds**: All moderation actions (warn, mute, kick, ban, unban, purge, clearwarns) are logged to a configurable channel with action-specific colors (e.g., yellow for warn, red for ban).
- **Embed Details**: Include user, moderator, reason, points (if applicable), duration, and timestamp.

### DM Notifications
- **Customizable Template**: Supports `{user}`, `{action}`, `{reason}`, `{points}`, `{duration}`, `{guild}` placeholders.
- **Toggleable**: Enable/disable DMs per guild.
- **Privacy**: Moderator names are excluded from DMs.

### GUI Configuration
- **Interactive Setup**: Use `[p]punishments gui` for a Discord UI with buttons (`Add/Edit`, `Remove`, `Close`) and modals for managing punishment thresholds.
- **DM Template Modal**: Edit the DM template interactively with `[p]modset setdmtemplate`.
- **Extensible Design**: UI components are modular for future additions (e.g., role management).

### Error Handling and Quality
- **Robust Checks**: Commands enforce role-based permissions, with fallback to Redbot’s `mod_or_permissions` and `admin_or_permissions`.
- **Graceful Degradation**: Handles missing permissions, invalid inputs, and API errors (e.g., Forbidden, NotFound) with user-friendly messages.
- **Logging**: Uses `logging.getLogger("red.spinnerModeration")` for debugging and error tracking.
- **Concurrency Safety**: Config updates use async context managers to ensure data consistency.

### Future-Proofing
- **Hybrid Commands**: Commands are ready for slash command migration using `commands.hybrid_command` and `commands.hybrid_group`.
- **Localization Ready**: Structured for `_()` translation support.
- **Extensibility**: Modular helper functions and UI classes allow easy additions (e.g., new punishment types, audit log integration).

---

## Installation

### Prerequisites
- **Red Discord Bot**: Version 3.5 or higher.
- **Discord.py**: Version 2.3 or higher.
- **Python**: Version 3.8+ (as required by Redbot).
- **Permissions**: Bot must have `manage_roles`, `kick_members`, `ban_members`, `manage_messages`, and `send_messages` permissions for full functionality.

### Steps
1. **Add the Repository**:
   - In your Discord server where Redbot is running, add the Spinner-Cogs repository:
     ```
     [m]repo add spinner-cogs https://github.com/FreeSpinner09/Spinner-Cogs
     ```
   - Verify the repository was added:
     ```
     [m]repo list
     ```

2. **Install the SpinnerModeration Cog**:
   - Install the cog from the repository:
     ```
     [m]cog install spinner-cogs SpinnerModeration
     ```
   - Load the cog:
     ```
     [m]load SpinnerModeration
     ```
   - Confirm the cog is loaded:
     ```
     [m]cog list
     ```

3. **Set Up Permissions**:
   - Configure moderator/admin roles with `[p]modset addmodrole <role>` and `[p]modset addadminrole <role>`.
   - Set a modlog channel with `[p]modset setlogchannel <channel>`.
   - Optionally enable DM notifications with `[p]modset toggledm`.

4. **Test Commands**:
   - Try `[p]help SpinnerModeration` to view all commands.
   - Test `[p]warn <member> test` or `[p]punishments gui` to ensure functionality.

5. **Update the Cog**:
   - Update the cog when new changes are pushed to the repository:
     ```
     [m]cog update SpinnerModeration
     ```

6. **Remove the Cog or Repository** (if needed):
   - Unload and delete the cog:
     ```
     [m]cog unload SpinnerModeration
     [m]cog delete SpinnerModeration
     ```
   - Remove the repository:
     ```
     [m]repo remove spinner-cogs
     ```

---

## Configuration

### Config Structure
The cog uses Redbot’s Config API with the identifier `0xDEAD2025`.

#### Global Config
- `version` (str): Cog version for migration checks (default: `"1.0"`).

#### Guild Config
| Key                  | Type         | Default                                                                 | Description                                      |
|----------------------|--------------|-------------------------------------------------------------------------|--------------------------------------------------|
| `mod_roles`          | List[int]    | `[]`                                                                    | Moderator role IDs.                               |
| `admin_roles`        | List[int]    | `[]`                                                                    | Administrator role IDs.                           |
| `modlog_channel`     | int/None     | `None`                                                                  | Channel ID for mod logs.                          |
| `dm_notify`          | bool         | `False`                                                                 | Enable DM notifications for users.                |
| `dm_message_template`| str          | `"You have received a {action} in {guild}.\nReason: {reason}\nDuration: {duration}\nTotal Points: {points}"` | DM template with placeholders.                   |
| `warn_reasons`       | Dict[str, Dict] | `{}`                                                                 | Custom warn reasons with points, duration, permanence. |
| `punishments`        | List[Dict]   | `[]`                                                                    | Point-based auto-punishment thresholds.           |
| `mute_role`          | int/None     | `None`                                                                  | ID of the mute role.                             |
| `sync_red_perms`     | bool         | `False`                                                                 | Sync with Redbot’s mod/admin permissions.         |

#### User Config (Per Guild)
| Key        | Type       | Default | Description                          |
|------------|------------|---------|--------------------------------------|
| `warnings` | List[Dict] | `[]`    | List of warnings for the user.       |

#### Warning Entry Structure
```json
{
    "reason": str,
    "points": int,
    "permanent": bool,
    "expires": Optional[int],  // Unix timestamp
    "moderator": int,
    "date": int  // Unix timestamp
}
```

### Setup Commands
Run these commands to configure the cog:
- `[p]modset addmodrole <role>`: Add a moderator role.
- `[p]modset addadminrole <role>`: Add an admin role.
- `[p]modset setlogchannel <channel>`: Set the modlog channel.
- `[p]modset toggledm`: Enable/disable DM notifications.
- `[p]modset setdmtemplate`: Edit the DM template via a modal.
- `[p]modset muterole [role]`: Set or create a mute role.
- `[p]modset syncperms`: Toggle Redbot permission sync.

---

## Commands

### Warn Commands
| Command                            | Description                                   | Example                        |
|------------------------------------|-----------------------------------------------|--------------------------------|
| `[p]warn <member> <reason>`        | Issue a warning with points and check punishments. | `[p]warn @User Spam`          |
| `[p]warnings <member>`             | Display active/expired warnings.              | `[p]warnings @User`           |
| `[p]clearwarns <member>`           | Clear warnings (with confirmation).           | `[p]clearwarns @User`         |
| `[p]reason add <name> <points> [duration] [--perm]` | Add/edit a warn reason.            | `[p]reason add spam 5 1d`     |
| `[p]reason remove <name>`          | Remove a warn reason.                         | `[p]reason remove spam`       |
| `[p]reason list`                   | List all warn reasons.                        | `[p]reason list`              |

### Punishment Commands
| Command                            | Description                                   | Example                        |
|------------------------------------|-----------------------------------------------|--------------------------------|
| `[p]punishments list`              | List configured punishments.                  | `[p]punishments list`         |
| `[p]punishments add <points> <action> [duration]` | Add/update a punishment threshold. | `[p]punishments add 10 mute 1h` |
| `[p]punishments remove <points>`   | Remove a punishment threshold.                | `[p]punishments remove 10`    |
| `[p]punishments gui`               | Open an interactive punishment setup UI.      | `[p]punishments gui`          |

### Moderation Commands
| Command                            | Description                                   | Example                        |
|------------------------------------|-----------------------------------------------|--------------------------------|
| `[p]mute <member> [duration] [reason]` | Mute a member with role/timeout.         | `[p]mute @User 1h Spam`       |
| `[p]unmute <member>`               | Unmute a member.                              | `[p]unmute @User`             |
| `[p]kick <member> [reason]`        | Kick a member.                                | `[p]kick @User Disruption`    |
| `[p]ban <member> [reason]`         | Ban a member.                                 | `[p]ban @User Rule break`     |
| `[p]unban <user_id or name#discrim>` | Unban a user.                              | `[p]unban 1234567890`        |
| `[p]purge <amount>`                | Purge messages in the channel.                | `[p]purge 50`                 |

### Setup Commands
| Command                            | Description                                   | Example                        |
|------------------------------------|-----------------------------------------------|--------------------------------|
| `[p]modset addmodrole <role>`      | Add a moderator role.                         | `[p]modset addmodrole @Mod`   |
| `[p]modset removemodrole <role>`   | Remove a moderator role.                      | `[p]modset removemodrole @Mod`|
| `[p]modset addadminrole <role>`    | Add an admin role.                            | `[p]modset addadminrole @Admin`|
| `[p]modset removeadminrole <role>` | Remove an admin role.                         | `[p]modset removeadminrole @Admin`|
| `[p]modset setlogchannel <channel>`| Set the modlog channel.                       | `[p]modset setlogchannel #logs`|
| `[p]modset toggledm`               | Toggle DM notifications.                      | `[p]modset toggledm`          |
| `[p]modset setdmtemplate`          | Edit DM template via modal.                   | `[p]modset setdmtemplate`     |
| `[p]modset muterole [role]`        | Set or create a mute role.                    | `[p]modset muterole @Muted`   |
| `[p]modset syncperms`              | Toggle Redbot permission sync.                | `[p]modset syncperms`         |

---

## Usage Examples

### Setting Up
1. Add a mod role and log channel:
   ```
   [p]modset addmodrole @Moderator
   [p]modset setlogchannel #mod-logs
   ```

2. Enable DM notifications and customize the template:
   ```
   [p]modset toggledm
   [p]modset setdmtemplate
   ```

3. Set up a mute role:
   ```
   [p]modset muterole  // Creates a new "Muted" role
   ```

### Configuring Punishments
1. Add a warn reason:
   ```
   [p]reason add spam 5 1d  // 5 points, expires in 1 day
   ```

2. Set up auto-punishments via GUI:
   ```
   [p]punishments gui
   ```
   - Click "Add/Edit" to open a modal, enter `10` points, `mute` action, `1h` duration.
   - Click "Remove" to delete a threshold.

3. Add a punishment manually:
   ```
   [p]punishments add 20 ban
   ```

### Moderating
1. Warn a user:
   ```
   [p]warn @User spam
   ```
   - If "spam" is configured, assigns 5 points and logs the action.
   - Checks for auto-punishments (e.g., mute at 10 points).

2. Mute a user:
   ```
   [p]mute @User 30m Disruptive behavior
   ```

3. View warnings:
   ```
   [p]warnings @User
   ```

4. Purge messages:
   ```
   [p]purge 100
   ```

---

## Development

### File Structure
- **`spinnerMod.py`**: Main cog file with all logic and commands.
- **`__init__.py`**: Cog setup file:
  ```python
  from .spinnerMod import SpinnerModeration

  def setup(bot):
      bot.add_cog(SpinnerModeration(bot))
  ```
- **`info.json`**: Metadata for Redbot:
  ```json
  {
      "author": ["Elijah Partney"],
      "install_msg": "Thank you for installing SpinnerModeration! Use `[p]help SpinnerModeration` to get started.",
      "name": "SpinnerModeration",
      "short": "Advanced modular moderation system with point-based warns, logging, and GUI config.",
      "description": "A powerful moderation cog featuring warnings, point thresholds, expiring warns, automated punishments, role-based mutes, DM notifications, and Discord-interaction-based configuration tools.",
      "requirements": [],
      "tags": ["moderation", "utility", "logging", "admin"],
      "type": "COG"
  }
  ```

### Extending the Cog
- **Localization**: Add `_()` from `redbot.core.i18n` for translatable strings.
- **New Punishments**: Extend `apply_auto_punishment` to support custom actions (e.g., role removal).
- **GUI Expansion**: Add buttons/modals to `PunishmentSetupView` for managing mod roles or log channels.
- **Audit Log Integration**: Add methods to fetch Discord audit logs for enhanced logging.

### Debugging
- Check logs with `logging.getLogger("red.spinnerModeration")`.
- Common issues:
  - **Missing Permissions**: Ensure the bot has required permissions.
  - **Config Errors**: Verify modlog channel and mute role exist.
  - **DM Failures**: Users may have DMs disabled, handled silently.

---

## FAQ

**Q: Why isn’t the modlog channel receiving logs?**
- Ensure `[p]modset setlogchannel` is set to a valid channel and the bot has `send_messages` permission.

**Q: How do I make warnings permanent?**
- Use `[p]reason add <name> <points> --perm` to create a permanent reason, or omit duration.

**Q: Can I use this with slash commands?**
- Yes, all commands are hybrid-ready (`commands.hybrid_command`). Run `[p]slash enable` on Redbot to enable slash commands.

**Q: Why does `[p]mute` fail?**
- Check if a mute role is set with `[p]modset muterole` and verify bot permissions (`manage_roles`, `moderate_members`).

---

## Contributing
Contributions are welcome! Please:
1. Fork the `Spinner-Cogs` repository.
2. Create a feature branch (`git checkout -b feature/new-feature`).
3. Submit a pull request with detailed changes.

---

## License
This cog is released under the [MIT License](https://opensource.org/licenses/MIT).

---

## Contact
- **Author**: Elijah Partney
- **Repository**: [Spinner-Cogs](https://github.com/FreeSpinner09/Spinner-Cogs)
- **Issues**: Report bugs or request features on the repository’s issue tracker.

Thank you for using **SpinnerModeration**! 🚀