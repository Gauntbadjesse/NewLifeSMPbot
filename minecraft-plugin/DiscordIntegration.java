package com.yourserver.discordintegration;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;
import java.util.UUID;
import java.util.logging.Level;

public class DiscordIntegration extends JavaPlugin implements Listener {
    
    private String webhookUrl;
    private String botApiUrl;
    private Map<String, String> pendingLinks = new HashMap<>(); // minecraft_username -> verification_code
    private Map<String, String> linkedAccounts = new HashMap<>(); // minecraft_username -> discord_id
    
    @Override
    public void onEnable() {
        // Save default config
        saveDefaultConfig();
        loadConfiguration();
        loadLinkedAccounts();
        
        // Register events
        getServer().getPluginManager().registerEvents(this, this);
        
        // Register commands
        getCommand("link").setExecutor(new LinkCommand(this));
        getCommand("unlink").setExecutor(new LinkCommand(this));
        getCommand("linked").setExecutor(new LinkCommand(this));
        
        getLogger().info("Discord Integration Plugin enabled!");
        
        // Send startup notification
        sendDiscordWebhook("🟢 **Server Started**", "The Minecraft server is now online!", 0x00FF00);
    }
    
    @Override
    public void onDisable() {
        saveLinkedAccounts();
        sendDiscordWebhook("🔴 **Server Stopped**", "The Minecraft server is now offline.", 0xFF0000);
        getLogger().info("Discord Integration Plugin disabled!");
    }
    
    private void loadConfiguration() {
        reloadConfig();
        webhookUrl = getConfig().getString("webhook-url", "");
        botApiUrl = getConfig().getString("bot-api-url", "http://localhost:8080");
    }
    
    private void loadLinkedAccounts() {
        File dataFile = new File(getDataFolder(), "linked_accounts.txt");
        if (!dataFile.exists()) return;
        
        try (BufferedReader reader = new BufferedReader(new FileReader(dataFile))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] parts = line.split(":");
                if (parts.length == 2) {
                    linkedAccounts.put(parts[0], parts[1]);
                }
            }
        } catch (IOException e) {
            getLogger().log(Level.WARNING, "Failed to load linked accounts", e);
        }
    }
    
    private void saveLinkedAccounts() {
        File dataFile = new File(getDataFolder(), "linked_accounts.txt");
        getDataFolder().mkdirs();
        
        try (PrintWriter writer = new PrintWriter(new FileWriter(dataFile))) {
            for (Map.Entry<String, String> entry : linkedAccounts.entrySet()) {
                writer.println(entry.getKey() + ":" + entry.getValue());
            }
        } catch (IOException e) {
            getLogger().log(Level.WARNING, "Failed to save linked accounts", e);
        }
    }
    
    // ========== EVENT HANDLERS ==========
    
    @EventHandler
    public void onPlayerJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        String mcUsername = player.getName();
        
        // Check if player is linked
        if (!linkedAccounts.containsKey(mcUsername)) {
            // Send warning about needing to link account
            Bukkit.getScheduler().runTaskLater(this, () -> {
                player.sendMessage("§c⚠️ Your account is not linked to Discord!");
                player.sendMessage("§eUse §f/link <your_discord_username> §eto link your account.");
                player.sendMessage("§7Example: §f/link JohnDoe#1234");
                player.sendMessage("§cYou may be kicked if you don't link your account!");
            }, 60L); // 3 seconds delay
        } else {
            // Welcome back linked user
            player.sendMessage("§a✅ Welcome back! Your Discord account is linked.");
            
            // Notify Discord
            String discordId = linkedAccounts.get(mcUsername);
            String description = String.format("**%s** (linked to <@%s>) joined the server", 
                                             player.getDisplayName(), discordId);
            sendDiscordWebhook("📥 Linked Player Joined", description, 0x00FF00);
        }
    }
    
    @EventHandler
    public void onPlayerQuit(PlayerQuitEvent event) {
        Player player = event.getPlayer();
        
        // Clean up pending link if player leaves
        pendingLinks.remove(player.getName());
        
        // Notify Discord if linked
        if (linkedAccounts.containsKey(player.getName())) {
            String discordId = linkedAccounts.get(player.getName());
            String description = String.format("**%s** (linked to <@%s>) left the server", 
                                             player.getDisplayName(), discordId);
            sendDiscordWebhook("📤 Linked Player Left", description, 0xFF4444);
        }
    }
    
    // ========== LINKING SYSTEM ==========
    
    public String generateLinkCode(String mcUsername, String discordUsername) {
        // Generate 6-digit verification code
        String code = String.format("%06d", new Random().nextInt(999999));
        pendingLinks.put(mcUsername, code);
        
        // Send code to Discord webhook
        String description = String.format(
            "**Minecraft Account Link Request**\n\n" +
            "🎮 **Minecraft:** %s\n" +
            "💬 **Discord:** %s\n" +
            "🔢 **Code:** `%s`\n\n" +
            "Player %s should type `!verify %s` in Discord to complete the link.",
            mcUsername, discordUsername, code, discordUsername, code
        );
        
        sendDiscordWebhook("� Link Request", description, 0x5865F2);
        
        return code;
    }
    
    public boolean verifyLinkCode(String mcUsername, String code, String discordId) {
        if (!pendingLinks.containsKey(mcUsername)) {
            return false;
        }
        
        if (!pendingLinks.get(mcUsername).equals(code)) {
            return false;
        }
        
        // Link successful
        pendingLinks.remove(mcUsername);
        linkedAccounts.put(mcUsername, discordId);
        saveLinkedAccounts();
        
        // Notify Discord
        String description = String.format(
            "✅ **Account Successfully Linked!**\n\n" +
            "🎮 **Minecraft:** %s\n" +
            "💬 **Discord:** <@%s>",
            mcUsername, discordId
        );
        
        sendDiscordWebhook("� Link Successful", description, 0x00FF00);
        
        // Notify player if online
        Player player = Bukkit.getPlayer(mcUsername);
        if (player != null && player.isOnline()) {
            player.sendMessage("§a✅ Your Discord account has been successfully linked!");
            player.sendMessage("§eYou can now play without restrictions!");
        }
        
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
            "🎮 **Minecraft:** %s\n" +
            "💬 **Discord:** <@%s>",
            mcUsername, discordId
        );
        
        sendDiscordWebhook("🔓 Account Unlinked", description, 0xFF4444);
        
        return true;
    }
    
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
    
    // ========== DISCORD COMMUNICATION ==========
    
    public void sendDiscordWebhook(String title, String description, int color) {
        if (webhookUrl.isEmpty()) return;
        
        Bukkit.getScheduler().runTaskAsynchronously(this, () -> {
            try {
                URL url = new URL(webhookUrl);
                HttpURLConnection connection = (HttpURLConnection) url.openConnection();
                connection.setRequestMethod("POST");
                connection.setRequestProperty("Content-Type", "application/json");
                connection.setDoOutput(true);
                
                // Create JSON payload
                String jsonPayload = String.format(
                    "{\"embeds\":[{\"title\":\"%s\",\"description\":\"%s\",\"color\":%d,\"timestamp\":\"%s\"}]}",
                    title.replace("\"", "\\\""),
                    description.replace("\"", "\\\"").replace("\n", "\\n"),
                    color,
                    java.time.Instant.now().toString()
                );
                
                try (OutputStream os = connection.getOutputStream()) {
                    byte[] input = jsonPayload.getBytes("utf-8");
                    os.write(input, 0, input.length);
                }
                
                int responseCode = connection.getResponseCode();
                if (responseCode != 204) {
                    getLogger().warning("Discord webhook failed with response code: " + responseCode);
                }
                
            } catch (Exception e) {
                getLogger().log(Level.WARNING, "Failed to send Discord webhook", e);
            }
        });
    }
    
    // ========== API ENDPOINT FOR DISCORD BOT ==========
    
    public boolean processVerificationFromDiscord(String mcUsername, String code, String discordId) {
        return verifyLinkCode(mcUsername, code, discordId);
    }
}