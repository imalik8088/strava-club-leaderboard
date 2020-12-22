# -*- coding: utf-8 -*-

from pydantic import BaseModel
from tinydb import TinyDB, Query
from tinydb.database import Table


class User(BaseModel):
    user_id: str
    name: str
    profile_url: str
    cycling_distance_in_km: float
    cycling_duration_in_minute: int
    running_distance_in_km: float
    running_duration_in_minute: int
    swimming_distance_in_meter: float
    swimming_duration_in_minute: int


def _minutes_in_hours(minutes):
    hours = int(minutes / 60)
    minute = minutes % hours
    return "%d hours %02d minutes" % (hours, minute)


db: Table = TinyDB('./db/strava-leaderboard.json')
Leaderboard = Query()

members = {}
get_all_entries = db.all()
for entry in get_all_entries:
    member = User(name=entry.get('name'),
                  user_id=entry.get('user_id'),
                  profile_url=entry.get('profile_url'),
                  cycling_distance_in_km=entry.get('cycling_distance_in_km'),
                  cycling_duration_in_minute=entry.get('cycling_duration_in_minute'),
                  running_distance_in_km=entry.get('running_distance_in_km'),
                  running_duration_in_minute=entry.get('running_duration_in_minute'),
                  swimming_distance_in_meter=entry.get('swimming_distance_in_meter'),
                  swimming_duration_in_minute=entry.get('swimming_duration_in_minute'),
                  )
    if member.user_id == "64492740":
        continue
    members[member.user_id] = member

print(f"parsed {len(members)} members")

# ----------- LEADERBOARD: active member
class ActiveLeader(BaseModel):
    name: str
    duration: str

class UserDuration(BaseModel):
    user_id: str
    name: str
    duration: int

total_member_activity_duration = []
for user_id, m in members.items():
    member_duration = UserDuration(user_id=m.user_id,
                                   name=m.name,
                                   duration=m.cycling_duration_in_minute + m.running_duration_in_minute + m.swimming_duration_in_minute)
    total_member_activity_duration.append(member_duration)

total_member_activity_duration = sorted(total_member_activity_duration, key=lambda k: k.duration, reverse=True)
leaderboard_duration = []
for member in total_member_activity_duration[:5]:
    leaderboard_duration.append(ActiveLeader(
        name=member.name,
        duration=_minutes_in_hours(member.duration)))

print("🕓 Most active member:")
for index, member in enumerate(leaderboard_duration, start=1):
    print(f"{index}. {member.name} - {member.duration}")
print()



# ----------- LEADERBOARD: cycling
class CyclingLeader(BaseModel):
    name: str
    cycling_distance_in_km: float

leaderboard_cycling = []
for k, v in members.items():
    leaderboard_cycling.append(CyclingLeader(name=v.name, cycling_distance_in_km=v.cycling_distance_in_km))

cycling_distance_in_km = sorted(leaderboard_cycling, key=lambda k: k.cycling_distance_in_km, reverse=True)
print("🚴 Most active cyclists")
for index, member in enumerate(cycling_distance_in_km[:5], start=1):
    print(f"{index}. {member.name} - {member.cycling_distance_in_km} Km")
print()
# ----------- LEADERBOARD: running
class RunnerLeader(BaseModel):
    name: str
    running_distance_in_km: float

leaderboard_cycling = []
for k, v in members.items():
    leaderboard_cycling.append(RunnerLeader(name=v.name, running_distance_in_km=v.running_distance_in_km))

running_distance_in_km = sorted(leaderboard_cycling, key=lambda k: k.running_distance_in_km, reverse=True)

print("🚴 Most active runner")
for index, member in enumerate(running_distance_in_km[:5], start=1):
    print(f"{index}. {member.name} - {member.running_distance_in_km} Km")
print()
# ----------- LEADERBOARD: swimming
class SwimmingLeader(BaseModel):
    name: str
    swimming_distance_in_meter: int

leaderboard_cycling = []
for k, v in members.items():
    leaderboard_cycling.append(SwimmingLeader(name=v.name, swimming_distance_in_meter=v.swimming_distance_in_meter))

swimming_distance_in_meter = sorted(leaderboard_cycling, key=lambda k: k.swimming_distance_in_meter, reverse=True)

print("🚴 Most active swimmer")
for index, member in enumerate(swimming_distance_in_meter[:5], start=1):
    print(f"{index}. {member.name} - {member.swimming_distance_in_meter} meter")
