package com.yourserver.discordintegration;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Ring buffer for recent vote-related console lines, with monotonically increasing sequence IDs.
 */
public class VoteLogBuffer {
    private static final int MAX_LINES = 512; // keep last 512 lines
    private static final VoteLogBuffer INSTANCE = new VoteLogBuffer();

    public static VoteLogBuffer getInstance() { return INSTANCE; }

    public static class Entry {
        public final long seq;
        public final long time;
        public final String line;

        public Entry(long seq, long time, String line) {
            this.seq = seq;
            this.time = time;
            this.line = line;
        }
    }

    private final Deque<Entry> buffer = new ArrayDeque<>();
    private final AtomicLong seqCounter = new AtomicLong(0);

    public synchronized void add(String line) {
        long seq = seqCounter.incrementAndGet();
        buffer.addLast(new Entry(seq, System.currentTimeMillis(), line));
        while (buffer.size() > MAX_LINES) {
            buffer.removeFirst();
        }
    }

    public synchronized List<Entry> getAfter(long afterSeq, int limit) {
        List<Entry> result = new ArrayList<>();
        for (Entry e : buffer) {
            if (e.seq > afterSeq) {
                result.add(e);
                if (result.size() >= limit) break;
            }
        }
        return result;
    }

    public synchronized long getLatestSeq() {
        Entry last = buffer.peekLast();
        return last != null ? last.seq : 0L;
    }
}
