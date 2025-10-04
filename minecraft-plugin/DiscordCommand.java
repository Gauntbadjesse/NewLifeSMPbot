package com.yourserver.discordintegration;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

public class LinkCommand implements CommandExecutor {
    
    private final DiscordIntegration plugin;
    
    public LinkCommand(DiscordIntegration plugin) {
        this.plugin = plugin;
    }
    
    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        
        if (!(sender instanceof Player)) {
            sender.sendMessage("§cThis command can only be used by players!");
            return true;
        }
        
        Player player = (Player) sender;
        String mcUsername = player.getName();
        
        switch (command.getName().toLowerCase()) {
            case "link":
                return handleLinkCommand(player, args);
                
            case "unlink":
                return handleUnlinkCommand(player);
                
            case "linked":
                return handleLinkedCommand(player);
                
            default:
                return false;
        }
    }
    
    private boolean handleLinkCommand(Player player, String[] args) {
        String mcUsername = player.getName();
        
        // Check if already linked
        if (plugin.isLinked(mcUsername)) {
            player.sendMessage("§c❌ Your account is already linked to Discord!");
            player.sendMessage("§eUse §f/unlink §eto unlink first, then try again.");
            return true;
        }
        
        if (args.length == 0) {
            player.sendMessage("§c❌ Please provide your Discord username!");
            player.sendMessage("§eUsage: §f/link <your_discord_username>");
            player.sendMessage("§7Example: §f/link JohnDoe#1234 §7or §f/link @JohnDoe");
            return true;
        }
        
        String discordUsername = String.join(" ", args);
        
        // Clean up common Discord username formats
        discordUsername = discordUsername.replace("@", "").trim();
        
        if (discordUsername.length() < 2) {
            player.sendMessage("§c❌ Discord username too short!");
            return true;
        }
        
        // Generate verification code
        String code = plugin.generateLinkCode(mcUsername, discordUsername);
        
        player.sendMessage("§a✅ Link request sent!");
        player.sendMessage("§e📱 A verification code has been posted in Discord.");
        player.sendMessage("§eGo to the Discord server and type: §f!verify " + code);
        player.sendMessage("§7The code will expire in 5 minutes.");
        
        return true;
    }
    
    private boolean handleUnlinkCommand(Player player) {
        String mcUsername = player.getName();
        
        if (!plugin.isLinked(mcUsername)) {
            player.sendMessage("§c❌ Your account is not linked to Discord!");
            return true;
        }
        
        if (plugin.unlinkAccount(mcUsername)) {
            player.sendMessage("§a✅ Your account has been unlinked from Discord.");
        } else {
            player.sendMessage("§c❌ Failed to unlink your account. Please try again.");
        }
        
        return true;
    }
    
    private boolean handleLinkedCommand(Player player) {
        String mcUsername = player.getName();
        
        if (plugin.isLinked(mcUsername)) {
            String discordId = plugin.getDiscordId(mcUsername);
            player.sendMessage("§a✅ Your account is linked to Discord!");
            player.sendMessage("§7Discord ID: §f" + discordId);
        } else {
            player.sendMessage("§c❌ Your account is not linked to Discord!");
            player.sendMessage("§eUse §f/link <your_discord_username> §eto link your account.");
        }
        
        return true;
    }
}