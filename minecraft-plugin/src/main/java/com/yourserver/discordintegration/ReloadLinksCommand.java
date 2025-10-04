package com.yourserver.discordintegration;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

public class ReloadLinksCommand implements CommandExecutor {
    private final DiscordIntegration plugin;

    public ReloadLinksCommand(DiscordIntegration plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (sender instanceof Player) {
            Player p = (Player) sender;
            if (!p.hasPermission("discordintegration.admin")) {
                p.sendMessage("§cYou don't have permission to use this command.");
                return true;
            }
        }

        plugin.loadLinkedAccounts();
        int count = plugin.getAllLinkedAccounts().size();
        sender.sendMessage("§aReloaded linked accounts. Total linked: " + count);
        plugin.getLogger().info("Reloaded linked accounts via command. Total: " + count);
        return true;
    }
}
