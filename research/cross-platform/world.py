"""The simulated enterprise: 12 users, 3 roles, designed seats. Writes data/directory.json and data/seats.json.

    python3 world.py
"""
import json
from common import *

ROLES = {"support": "maya", "operations": "arjun", "management": "lena"}        # role -> author of the scripts
USERS = [  # handle, name, role, habit: where the person starts a task (weights), seats = the keys
    ("priya", "Priya Nair", "support", {"atlas": .8, "chatly": .2}),
    ("tomas", "Tomas Berg", "support", {"atlas": 1.0}),
    ("hana", "Hana Okafor", "support", {"atlas": .6, "beacon": .4, "chatly": 0.0}),
    ("jonas", "Jonas Reid", "support", {"beacon": .7, "chatly": .3}),
    ("kofi", "Kofi Mensah", "operations", {"atlas": .5, "beacon": .5}),
    ("lucia", "Lucia Ferrer", "operations", {"beacon": 1.0}),
    ("dmitri", "Dmitri Volkov", "operations", {"atlas": .97, "chatly": .03}),
    ("ines", "Ines Costa", "operations", {"atlas": .7, "beacon": .3, "chatly": 0.0}),
    ("rosa", "Rosa Lindqvist", "management", {"chatly": .8, "atlas": .2}),
    ("omar", "Omar Haddad", "management", {"chatly": 1.0}),
    ("freya", "Freya Doyle", "management", {"atlas": .4, "beacon": .3, "chatly": .3}),
    ("ben", "Ben Achterberg", "management", {"beacon": 1.0, "atlas": 0.0}),
]
IDLE_THRESHOLD = .05      # a designed idle seat: the person starts under 5% of tasks there


def build():
    directory, seats = [], []
    for i, (h, name, role, habit) in enumerate(USERS):
        directory.append({"handle": h, "name": name, "role": role, "email": f"{name.lower().replace(' ', '.')}@kettleandcrumb.example",
                          "employee_id": f"E{1041 + 7 * i}"})
        for p, w in habit.items():
            seats.append({"handle": h, "platform": p, "monthly_price": PRICE[p], "designed_idle": w < IDLE_THRESHOLD, "start_weight": w})
    # the analysis may read directory.json and the seat list (licences); the designed flag and weights stay in truth only
    json.dump({"users": directory}, open(os.path.join(D, "directory.json"), "w"), indent=1)
    json.dump([{k: s[k] for k in ("handle", "platform", "monthly_price")} for s in seats], open(os.path.join(D, "seats.json"), "w"), indent=1)
    return directory, seats


if __name__ == "__main__":
    d, s = build()
    print(len(d), "users", len(s), "seats", sum(x["monthly_price"] for x in s), "per month,",
          sum(x["designed_idle"] for x in s), "designed idle")
