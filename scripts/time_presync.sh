#!/bin/bash
# Pre-sync system time before power cut
# Runs at 17:55 on weekdays, sets time to 6:55 of next power-on day

DAY_OF_WEEK=$(date +%u)  # 1=Monday, 5=Friday, 7=Sunday

# Calculate days to add based on current day
case $DAY_OF_WEEK in
    5)  # Friday -> Monday (add 3 days)
        DAYS_AHEAD=3
        ;;
    *)  # Mon-Thu -> next day (add 1 day)
        DAYS_AHEAD=1
        ;;
esac

# Calculate target date
TARGET_DATE=$(date -d "+${DAYS_AHEAD} days" +%Y-%m-%d 2>/dev/null)

# Fallback for macOS/BSD date command
if [ -z "$TARGET_DATE" ]; then
    TARGET_DATE=$(date -v+${DAYS_AHEAD}d +%Y-%m-%d)
fi

TARGET_DATETIME="${TARGET_DATE} 06:55:00"

echo "$(date): Setting system time to ${TARGET_DATETIME}"
sudo date -s "${TARGET_DATETIME}" 2>/dev/null || sudo date "${TARGET_DATE}0655.00"

echo "Time pre-sync complete. New time: $(date)"
