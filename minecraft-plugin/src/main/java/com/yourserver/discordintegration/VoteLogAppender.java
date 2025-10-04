package com.yourserver.discordintegration;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.logging.log4j.core.Appender;
import org.apache.logging.log4j.core.appender.AppenderLoggingException;
import org.apache.logging.log4j.core.Filter;
import org.apache.logging.log4j.core.Layout;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.LoggerContext;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Configuration;
import org.apache.logging.log4j.core.config.LoggerConfig;

import java.io.Serializable;
import java.util.Locale;

/**
 * Log4j appender that filters console lines for vote-related messages and stores them in VoteLogBuffer.
 */
public class VoteLogAppender extends AbstractAppender {
    private static final Logger LOGGER = LogManager.getLogger("DiscordIntegration-VoteLogAppender");

    protected VoteLogAppender(String name, Filter filter, Layout<? extends Serializable> layout, boolean ignoreExceptions) {
        super(name, filter, layout, ignoreExceptions);
    }

    public static Appender register() {
        LoggerContext ctx = (LoggerContext) LogManager.getContext(false);
        Configuration config = ctx.getConfiguration();

        Appender appender = new VoteLogAppender("VoteLogAppender", null, null, true);
        appender.start();

        config.addAppender(appender);
        for (LoggerConfig loggerConfig : config.getLoggers().values()) {
            loggerConfig.addAppender(appender, null, null);
        }
        config.getRootLogger().addAppender(appender, null, null);
        ctx.updateLoggers();

        LOGGER.info("VoteLogAppender registered");
        return appender;
    }

    @Override
    public void append(LogEvent event) {
        try {
            String msg = event.getMessage().getFormattedMessage();
            if (msg == null || msg.isEmpty()) return;
            String lower = msg.toLowerCase(Locale.ROOT);
            if (lower.contains("[votifier]") || lower.contains("[votingplugin]") ||
                (lower.contains("received a vote") && lower.contains("player")) ||
                (lower.contains("protocol v1 vote record") && lower.contains("vote (from:"))) {
                VoteLogBuffer.getInstance().add(msg);
            }
        } catch (Exception ex) {
            if (!ignoreExceptions()) {
                throw new AppenderLoggingException(ex);
            }
        }
    }
}
