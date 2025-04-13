import datetime
import pytz


def format_time_ago(timestamp_str):
    """Format a timestamp as '2 hours ago', '3 days ago', etc"""
    if not timestamp_str:
        return "Never"

    timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

    utc_timestamp = (
        pytz.UTC.localize(timestamp) if timestamp.tzinfo is None else timestamp
    )

    now = datetime.datetime.now(datetime.timezone.utc).astimezone()

    local_timestamp = utc_timestamp.astimezone(now.tzinfo)

    diff = now - local_timestamp

    if diff.total_seconds() < 60:
        return "Just now"

    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() / 60)
        return f"{minutes} {'minute' if minutes == 1 else 'minutes'} ago"

    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} {'hour' if hours == 1 else 'hours'} ago"

    elif diff.days < 30:
        return f"{diff.days} {'day' if diff.days == 1 else 'days'} ago"

    elif diff.days < 365:
        months = int(diff.days / 30)
        return f"{months} {'month' if months == 1 else 'months'} ago"

    else:
        years = int(diff.days / 365)
        return f"{years} {'year' if years == 1 else 'years'} ago"
