# Systemd Service Fixes

## Issue 1: Failed to determine supplementary groups

If you encounter the error:
```
bybit-mr-bot.service: Failed to determine supplementary groups: Operation not permitted
```

This happens when the service file includes `User=` directive for a user-level systemd service.

## Issue 2: ModuleNotFoundError: No module named 'src'

If you encounter the error:
```
ModuleNotFoundError: No module named 'src'
```

This was happening because Python couldn't find the `src` module. **This has been fixed** by adding automatic path setup in all scripts. The scripts now automatically add the project root to sys.path, so they work regardless of PYTHONPATH settings.

## Quick Fix

1. Stop the service:
   ```bash
   systemctl --user stop bybit-mr-bot
   ```

2. Remove the old service file:
   ```bash
   rm ~/.config/systemd/user/bybit-mr-bot.service
   ```

3. Re-run the installer (only the systemd portion will be recreated):
   ```bash
   ./install.sh
   # When prompted, answer "y" to "Install systemd service?"
   ```

Or manually fix the service file:

1. Edit the service file:
   ```bash
   nano ~/.config/systemd/user/bybit-mr-bot.service
   ```

2. In the `[Service]` section:
   - Remove the `User=` line (for user-level services)

   The `[Service]` section should look like:
   ```ini
   [Service]
   Type=simple
   WorkingDirectory=/home/ubuntu/mean-reversion
   Environment="PATH=/home/ubuntu/mean-reversion/.venv/bin:$PATH"
   EnvironmentFile=/home/ubuntu/mean-reversion/.env
   ExecStart=/home/ubuntu/mean-reversion/.venv/bin/python /home/ubuntu/mean-reversion/scripts/live.py --config /home/ubuntu/mean-reversion/config/config.yaml --paper
   Restart=always
   RestartSec=10
   StandardOutput=journal
   StandardError=journal
   ```

3. Reload and restart:
   ```bash
   systemctl --user daemon-reload
   systemctl --user restart bybit-mr-bot
   systemctl --user status bybit-mr-bot
   ```

The updated installer script (install.sh) now handles both issues correctly:
- User-level services don't include `User=` directive
- Scripts automatically add the project root to sys.path (no PYTHONPATH needed)

