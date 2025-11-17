"""
Make User.email unique.
Keeps the *first* user for each duplicated address and
sets the others’ e-mail to NULL so the unique constraint
can be created without integrity-error.
"""
import os, sys
import django

# 1.  Setup Django -------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.production")   
django.setup()

# 2.  Imports ------------------------------------------------------
from django.db import transaction, models
from django.contrib.auth import get_user_model

User = get_user_model()

# 3.  Actual work --------------------------------------------------
def make_email_unique():
    duplicates = (
        User.objects.values("email")
        .order_by()                       # clear default ordering
        .annotate(c=models.Count("id"))
        .filter(c__gt=1)
        .exclude(email__exact="")         # ignore empty strings
        .exclude(email=None)
    )

    total_fixed = 0
    for dup in duplicates:
        email = dup["email"]
        users = list(User.objects.filter(email=email).order_by("date_joined"))
        keeper = users.pop(0)            # first user keeps the address
        with transaction.atomic():
            for u in users:
                u.email = None
                u.save(update_fields=["email"])
            total_fixed += len(users)
        print(f"Kept e-mail for {keeper}  –  nulled {len(users)} duplicates")

    if total_fixed:
        print(f"\n✅  {total_fixed} duplicate e-mails nulled.")
    else:
        print("\n✅  No duplicates found.")

if __name__ == "__main__":
    make_email_unique()