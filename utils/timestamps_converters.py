from datetime import datetime

def parse_iso_z(timestamp: str) -> datetime:
  # Parse ISO 8601 timestamp with optional Z and nanoseconds
  # Always returns timezone-aware UTC datetime
  if timestamp.endswith("Z"):
    timestamp = timestamp[:-1] + "+00:00"

  return datetime.fromisoformat(timestamp)


def timestamp_to_seconds(timestamp: str) -> int:
  dt = parse_iso_z(timestamp)
  return int(dt.timestamp())


def get_timestamp_difference(timestamp_new: str, timestamp_old: str) -> int:
  dt1 = parse_iso_z(timestamp_new)
  dt2 = parse_iso_z(timestamp_old)
  return int((dt1 - dt2).total_seconds())
