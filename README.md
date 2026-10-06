# Configurations

Installs Vim, Git, tmux, rsync, htop, and personal Bash/Vim/tmux settings.
Supports Debian/Ubuntu/Pi OS and Fedora. Run as your normal user:

```bash
bash setup.sh                  # Install tools and settings
bash setup.sh dotfiles         # Apply settings only
bash setup.sh export           # Copy managed settings back into this checkout
bash setup.sh --dry-run        # Preview without changes
```

Without a checkout (requires curl):

```bash
curl -fL https://raw.githubusercontent.com/RichSeibert/configurations/main/setup.sh -o /tmp/rich-setup.sh && bash /tmp/rich-setup.sh
```

Existing files are backed up under `~/.local/state/configurations/backups/`
(`$XDG_STATE_HOME` is respected); the OS Bash startup file is preserved.
Open a new shell afterward. SSH keys and Git identity are unchanged.
