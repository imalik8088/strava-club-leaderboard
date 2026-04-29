# Scrape Strava club leaderboard
Its helps one to get the most active (time), cyclist (km), runner (km) and swimmer (m) from a passed club_id. Unfortunately Strava does not expose a proper 
API that give one the necessary information easily. Therefore this repo has been created to login into Strava via email and password, scrape all member data 
of the club. 


## Usage
```bash
uv run main.py
uv run post_processing.py
```
#### Output

```bash
❯ python post_processing.py
parsed xxx members
🕓 Most active member:
1. Qwe rty - 123 hours 12 minutes

🚴 Most active cyclists
1. Qwe rty - 1234.1 Km

🏃 Most active runner
1. Qwe rty - 123.1 Km

🏊‍ Most active swimmer
2. Qwe rty - 123 meter
```

 
### Todo/Issues
  - [ ] duplicate/cleanup code
  - [ ] cleanup hacked post_processing.py file
  - [ ] swimming max 999.999 representation bcz regex
   

