package com.yourserver.discordintegration;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;
import org.bukkit.util.StringUtil;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class LinkCommand implements CommandExecutor, TabCompleter {
    
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
                return handleLinkCommand(player, mcUsername, args);
            case "unlink":
                return handleUnlinkCommand(player, mcUsername);
            case "linked":
                return handleLinkedCommand(player, mcUsername);
            default:
                return false;
        }
    }
    
    private boolean handleLinkCommand(Player player, String mcUsername, String[] args) {
        // Check if already linked
        if (plugin.isLinked(mcUsername)) {
            player.sendMessage("§c❌ Your account is already linked!");
            player.sendMessage("§7Current Discord: " + plugin.getDiscordId(mcUsername));
            player.sendMessage("§eUse §f/unlink §eto remove the current link first.");
            return true;
        }
        
        // Check if already has a pending link
        if (plugin.hasPendingLink(mcUsername)) {
            player.sendMessage("§c⏳ You already have a pending link request!");
            player.sendMessage("§eCheck Discord for your verification code and use §f!verify <code>");
            return true;
        }
        
        // Validate arguments
        if (args.length == 0) {
            player.sendMessage("§c❌ Usage: §f/link <discord_username>");
            player.sendMessage("§7Examples:");
            player.sendMessage("§f  /link JohnDoe");
            player.sendMessage("§f  /link JohnDoe#1234");
            player.sendMessage("§f  /link @JohnDoe");
            return true;
        }
        
        // Get Discord username from arguments
        String discordUsername = String.join(" ", args).trim();
        
        // Clean up Discord username
        if (discordUsername.startsWith("@")) {
            discordUsername = discordUsername.substring(1);
        }
        
        // Validate Discord username format (basic validation)
        if (discordUsername.length() < 2 || discordUsername.length() > 37) {
            player.sendMessage("§c❌ Invalid Discord username format!");
            player.sendMessage("§eDiscord usernames must be 2-37 characters long.");
            return true;
        }
        
        // Check for invalid characters (basic check)
        if (discordUsername.contains(" ")) {
            player.sendMessage("§c❌ Discord usernames cannot contain spaces!");
            player.sendMessage("§eUse the exact username without spaces.");
            return true;
        }
        
        // Generate verification code
        String code = plugin.generateLinkCode(mcUsername, discordUsername);
        
        // Send success message to player
        player.sendMessage("§a✅ Link request sent!");
        player.sendMessage("§e📧 Check Discord for your verification code.");
        player.sendMessage("§7Discord Username: §f" + discordUsername);
        player.sendMessage("§7Verification Code: §f" + code);
        player.sendMessage("");
        player.sendMessage("§eType this in Discord: §f!verify " + code);
        player.sendMessage("§7⏰ Code expires in 5 minutes.");
        player.sendMessage("");
        player.sendMessage("§6💡 After linking, you'll be switched to Survival mode!");
        
        // Log the request
        plugin.getLogger().info("§a[Discord Integration] Link request from " + mcUsername + " for Discord: " + discordUsername);
        
        return true;
    }
    
    private boolean handleUnlinkCommand(Player player, String mcUsername) {
        // Check if linked
        if (!plugin.isLinked(mcUsername)) {
            player.sendMessage("§c❌ Your account is not linked to Discord!");
            player.sendMessage("§eUse §f/link <discord_username> §eto link your account.");
            return true;
        }
        
        // Get current Discord ID for confirmation
        String currentDiscordId = plugin.getDiscordId(mcUsername);
        
        // Attempt to unlink
        if (plugin.unlinkAccount(mcUsername)) {
            player.sendMessage("§a✅ Your Discord account has been unlinked successfully!");
            player.sendMessage("§7Previous Discord ID: " + currentDiscordId);
            player.sendMessage("§eYou can link a new account with §f/link <discord_username>");
            
            // Log the unlink
            plugin.getLogger().info("§a[Discord Integration] Unlinked account: " + mcUsername + " from Discord ID: " + currentDiscordId);
        } else {
            player.sendMessage("§c❌ Failed to unlink your account!");
            player.sendMessage("§eContact an administrator for help.");
            
            // Log the error
            plugin.getLogger().warning("§c[Discord Integration] Failed to unlink account for " + mcUsername);
        }
        
        return true;
    }
    
    private boolean handleLinkedCommand(Player player, String mcUsername) {
        if (plugin.isLinked(mcUsername)) {
            String discordId = plugin.getDiscordId(mcUsername);
            player.sendMessage("§a✅ Your account is linked to Discord!");
            player.sendMessage("§7Discord ID: §f" + discordId);
            player.sendMessage("§7Minecraft: §f" + mcUsername);
            player.sendMessage("");
            player.sendMessage("§eUse §f/unlink §eto remove the link.");
        } else if (plugin.hasPendingLink(mcUsername)) {
            player.sendMessage("§e⏳ Your account has a pending link request.");
            player.sendMessage("§eCheck Discord for your verification code and use §f!verify <code>");
        } else {
            player.sendMessage("§c❌ Your account is not linked to Discord.");
            player.sendMessage("§eUse §f/link <discord_username> §eto link your account.");
        }
        
        return true;
    }
    
    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        List<String> completions = new ArrayList<>();
        
        if (!(sender instanceof Player)) {
            return completions;
        }
        
        switch (command.getName().toLowerCase()) {
            case "link":
                if (args.length == 1) {
                    // Suggest common Discord username formats
                    List<String> suggestions = Arrays.asList(
                        "YourDiscordName",
                        "Username#1234",
                        "@Username"
                    );
                    StringUtil.copyPartialMatches(args[0], suggestions, completions);
                }
                break;
            case "unlink":
            case "linked":
                // These commands don't need tab completion
                break;
        }
        
        return completions;
    }
}