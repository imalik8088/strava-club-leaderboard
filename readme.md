# Scrape Strava club leaderboard
Its helps one to get the most active (time), cyclist (km), runner (km) and swimmer (m) from a passed club_id. Unfortunately Strava does not expose a proper 
API that give one the necessary information easily. Therefore this repo has been created to login into Strava via email and password, scrape all member data 
of the club. 


## Usage
```bash
scrapy crawl strava -a club_id=2282432
python post_processing.py
```
#### Output

```bash
❯ python post_processing.py 
parsed 404 members
[🕓] Most active member: [ActiveLeader(name='Mno Pqr', duration='100 hours 46 minutes')]
[🚴] Most active cyclists [CyclingLeader(name='Xyz Abc', cycling_distance_in_km=1234.5)]
[🏃‍] Most active runner [RunnerLeader(name='Abc Def', running_distance_in_km=123.1)]
[🏊‍] Most active swimmer [SwimmingLeader(name='Qwe rty', swimming_distance_in_meter=12345.0)]
```

 
## Install
```bash
# if you're using virtualenv
virtualenv -p python3.8 venv
source ./venv/bin/activate

pip install -r requirements.txt
```

### Todo/Issues
  - [ ] duplicate/cleanup code
  - [ ] cleanup hacked post_processing.py file
  - [ ] swimming max 999.999 representation bcz regex
   

