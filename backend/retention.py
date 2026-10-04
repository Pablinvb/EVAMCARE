"""Pure retention eligibility; no automatic destructive job is enabled."""
from calendar import monthrange
from datetime import datetime

def shift_months(value, months):
    total=value.year*12+value.month-1+months
    year,month=divmod(total,12);month+=1
    return value.replace(year=year,month=month,day=min(value.day,monthrange(year,month)[1]))

def eligible(created_at,last_activity,at):
    created=datetime.fromisoformat(created_at)
    activity=datetime.fromisoformat(last_activity)
    # One full calendar year AND three complete calendar months of inactivity.
    return at>=shift_months(created,12) and at>=shift_months(activity,3)
