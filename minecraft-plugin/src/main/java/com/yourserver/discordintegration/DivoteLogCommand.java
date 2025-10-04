package com.yourserver.discordintegration;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.jetbrains.annotations.NotNull;

import java.util.List;

public class DivoteLogCommand implements CommandExecutor {
    @Override
    public boolean onCommand(@NotNull CommandSender sender, @NotNull Command command, @NotNull String label, @NotNull String[] args) {
        if (sender instanceof Player) {
            sender.sendMessage("§cThis command is console-only.");
            return true;
        }

        long after = 0L;
        int limit = 50;
        if (args.length >= 1) {
            try { after = Long.parseLong(args[0]); } catch (NumberFormatException ignored) {}
        }
        if (args.length >= 2) {
            try { limit = Math.max(1, Math.min(200, Integer.parseInt(args[1]))); } catch (NumberFormatException ignored) {}
        }

        List<VoteLogBuffer.Entry> entries = VoteLogBuffer.getInstance().getAfter(after, limit);
        StringBuilder sb = new StringBuilder();
        sb.append("[");
        for (int i = 0; i < entries.size(); i++) {
            VoteLogBuffer.Entry e = entries.get(i);
            // Simple JSON escaping for quotes and backslashes
            String safe = e.line.replace("\\", "\\\\").replace("\"", "\\\"");
            sb.append("{\"seq\":").append(e.seq)
              .append(",\"time\":").append(e.time)
              .append(",\"line\":\"").append(safe).append("\"}");
            if (i < entries.size() - 1) sb.append(",");
        }
        sb.append("]");

        sender.sendMessage(sb.toString());
        return true;
    }
}
