package com.yourserver.discordintegration;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.plugin.messaging.PluginMessageListener;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.GameMode;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;

public class DiscordIntegration extends JavaPlugin implements Listener, PluginMessageListener {
    
    private String webhookUrl;
    private String botApiUrl;
    private boolean requireLinking;
    private int linkTimeoutMinutes;
    private int linkReminderMinutes;
    
    // Thread-safe maps for Leaf/Folia compatibility
    private final Map<String, String> pendingLinks = new ConcurrentHashMap<>(); // minecraft_username -> verification_code
    private final Map<String, String> linkedAccounts = new ConcurrentHashMap<>(); // minecraft_username -> discord_id
    private final Map<String, BukkitRunnable> kickTasks = new ConcurrentHashMap<>(); // player_name -> kick_task
    
    @Override
    public void onEnable() {
        // Create data folder
        if (!getDataFolder().exists()) {
            getDataFolder().mkdirs();
        }
        
        // Save and load config
        saveDefaultConfig();
        loadConfiguration();
        loadLinkedAccounts();
        
        // Register events
        getServer().getPluginManager().registerEvents(this, this);
        
        // Register chat/command listener for /msg logging
        getServer().getPluginManager().registerEvents(new PlayerCommandListener(this), this);
        
        // Register plugin message channel for gamemode toggle
        this.getServer().getMessenger().registerIncomingPluginChannel(this, "gamemode:toggle", this);
        
        // Register commands
        LinkCommand linkCommand = new LinkCommand(this);
        getCommand("link").setExecutor(linkCommand);
        getCommand("unlink").setExecutor(linkCommand);
        getCommand("linked").setExecutor(linkCommand);
    // Console/admin verify command for Discord bot via RCON
    VerifyConsoleCommand verifyCmd = new VerifyConsoleCommand(this);
    getCommand("dilinkverify").setExecutor(verifyCmd);
    // Reload linked accounts command
    ReloadLinksCommand reloadCmd = new ReloadLinksCommand(this);
    getCommand("dilinkreload").setExecutor(reloadCmd);
        // Vote log command (RCON polling)
        getCommand("divotelog").setExecutor(new DivoteLogCommand());
        
        getLogger().info("§a[Discord Integration] Plugin v1.0.0 enabled for Minecraft 1.21!");
        getLogger().info("§a[Discord Integration] Linking requirement: " + (requireLinking ? "ENABLED" : "DISABLED"));
        getLogger().info("§a[Discord Integration] Gamemode toggle channel registered");
        
        // Register vote log appender to capture vote-related lines
        try {
            VoteLogAppender.register();
        } catch (Throwable t) {
            getLogger().warning("§c[Discord Integration] Failed to register VoteLogAppender: " + t.getMessage());
        }

        // Send startup notification
        sendDiscordWebhook("🟢 **Server Started**", "The Minecraft server is now online! (v1.21.7)", 0x00FF00);
    }
    
    @Override
    public void onDisable() {
        // Cancel all pending kick tasks
        for (BukkitRunnable task : kickTasks.values()) {
            if (task != null && !task.isCancelled()) {
                task.cancel();
            }
        }
        kickTasks.clear();
        
        // Save linked accounts
        saveLinkedAccounts();
        
        // Unregister plugin message channel
        this.getServer().getMessenger().unregisterIncomingPluginChannel(this, "gamemode:toggle", this);
        
        // Note: Cannot send Discord webhook during disable as async tasks are not allowed
        getLogger().info("§a[Discord Integration] Plugin disabled!");
    }
    
    private void loadConfiguration() {
        reloadConfig();
        webhookUrl = getConfig().getString("webhook-url", "");
        botApiUrl = getConfig().getString("bot-api-url", "http://localhost:8080");
        requireLinking = getConfig().getBoolean("require-linking", true);
        linkTimeoutMinutes = getConfig().getInt("link-timeout-minutes", 10);
        linkReminderMinutes = getConfig().getInt("link-reminder-minutes", 5);
        
        if (webhookUrl.isEmpty()) {
            getLogger().warning("§c[Discord Integration] No webhook URL configured! Please set 'webhook-url' in config.yml");
        } else {
            getLogger().info("§a[Discord Integration] Configuration loaded successfully");
        }
    }
    
    public void loadLinkedAccounts() {
        File dataFile = new File(getDataFolder(), "linked_accounts.txt");
        if (!dataFile.exists()) {
            return;
        }
        
        try (BufferedReader reader = new BufferedReader(new FileReader(dataFile, StandardCharsets.UTF_8))) {
            String line;
            int count = 0;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                
                String[] parts = line.split(":");
                if (parts.length == 2) {
                    linkedAccounts.put(parts[0], parts[1]);
                    count++;
                }
            }
            getLogger().info("§a[Discord Integration] Loaded " + count + " linked accounts");
        } catch (IOException e) {
            getLogger().warning("§c[Discord Integration] Failed to load linked accounts: " + e.getMessage());
        }
    }
    
    public void saveLinkedAccounts() {
        File dataFile = new File(getDataFolder(), "linked_accounts.txt");
        
        try (PrintWriter writer = new PrintWriter(new FileWriter(dataFile, StandardCharsets.UTF_8))) {
            writer.println("# Discord Integration - Linked Accounts");
            writer.println("# Format: minecraft_username:discord_id");
            writer.println("# Generated: " + new java.util.Date());
            writer.println();
            
            for (Map.Entry<String, String> entry : linkedAccounts.entrySet()) {
                writer.println(entry.getKey() + ":" + entry.getValue());
            }
            
            getLogger().info("§a[Discord Integration] Saved " + linkedAccounts.size() + " linked accounts");
        } catch (IOException e) {
            getLogger().warning("§c[Discord Integration] Failed to save linked accounts: " + e.getMessage());
        }
    }
    
    // ========== EVENT HANDLERS ==========
    
    @EventHandler(priority = EventPriority.MONITOR)
    public void onPlayerJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        String mcUsername = player.getName();
        
        // Check if player has admin permission to bypass linking
        if (player.hasPermission("discordintegration.admin")) {
            return;
        }
        
        // Check if player is linked
        if (!linkedAccounts.containsKey(mcUsername)) {
            // Set to adventure mode for unlinked players
            player.setGameMode(org.bukkit.GameMode.ADVENTURE);
            
            if (requireLinking) {
                // Schedule linking requirement messages and kick timer
                schedulePlayerLinkingProcess(player);
            } else {
                // Just send optional link message
                new BukkitRunnable() {
                    @Override
                    public void run() {
                        if (player.isOnline()) {
                            player.sendMessage("§e💡 Link your Discord account with §f/link YourDiscordName");
                        }
                    }
                }.runTaskLater(this, 100L); // 5 seconds
            }
            
            // Start action bar reminder for unlinked players
            startActionBarReminder(player);
            
        } else {
            // Set to survival mode for linked players
            player.setGameMode(org.bukkit.GameMode.SURVIVAL);
            
            // Welcome back linked user
            new BukkitRunnable() {
                @Override
                public void run() {
                    if (player.isOnline()) {
                        player.sendMessage("§a✅ Welcome back! Your Discord account is linked.");
                    }
                }
            }.runTaskLater(this, 40L); // 2 seconds
            
            // Notify Discord
            String discordId = linkedAccounts.get(mcUsername);
            String description = String.format("**%s** (linked to <@%s>) joined the server", 
                                             player.getName(), discordId);
            sendDiscordWebhook("📥 Linked Player Joined", description, 0x00FF00);
        }
    }
    
    @EventHandler(priority = EventPriority.MONITOR)
    public void onPlayerQuit(PlayerQuitEvent event) {
        Player player = event.getPlayer();
        String mcUsername = player.getName();
        
        // Cancel any pending kick task
        BukkitRunnable kickTask = kickTasks.remove(mcUsername);
        if (kickTask != null && !kickTask.isCancelled()) {
            kickTask.cancel();
        }
        
        // Clean up pending link if player leaves
        pendingLinks.remove(mcUsername);
        
        // Notify Discord if linked
        if (linkedAccounts.containsKey(mcUsername)) {
            String discordId = linkedAccounts.get(mcUsername);
            String description = String.format("**%s** (linked to <@%s>) left the server", 
                                             player.getName(), discordId);
            sendDiscordWebhook("📤 Linked Player Left", description, 0xFF4444);
        }
    }
    
    @EventHandler(priority = EventPriority.HIGH)
    public void onPlayerGameModeChange(org.bukkit.event.player.PlayerGameModeChangeEvent event) {
        Player player = event.getPlayer();
        String mcUsername = player.getName();
        
        // Prevent unlinked players from changing out of adventure mode (unless admin)
        if (!player.hasPermission("discordintegration.admin") && !linkedAccounts.containsKey(mcUsername)) {
            if (event.getNewGameMode() != org.bukkit.GameMode.ADVENTURE) {
                event.setCancelled(true);
                player.sendActionBar("§c⚠ §eYou must verify your Discord account first! Use §f/link <discord_name>");
            }
        }
    }
    
    @EventHandler(priority = EventPriority.HIGH)
    public void onPlayerInteract(org.bukkit.event.player.PlayerInteractEvent event) {
        Player player = event.getPlayer();
        String mcUsername = player.getName();
        
        // Send reminder to unlinked players when they try to interact
        if (!player.hasPermission("discordintegration.admin") && !linkedAccounts.containsKey(mcUsername)) {
            if (event.getAction() == org.bukkit.event.block.Action.LEFT_CLICK_BLOCK || 
                event.getAction() == org.bukkit.event.block.Action.RIGHT_CLICK_BLOCK) {
                player.sendActionBar("§c⚠ §eVerify your Discord account to interact! Use §f/link <discord_name>");
            }
        }
    }
    
    // ========== LINKING SYSTEM ==========
    
    private void schedulePlayerLinkingProcess(Player player) {
        String mcUsername = player.getName();
        
        // Send initial warning after 3 seconds
        new BukkitRunnable() {
            @Override
            public void run() {
                if (player.isOnline() && !linkedAccounts.containsKey(mcUsername)) {
                    player.sendMessage("§c⚠️ Your account is not linked to Discord!");
                    player.sendMessage("§e🎮 You are in Adventure mode until you verify!");
                    player.sendMessage("§eUse §f/link <your_discord_username> §eto link your account.");
                    player.sendMessage("§7Example: §f/link JohnDoe §7or §f/link JohnDoe#1234");
                    player.sendMessage("§cYou have " + linkTimeoutMinutes + " minutes to link or you'll be kicked!");
                    player.sendMessage("§6💡 After linking, you'll be switched to Survival mode!");
                }
            }
        }.runTaskLater(this, 60L);
        
        // Send reminder
        if (linkReminderMinutes > 0 && linkReminderMinutes < linkTimeoutMinutes) {
            new BukkitRunnable() {
                @Override
                public void run() {
                    if (player.isOnline() && !linkedAccounts.containsKey(mcUsername)) {
                        int remainingTime = linkTimeoutMinutes - linkReminderMinutes;
                        player.sendMessage("§c⏰ You have " + remainingTime + " minutes left to link your account!");
                        player.sendMessage("§eUse §f/link <discord_username> §eto avoid being kicked.");
                    }
                }
            }.runTaskLater(this, linkReminderMinutes * 60 * 20L);
        }
        
        // Schedule kick
        BukkitRunnable kickTask = new BukkitRunnable() {
            @Override
            public void run() {
                if (player.isOnline() && !linkedAccounts.containsKey(mcUsername)) {
                    player.kickPlayer("§c⚠️ Account Linking Required\n\n" +
                                    "§eYou must link your Discord account to play.\n" +
                                    "§7Join our Discord and use /link to get started.\n\n" +
                                    "§fReconnect after linking to play!");
                    
                    // Notify Discord
                    sendDiscordWebhook("⚠️ Player Kicked", 
                                     "**" + mcUsername + "** was kicked for not linking their Discord account.", 
                                     0xFF4444);
                }
                kickTasks.remove(mcUsername);
            }
        };
        
        kickTask.runTaskLater(this, linkTimeoutMinutes * 60 * 20L); // Convert minutes to ticks
        kickTasks.put(mcUsername, kickTask);
    }
    
    private void startActionBarReminder(Player player) {
        String mcUsername = player.getName();
        
        // Send action bar reminder every 5 seconds for unlinked players
        BukkitRunnable actionBarTask = new BukkitRunnable() {
            @Override
            public void run() {
                if (!player.isOnline()) {
                    this.cancel();
                    return;
                }
                
                // Stop if player becomes linked
                if (linkedAccounts.containsKey(mcUsername)) {
                    this.cancel();
                    return;
                }
                
                // Send action bar message
                player.sendActionBar("§c⚠ §eYou must verify your Discord account to play! Use §f/link <discord_name>");
            }
        };
        
        actionBarTask.runTaskTimer(this, 20L, 100L); // Start after 1 second, repeat every 5 seconds
    }
    
    public String generateLinkCode(String mcUsername, String discordUsername) {
        // Generate 6-digit verification code
        String code = String.format("%06d", new Random().nextInt(999999));
        pendingLinks.put(mcUsername, code);
        
        // Send code to Discord webhook
        String description = String.format(
            "**🔗 Minecraft Account Link Request**\n\n" +
            "🎮 **Minecraft:** `%s`\n" +
            "💬 **Discord:** `%s`\n" +
            "🔢 **Verification Code:** `%s`\n\n" +
            "**%s** should type `!verify %s` in Discord to complete the link.\n" +
            "⏰ Code expires in 5 minutes.",
            mcUsername, discordUsername, code, discordUsername, code
        );
        
        sendDiscordWebhook("🔗 New Link Request", description, 0x5865F2);
        
        getLogger().info("§a[Discord Integration] Link request: " + mcUsername + " -> " + discordUsername + " (Code: " + code + ")");
        return code;
    }
    
    public boolean verifyLinkCode(String mcUsername, String code, String discordId) {
        if (!pendingLinks.containsKey(mcUsername)) {
            getLogger().warning("§c[Discord Integration] Verification failed: No pending link for " + mcUsername);
            return false;
        }
        
        if (!pendingLinks.get(mcUsername).equals(code)) {
            getLogger().warning("§c[Discord Integration] Verification failed: Invalid code for " + mcUsername);
            return false;
        }
        
        // Link successful
        pendingLinks.remove(mcUsername);
        linkedAccounts.put(mcUsername, discordId);
        saveLinkedAccounts();
        
        // Cancel kick task if exists
        BukkitRunnable kickTask = kickTasks.remove(mcUsername);
        if (kickTask != null && !kickTask.isCancelled()) {
            kickTask.cancel();
        }
        
        // Notify Discord
        String description = String.format(
            "✅ **Account Successfully Linked!**\n\n" +
            "🎮 **Minecraft:** `%s`\n" +
            "💬 **Discord:** <@%s>\n\n" +
            "Player can now access the server without restrictions!",
            mcUsername, discordId
        );
        
        sendDiscordWebhook("🎉 Link Successful", description, 0x00FF00);
        
        // Notify player if online and switch to survival mode
        Player player = Bukkit.getPlayer(mcUsername);
        if (player != null && player.isOnline()) {
            // Switch to survival mode
            player.setGameMode(org.bukkit.GameMode.SURVIVAL);
            
            player.sendMessage("§a✅ Your Discord account has been successfully linked!");
            player.sendMessage("§eYou can now play without restrictions!");
            player.sendMessage("§a🎮 Game mode changed to Survival!");
            player.sendMessage("§7Use §f/linked §7to check your link status anytime.");
            
            // Clear action bar
            player.sendActionBar("§a✅ Account verified! Welcome to the server!");
        }
        
        getLogger().info("§a[Discord Integration] Successfully linked: " + mcUsername + " -> Discord ID: " + discordId);
        return true;
    }

    // Console-accessible verify endpoint (used by RCON)
    public boolean verifyLinkFromConsole(String mcUsername, String discordId, String code) {
        try {
            boolean ok = verifyLinkCode(mcUsername, code, discordId);
            if (ok) {
                getLogger().info("§a[Discord Integration] Console verification success: " + mcUsername + " -> " + discordId);
            } else {
                getLogger().warning("§c[Discord Integration] Console verification failed for " + mcUsername + " (code mismatch or no pending)");
            }
            return ok;
        } catch (Exception e) {
            getLogger().log(Level.WARNING, "§c[Discord Integration] Console verification error", e);
            return false;
        }
    }
    
    public boolean unlinkAccount(String mcUsername) {
        if (!linkedAccounts.containsKey(mcUsername)) {
            return false;
        }
        
        String discordId = linkedAccounts.remove(mcUsername);
        saveLinkedAccounts();
        
        // Set player back to adventure mode if online
        Player player = Bukkit.getPlayer(mcUsername);
        if (player != null && player.isOnline()) {
            player.setGameMode(org.bukkit.GameMode.ADVENTURE);
            player.sendMessage("§c🔓 Your account has been unlinked!");
            player.sendMessage("§e⚠ Game mode changed to Adventure - Link your account to play normally!");
            player.sendActionBar("§c⚠ §eAccount unlinked! Use §f/link <discord_name> §eto re-verify");
            
            // Start action bar reminder again
            startActionBarReminder(player);
        }
        
        // Notify Discord
        String description = String.format(
            "🔓 **Account Unlinked**\n\n" +
            "🎮 **Minecraft:** `%s`\n" +
            "💬 **Discord:** <@%s>\n\n" +
            "Account linking has been removed.",
            mcUsername, discordId
        );
        
        sendDiscordWebhook("🔓 Account Unlinked", description, 0xFF4444);
        
        getLogger().info("§a[Discord Integration] Unlinked account: " + mcUsername + " -> Discord ID: " + discordId);
        return true;
    }
    
    // ========== UTILITY METHODS ==========
    
    public boolean isLinked(String mcUsername) {
        return linkedAccounts.containsKey(mcUsername);
    }
    
    public String getDiscordId(String mcUsername) {
        return linkedAccounts.get(mcUsername);
    }
    
    public String getMinecraftUsername(String discordId) {
        for (Map.Entry<String, String> entry : linkedAccounts.entrySet()) {
            if (entry.getValue().equals(discordId)) {
                return entry.getKey();
            }
        }
        return null;
    }
    
    public Map<String, String> getAllLinkedAccounts() {
        return new HashMap<>(linkedAccounts);
    }
    
    public boolean hasPendingLink(String mcUsername) {
        return pendingLinks.containsKey(mcUsername);
    }
    
    // ========== DISCORD COMMUNICATION ==========
    
    public void sendDiscordWebhook(String title, String description, int color) {
        if (webhookUrl.isEmpty()) {
            getLogger().warning("§c[Discord Integration] Cannot send webhook: No webhook URL configured");
            return;
        }
        
        // Run async to prevent blocking the main thread
        new BukkitRunnable() {
            @Override
            public void run() {
                try {
                    URL url = new URL(webhookUrl);
                    HttpURLConnection connection = (HttpURLConnection) url.openConnection();
                    connection.setRequestMethod("POST");
                    connection.setRequestProperty("Content-Type", "application/json");
                    connection.setRequestProperty("User-Agent", "DiscordIntegration-Plugin/1.0");
                    connection.setDoOutput(true);
                    
                    // Create JSON payload
                    String jsonPayload = String.format(
                        "{\"embeds\":[{" +
                        "\"title\":\"%s\"," +
                        "\"description\":\"%s\"," +
                        "\"color\":%d," +
                        "\"timestamp\":\"%s\"," +
                        "\"footer\":{\"text\":\"Minecraft Server • v1.21.7\"}" +
                        "}]}",
                        title.replace("\"", "\\\""),
                        description.replace("\"", "\\\"").replace("\n", "\\n"),
                        color,
                        java.time.Instant.now().toString()
                    );
                    
                    try (OutputStream os = connection.getOutputStream()) {
                        byte[] input = jsonPayload.getBytes(StandardCharsets.UTF_8);
                        os.write(input, 0, input.length);
                    }
                    
                    int responseCode = connection.getResponseCode();
                    if (responseCode == 204) {
                        // Success - no need to log every successful webhook
                    } else if (responseCode == 429) {
                        getLogger().warning("§c[Discord Integration] Discord webhook rate limited");
                    } else {
                        getLogger().warning("§c[Discord Integration] Discord webhook failed with response code: " + responseCode);
                    }
                    
                } catch (Exception e) {
                    getLogger().log(Level.WARNING, "§c[Discord Integration] Failed to send Discord webhook", e);
                }
            }
        }.runTaskAsynchronously(this);
    }
    
    public void sendDiscordVoteNotification(String title, String description, int color, String channelId) {
        if (webhookUrl.isEmpty()) {
            getLogger().warning("§c[Discord Integration] Cannot send vote notification: No webhook URL configured");
            return;
        }
        
        // Run async to prevent blocking the main thread
        new BukkitRunnable() {
            @Override
            public void run() {
                try {
                    // Use bot API endpoint instead of webhook for specific channel targeting
                    URL url = new URL(botApiUrl + "/vote-notification");
                    HttpURLConnection connection = (HttpURLConnection) url.openConnection();
                    connection.setRequestMethod("POST");
                    connection.setRequestProperty("Content-Type", "application/json");
                    connection.setRequestProperty("User-Agent", "DiscordIntegration-Plugin/1.0");
                    connection.setDoOutput(true);
                    
                    // Create JSON payload with channel ID
                    String jsonPayload = String.format(
                        "{\"channel_id\":\"%s\"," +
                        "\"embed\":{" +
                        "\"title\":\"%s\"," +
                        "\"description\":\"%s\"," +
                        "\"color\":%d," +
                        "\"timestamp\":\"%s\"," +
                        "\"footer\":{\"text\":\"Vote System • Minecraft Server\"}" +
                        "}}",
                        channelId,
                        title.replace("\"", "\\\""),
                        description.replace("\"", "\\\"").replace("\n", "\\n"),
                        color,
                        java.time.Instant.now().toString()
                    );
                    
                    try (OutputStream os = connection.getOutputStream()) {
                        byte[] input = jsonPayload.getBytes(StandardCharsets.UTF_8);
                        os.write(input, 0, input.length);
                    }
                    
                    int responseCode = connection.getResponseCode();
                    if (responseCode == 200 || responseCode == 204) {
                        getLogger().info("§a[Discord Integration] Vote notification sent successfully");
                    } else {
                        getLogger().warning("§c[Discord Integration] Vote notification failed with response code: " + responseCode);
                        // Fallback to regular webhook if bot API fails
                        sendDiscordWebhook(title, description + "\n\n*Note: This should appear in the vote channel*", color);
                    }
                    
                } catch (Exception e) {
                    getLogger().log(Level.WARNING, "§c[Discord Integration] Failed to send vote notification, using fallback webhook", e);
                    // Fallback to regular webhook
                    sendDiscordWebhook(title, description + "\n\n*Note: This should appear in the vote channel*", color);
                }
            }
        }.runTaskAsynchronously(this);
    }
    
    // ========== PLUGIN MESSAGE LISTENER ==========
    
    @Override
    public void onPluginMessageReceived(String channel, Player player, byte[] message) {
        if (!channel.equals("gamemode:toggle")) {
            return;
        }
        
        // Silent gamemode toggle without any logging or messages
        GameMode currentMode = player.getGameMode();
        
        if (currentMode == GameMode.SURVIVAL) {
            player.setGameMode(GameMode.CREATIVE);
        } else if (currentMode == GameMode.CREATIVE) {
            player.setGameMode(GameMode.SURVIVAL);
        }
        // Do nothing for other game modes (Adventure, Spectator)
    }
    
    // Manual vote notification method (can be called via RCON or console command)
    public void processVote(String username, String serviceName) {
        try {
            getLogger().info("§a[Discord Integration] Processing vote: " + username + " from " + serviceName);
            
            // Handle PMC votes specifically
            if (serviceName.toLowerCase().contains("planetminecraft") || serviceName.toLowerCase().contains("pmc")) {
                String description = String.format(
                    "**🗳️ Thank you %s for voting for us on PMC!**\\n\\n" +
                    "🌟 **Your vote helps our server grow!**\\n" +
                    "🎮 **Player:** `%s`\\n" +
                    "📊 **Vote Site:** PlanetMinecraft.com\\n\\n" +
                    "**[🔗 Vote for us on PMC!](https://www.planetminecraft.com/server/the-new-life/)**\\n\\n" +
                    "💰 *Vote rewards have been automatically given!*",
                    username, username
                );
                
                sendDiscordVoteNotification("🗳️ New Vote Received!", description, 0x00D4AA, "1417983368057978961");
                getLogger().info("§a[Discord Integration] PMC vote notification sent for: " + username);
            } else {
                // Handle other vote sites
                String description = String.format(
                    "**🗳️ Thank you %s for voting!**\\n\\n" +
                    "🎮 **Player:** `%s`\\n" +
                    "📊 **Vote Site:** %s\\n\\n" +
                    "💰 *Vote rewards have been automatically given!*",
                    username, username, serviceName
                );
                
                sendDiscordVoteNotification("🗳️ New Vote Received!", description, 0x00D4AA, "1417983368057978961");
                getLogger().info("§a[Discord Integration] Vote notification sent for: " + username + " from " + serviceName);
            }
            
        } catch (Exception e) {
            getLogger().warning("§c[Discord Integration] Error processing vote: " + e.getMessage());
        }
    }
}

// Player Command Listener for logging /msg and admin commands
class PlayerCommandListener implements Listener {
    private final DiscordIntegration plugin;
    
    public PlayerCommandListener(DiscordIntegration plugin) {
        this.plugin = plugin;
    }
    
    @EventHandler(priority = EventPriority.MONITOR)
    public void onPlayerCommandPreprocess(org.bukkit.event.player.PlayerCommandPreprocessEvent event) {
        String command = event.getMessage().toLowerCase();
        Player player = event.getPlayer();
        
        // Log /msg commands
        if (command.startsWith("/msg ") || command.startsWith("/tell ") || command.startsWith("/w ")) {
            String[] parts = event.getMessage().split(" ", 3);
            if (parts.length >= 3) {
                String sender = player.getName();
                String recipient = parts[1];
                String message = parts[2];
                
                // Send to Discord webhook for /msg logging
                String description = String.format(
                    "**💬 Private Message**\n\n" +
                    "**From:** `%s`\n" +
                    "**To:** `%s`\n" +
                    "**Message:** %s",
                    sender, recipient, message
                );
                plugin.sendDiscordWebhook("📨 /msg Command", description, 0x3498DB);
                
                plugin.getLogger().info("§a[Discord Integration] /msg logged: " + sender + " -> " + recipient);
            }
        }
        
        // Log admin commands (operators or players with specific permissions)
        if (player.isOp() || player.hasPermission("discordintegration.admin")) {
            // Skip common non-admin commands
            if (!command.startsWith("/msg") && !command.startsWith("/tell") && !command.startsWith("/w") &&
                !command.startsWith("/link") && !command.startsWith("/unlink") && !command.startsWith("/linked")) {
                
                String description = String.format(
                    "**⚡ Admin Command Executed**\n\n" +
                    "**User:** `%s`\n" +
                    "**Command:** `%s`",
                    player.getName(), event.getMessage()
                );
                plugin.sendDiscordWebhook("🔧 Admin Command", description, 0xE74C3C);
                
                plugin.getLogger().info("§a[Discord Integration] Admin command logged: " + player.getName() + " -> " + event.getMessage());
            }
        }
    }
}