package com.yourserver.discordintegration;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

public class VerifyConsoleCommand implements CommandExecutor {
    private final DiscordIntegration plugin;

    public VerifyConsoleCommand(DiscordIntegration plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length < 3) {
            sender.sendMessage("§cUsage: /" + label + " <minecraft_username> <discord_id> <code>");
            return true;
        }

        String mcUsername = args[0];
        String discordId = args[1];
        String code = args[2];

        // Only allow from console or players with admin perm
        if (sender instanceof Player) {
            Player p = (Player) sender;
            if (!p.hasPermission("discordintegration.admin")) {
                p.sendMessage("§cYou don't have permission to use this command.");
                return true;
            }
        }

        boolean ok = plugin.verifyLinkFromConsole(mcUsername, discordId, code);
        if (ok) {
            sender.sendMessage("§aLinked successfully: " + mcUsername + " -> " + discordId);
        } else {
            sender.sendMessage("§cFailed to link. Ensure a pending link exists and the code matches.");
        }
        return true;
    }
}
