package com.yourserver.discordintegration;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitRunnable;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;

public class DiscordIntegration extends JavaPlugin implements Listener {
    
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
        
        // Register commands
        LinkCommand linkCommand = new LinkCommand(this);
        getCommand("link").setExecutor(linkCommand);
        getCommand("unlink").setExecutor(linkCommand);
        getCommand("linked").setExecutor(linkCommand);
        
        getLogger().info("Discord Integration Plugin v1.0.0 enabled for Minecraft 1.21!");
        getLogger().info("Linking requirement: " + (requireLinking ? "ENABLED" : "DISABLED"));
        
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
        
        // Send shutdown notification
        sendDiscordWebhook("🔴 **Server Stopped**", "The Minecraft server is now offline.", 0xFF0000);
        getLogger().info("Discord Integration Plugin disabled!");
    }
    
    private void loadConfiguration() {
        reloadConfig();
        webhookUrl = getConfig().getString("webhook-url", "");
        botApiUrl = getConfig().getString("bot-api-url", "http://localhost:8080");
        requireLinking = getConfig().getBoolean("require-linking", true);
        linkTimeoutMinutes = getConfig().getInt("link-timeout-minutes", 10);
        linkReminderMinutes = getConfig().getInt("link-reminder-minutes", 5);
        
        if (webhookUrl.isEmpty()) {
            getLogger().warning("No webhook URL configured! Please set 'webhook-url' in config.yml");
        }
    }
    
    private void loadLinkedAccounts() {
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
            getLogger().info("Loaded " + count + " linked accounts");
        } catch (IOException e) {
            getLogger().log(Level.WARNING, "Failed to load linked accounts", e);
        }
    }
    
    private void saveLinkedAccounts() {
        File dataFile = new File(getDataFolder(), "linked_accounts.txt");
        
        try (PrintWriter writer = new PrintWriter(new FileWriter(dataFile, StandardCharsets.UTF_8))) {
            writer.println("# Discord Integration - Linked Accounts");
            writer.println("# Format: minecraft_username:discord_id");
            writer.println("# Generated: " + new java.util.Date());
            writer.println();
            
            for (Map.Entry<String, String> entry : linkedAccounts.entrySet()) {
                writer.println(entry.getKey() + ":" + entry.getValue());
            }
            
            getLogger().info("Saved " + linkedAccounts.size() + " linked accounts");
        } catch (IOException e) {
            getLogger().log(Level.WARNING, "Failed to save linked accounts", e);
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
        } else {
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
    
    // ========== LINKING SYSTEM ==========
    
    private void schedulePlayerLinkingProcess(Player player) {
        String mcUsername = player.getName();
        
        // Send initial warning after 3 seconds
        new BukkitRunnable() {
            @Override
            public void run() {
                if (player.isOnline() && !linkedAccounts.containsKey(mcUsername)) {
                    player.sendMessage("§c⚠️ Your account is not linked to Discord!");
                    player.sendMessage("§eUse §f/link <your_discord_username> §eto link your account.");
                    player.sendMessage("§7Example: §f/link JohnDoe §7or §f/link JohnDoe#1234");
                    player.sendMessage("§cYou have " + linkTimeoutMinutes + " minutes to link or you'll be kicked!");
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
        
        getLogger().info("Link request: " + mcUsername + " -> " + discordUsername + " (Code: " + code + ")");
        return code;
    }
    
    public boolean verifyLinkCode(String mcUsername, String code, String discordId) {
        if (!pendingLinks.containsKey(mcUsername)) {
            getLogger().warning("Verification failed: No pending link for " + mcUsername);
            return false;
        }
        
        if (!pendingLinks.get(mcUsername).equals(code)) {
            getLogger().warning("Verification failed: Invalid code for " + mcUsername);
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
        
        // Notify player if online
        Player player = Bukkit.getPlayer(mcUsername);
        if (player != null && player.isOnline()) {
            player.sendMessage("§a✅ Your Discord account has been successfully linked!");
            player.sendMessage("§eYou can now play without restrictions!");
            player.sendMessage("§7Use §f/linked §7to check your link status anytime.");
        }
        
        getLogger().info("Successfully linked: " + mcUsername + " -> Discord ID: " + discordId);
        return true;
    }
    
    public boolean unlinkAccount(String mcUsername) {
        if (!linkedAccounts.containsKey(mcUsername)) {
            return false;
        }
        
        String discordId = linkedAccounts.remove(mcUsername);
        saveLinkedAccounts();
        
        // Notify Discord
        String description = String.format(
            "🔓 **Account Unlinked**\n\n" +
            "🎮 **Minecraft:** `%s`\n" +
            "💬 **Discord:** <@%s>\n\n" +
            "Account linking has been removed.",
            mcUsername, discordId
        );
        
        sendDiscordWebhook("🔓 Account Unlinked", description, 0xFF4444);
        
        getLogger().info("Unlinked account: " + mcUsername + " -> Discord ID: " + discordId);
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
            getLogger().warning("Cannot send webhook: No webhook URL configured");
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
                        // Success
                    } else if (responseCode == 429) {
                        getLogger().warning("Discord webhook rate limited");
                    } else {
                        getLogger().warning("Discord webhook failed with response code: " + responseCode);
                    }
                    
                } catch (Exception e) {
                    getLogger().log(Level.WARNING, "Failed to send Discord webhook", e);
                }
            }
        }.runTaskAsynchronously(this);
    }
}