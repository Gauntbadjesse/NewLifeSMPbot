# Minecraft RCON Configuration Guide

## minecraft_config.txt Setup

The `minecraft_config.txt` file has been created with default values. You need to update it with your actual Minecraft server details.

### Current Configuration:
```
MC_HOST=localhost
MC_RCON_PORT=25575
MC_RCON_PASSWORD=your_rcon_password
```

### How to Configure:

1. **MC_HOST**: Your Minecraft server IP address
   - If server is on same machine: `localhost` or `127.0.0.1`
   - If server is on different machine: `192.168.1.100` (example IP)
   - If server is hosted elsewhere: `your.server.domain.com` or IP

2. **MC_RCON_PORT**: RCON port (default is usually 25575)
   - Check your server.properties file for `rcon.port=25575`

3. **MC_RCON_PASSWORD**: Your RCON password
   - Set in server.properties as `rcon.password=your_password_here`
   - Make sure `enable-rcon=true` in server.properties

### Example Configurations:

**Local Server:**
```
MC_HOST=localhost
MC_RCON_PORT=25575
MC_RCON_PASSWORD=mySecretPassword123
```

**Remote Server:**
```
MC_HOST=play.myserver.com
MC_RCON_PORT=25575
MC_RCON_PASSWORD=rconPassword456
```

**Custom Port:**
```
MC_HOST=192.168.1.50
MC_RCON_PORT=25580
MC_RCON_PASSWORD=customPassword789
```

### Minecraft Server Setup:

Make sure your Minecraft server has RCON enabled in `server.properties`:
```properties
enable-rcon=true
rcon.port=25575
rcon.password=your_password_here
```

### Testing RCON:

After configuring, restart your Discord bot. You should see:
- ✅ `RCON connection successful!`
- ❌ `RCON connection failed: [error details]`

### RCON Commands Available:

Once configured, these Discord commands will work:
- `!give <player> <item> [amount]`
- `!tp <player> <target>`
- `!kick <player> [reason]`
- `!whitelist <add|remove> <player>`
- `!say <message>`

### Security Notes:

- Keep your RCON password secure
- Don't share minecraft_config.txt publicly
- Use a strong RCON password
- Consider firewall rules for RCON port

The bot will automatically retry RCON connection if it fails initially.