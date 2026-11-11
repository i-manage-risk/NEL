"""COT publication calendar, separate from Tuesday position observations."""
from datetime import date,timedelta
# CFTC 2026 release schedule. https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm
DELAYED_2026={'2025-12-30':'2026-01-05','2026-06-16':'2026-06-22','2026-06-30':'2026-07-06','2026-11-10':'2026-11-16','2026-11-24':'2026-11-30','2026-12-22':'2026-12-28'}
def publication_date(observation):
    if observation in DELAYED_2026:return DELAYED_2026[observation], 'CFTC 2026 release schedule'
    day=date.fromisoformat(observation)
    release=day+timedelta(days=(4-day.weekday())%7)
    # Older datasets contain observation dates, not publication timestamps.
    return release.isoformat(),('CFTC 2026 release schedule' if release.year==2026 else 'Estimated regular Friday release; historical publication timestamp unavailable')
def stamp_market(market):
    for row in market['history']:
        row['release_date'],row['release_date_source']=publication_date(row['date'])
    return market
