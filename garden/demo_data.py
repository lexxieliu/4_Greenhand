"""Demo garden for the preview account (balcony_maya), loaded by `python manage.py seed_demo_garden`.

Formerly mock_data.GARDEN. Dates are written relative to greenhand.clock.today() (Oct 13, 2026).
Statuses follow PRD v1.1: the mint, which keeps being harvested, is `producing`.
"""

DEMO_GARDEN = [
    {
        "id": "basil", "type": "basil", "plant_slug": "basil", "nickname": "Balcony Basil", "variety": "Genovese",
        "planted_on": "2026-09-09", "start_method": "seedling", "setting": "outdoor", "container": "Pot · 20 cm", "quantity": 1,
        "status": "growing", "watering_interval_days": 2,
        "tip": "Pinch the top pair of leaves every couple of weeks to keep basil bushy, and let the pot dry out between waterings.",
        "timeline": [
            {"id": "t1", "stage": "seedling", "date": "2026-09-09", "note": "Transplanted a nursery seedling into a 20 cm pot on the balcony.", "photo": True},
            {"id": "t2", "stage": "vegetative", "date": "2026-09-24", "note": "Pinched the top above the third leaf pair. Already bushier.", "photo": True},
            {"id": "t3", "stage": "vegetative", "date": "2026-10-12", "note": "Lower leaves turning yellow and a bit soft.", "photo": True},
        ],
        "care": [
            {"action": "water", "amount": "300 ml", "note": "", "date": "2026-10-07", "source": "reminder"},
            {"action": "water", "amount": "300 ml", "note": "", "date": "2026-10-05", "source": "reminder"},
            {"action": "prune", "amount": "", "note": "Pinched the tops", "date": "2026-09-24", "source": "tutor_suggestion"},
            {"action": "fertilize", "amount": "5 ml/L", "note": "Half-strength liquid feed", "date": "2026-09-20", "source": "manual"},
        ],
        "problems": [
            {
                "id": "p1", "title": "Yellow lower leaves", "category": "watering", "severity": "medium", "status": "monitoring",
                "description": "The lowest leaves are turning yellow and feel soft. New growth at the top looks fine.",
                "opened": "2026-10-12", "photo": True,
                "diagnosis": {
                    "issues": [
                        {"name": "Overwatering", "confidence": "high", "reasoning": "You watered on Oct 5 and 7, then 12 mm of rain fell. Soft, yellow lower leaves usually mean roots are sitting in wet soil."},
                        {"name": "Nitrogen deficiency", "confidence": "low", "reasoning": "Possible if the yellowing keeps moving up the plant after the soil dries."},
                    ],
                    "immediate_actions": ["Skip watering until the top 2 cm of soil is dry", "Check that the pot drains freely", "Pinch off the yellow leaves"],
                    "watch_for": ["Black stems near the soil (root rot)", "New growth turning yellow"],
                },
            },
        ],
        "harvests": [],
        "reminders": [
            {"id": "r1", "type": "water", "title": "Water Balcony Basil", "every": 2, "time": "08:00", "weather_aware": True, "active": True, "inapp": True, "email": True, "next_due": "2026-10-15",
             "history": [
                 {"date": "2026-10-13", "status": "skipped_rain", "reason": "12 mm rain in the last 24h"},
                 {"date": "2026-10-11", "status": "skipped_user", "reason": "Letting the pot dry out"},
                 {"date": "2026-10-09", "status": "missed"},
                 {"date": "2026-10-07", "status": "done"},
                 {"date": "2026-10-05", "status": "done"},
             ]},
            {"id": "r2", "type": "check_problem", "title": "Check basil for new yellow leaves", "every": 0, "time": "09:00", "weather_aware": False, "active": True, "inapp": True, "email": False, "next_due": "2026-10-16", "history": []},
        ],
    },
    {
        "id": "tomato", "type": "tomato", "plant_slug": "cherry-tomato", "nickname": "Cherry Tomato ‘Sungold’", "variety": "Sungold",
        "planted_on": "2026-08-22", "start_method": "seedling", "setting": "outdoor", "container": "Raised bed", "quantity": 1,
        "status": "flowering", "watering_interval_days": 2,
        "tip": "While it flowers, gently shake the stems each morning to help pollination, and keep the soil evenly moist.",
        "timeline": [
            {"id": "t4", "stage": "seedling", "date": "2026-08-22", "note": "Bought a 15 cm seedling and started hardening it off on the balcony.", "photo": False},
            {"id": "t5", "stage": "seedling", "date": "2026-08-29", "note": "Transplanted into the raised bed.", "photo": True},
            {"id": "t6", "stage": "vegetative", "date": "2026-09-20", "note": "Staked and pruned suckers. 45 cm tall.", "photo": True},
            {"id": "t7", "stage": "flowering", "date": "2026-10-12", "note": "First yellow flowers on the top truss.", "photo": True},
        ],
        "care": [
            {"action": "water", "amount": "1 L", "note": "", "date": "2026-10-12", "source": "reminder"},
            {"action": "water", "amount": "1 L", "note": "", "date": "2026-10-10", "source": "reminder"},
            {"action": "prune", "amount": "", "note": "Removed suckers below the first flower truss", "date": "2026-10-08", "source": "manual"},
            {"action": "fertilize", "amount": "10 ml/L", "note": "Tomato feed", "date": "2026-10-03", "source": "reminder"},
            {"action": "treat_pest", "amount": "", "note": "Soapy water spray for aphids", "date": "2026-09-17", "source": "tutor_suggestion"},
        ],
        "problems": [
            {
                "id": "p2", "title": "Aphids on new growth", "category": "pest", "severity": "low", "status": "resolved",
                "description": "Clusters of small green insects under the top leaves, a bit sticky.",
                "opened": "2026-09-15", "resolved": "2026-09-19", "resolution_note": "Sprayed with soapy water twice, 2 days apart. Gone by the 19th.", "photo": True,
                "diagnosis": {
                    "issues": [{"name": "Aphids", "confidence": "high", "reasoning": "Small green clustered insects and sticky honeydew on new growth."}],
                    "immediate_actions": ["Spray with mild soapy water, undersides too", "Repeat in 2–3 days"],
                    "watch_for": ["Curling leaves", "Ants farming the aphids"],
                },
            },
        ],
        "harvests": [],
        "reminders": [
            {"id": "r3", "type": "water", "title": "Water Cherry Tomato", "every": 2, "time": "08:00", "weather_aware": True, "active": True, "inapp": True, "email": True, "next_due": "2026-10-14",
             "history": [{"date": "2026-10-12", "status": "done"}, {"date": "2026-10-10", "status": "done"}, {"date": "2026-10-08", "status": "done"}]},
            {"id": "r4", "type": "fertilize", "title": "Feed Cherry Tomato", "every": 14, "time": "09:00", "weather_aware": False, "active": True, "inapp": True, "email": False, "next_due": "2026-10-17",
             "history": [{"date": "2026-10-03", "status": "done"}]},
            {"id": "r5", "type": "harvest_check", "title": "Check for ripe tomatoes", "every": 0, "time": "09:00", "weather_aware": False, "active": True, "inapp": True, "email": True, "next_due": "2026-11-03", "history": []},
        ],
    },
    {
        "id": "lettuce", "type": "lettuce", "plant_slug": "lettuce", "nickname": "Butterhead Lettuce", "variety": "Butterhead",
        "planted_on": "2026-09-25", "start_method": "seed", "setting": "indoor", "container": "Windowsill tray", "quantity": 6,
        "status": "sprouting", "watering_interval_days": 2,
        "tip": "Thin to one seedling every 15 cm once they have two true leaves, and keep the tray out of direct afternoon heat.",
        "timeline": [
            {"id": "t8", "stage": "seed", "date": "2026-09-25", "note": "Sowed 6 seeds, 0.5 cm deep, in a windowsill tray.", "photo": False},
            {"id": "t9", "stage": "seedling", "date": "2026-10-05", "note": "Germinated! 5 of 6 seeds are up.", "photo": True},
        ],
        "care": [
            {"action": "water", "amount": "200 ml", "note": "", "date": "2026-10-11", "source": "reminder"},
            {"action": "water", "amount": "200 ml", "note": "", "date": "2026-10-09", "source": "reminder"},
            {"action": "water", "amount": "200 ml", "note": "Misted the surface", "date": "2026-10-07", "source": "reminder"},
        ],
        "problems": [],
        "harvests": [],
        "reminders": [
            {"id": "r6", "type": "water", "title": "Water Butterhead Lettuce", "every": 2, "time": "08:00", "weather_aware": False, "active": True, "inapp": True, "email": True, "next_due": "2026-10-13",
             "history": [{"date": "2026-10-11", "status": "done"}, {"date": "2026-10-09", "status": "done"}, {"date": "2026-10-07", "status": "done"}]},
            {"id": "r7", "type": "custom", "title": "Thin lettuce seedlings", "every": 0, "time": "10:00", "weather_aware": False, "active": True, "inapp": True, "email": False, "next_due": "2026-10-17", "history": []},
        ],
    },
    {
        "id": "mint", "type": "mint", "plant_slug": "mint", "nickname": "Mint", "variety": "Spearmint",
        "planted_on": "2026-06-14", "start_method": "seedling", "setting": "outdoor", "container": "Balcony pot · 25 cm", "quantity": 1,
        "status": "producing", "watering_interval_days": 3,
        "tip": "Mint survives frost, but trim it back before the first hard freeze and it will regrow in spring.",
        "timeline": [
            {"id": "t10", "stage": "seedling", "date": "2026-06-14", "note": "Potted up a small mint plant from the market.", "photo": False},
            {"id": "t11", "stage": "vegetative", "date": "2026-07-20", "note": "Spreading fast. Moved to a bigger pot.", "photo": True},
            {"id": "t12", "stage": "harvest", "date": "2026-09-20", "note": "First harvest — 100 g for tea.", "photo": True},
        ],
        "care": [
            {"action": "prune", "amount": "", "note": "Harvest cut, back to 10 cm", "date": "2026-10-10", "source": "manual"},
            {"action": "water", "amount": "400 ml", "note": "", "date": "2026-10-08", "source": "reminder"},
            {"action": "repot", "amount": "", "note": "Moved to 25 cm pot", "date": "2026-07-20", "source": "manual"},
        ],
        "problems": [],
        "harvests": [
            {"date": "2026-10-10", "quantity": 80, "unit": "g", "note": "Mojitos!"},
            {"date": "2026-09-28", "quantity": 60, "unit": "g", "note": ""},
            {"date": "2026-09-20", "quantity": 100, "unit": "g", "note": "Fresh mint tea"},
        ],
        "reminders": [
            {"id": "r8", "type": "water", "title": "Water Mint", "every": 3, "time": "08:00", "weather_aware": True, "active": True, "inapp": True, "email": False, "next_due": "2026-10-14",
             "history": [{"date": "2026-10-11", "status": "skipped_rain", "reason": "6 mm rain"}, {"date": "2026-10-08", "status": "done"}]},
            {"id": "r9", "type": "custom", "title": "Trim mint before frost", "every": 0, "time": "17:00", "weather_aware": False, "active": True, "inapp": True, "email": True, "next_due": "2026-10-14", "history": []},
        ],
    },
    {
        "id": "spinach", "type": "spinach", "plant_slug": "spinach", "nickname": "Spinach", "variety": "Bloomsdale",
        "planted_on": "2026-10-20", "start_method": "seed", "setting": "outdoor", "container": "Raised bed", "quantity": 12,
        "status": "planned", "watering_interval_days": 2,
        "tip": "Cool weather suits spinach. Sow 1 cm deep, 5 cm apart, and it will shrug off light frosts.",
        "timeline": [], "care": [], "problems": [], "harvests": [],
        "reminders": [{"id": "r10", "type": "custom", "title": "Sow spinach", "every": 0, "time": "10:00", "weather_aware": False, "active": True, "inapp": True, "email": True, "next_due": "2026-10-20", "history": []}],
    },
    {
        "id": "cilantro", "type": "cilantro", "plant_slug": "cilantro", "nickname": "Cilantro", "variety": "",
        "planted_on": "2026-07-10", "start_method": "seed", "setting": "outdoor", "container": "Balcony pot", "quantity": 8,
        "status": "failed", "failure_reason": "other", "watering_interval_days": 2,
        "tip": "Cilantro bolts in summer heat. Try again in early spring or right now in a shady spot — it loves cool weather.",
        "timeline": [
            {"id": "t13", "stage": "seed", "date": "2026-07-10", "note": "Sowed 8 seeds in a balcony pot.", "photo": False},
            {"id": "t14", "stage": "seedling", "date": "2026-07-18", "note": "Up and growing.", "photo": True},
            {"id": "t15", "stage": "flowering", "date": "2026-08-02", "note": "Already flowering — leaves turned thin and feathery.", "photo": True},
        ],
        "care": [{"action": "water", "amount": "300 ml", "note": "", "date": "2026-07-30", "source": "reminder"}],
        "problems": [
            {
                "id": "p3", "title": "Bolting in the heat", "category": "environment", "severity": "high", "status": "resolved",
                "description": "Tall flower stalks appeared after a week above 32 °C.",
                "opened": "2026-08-02", "resolved": "2026-08-15", "resolution_note": "Plant lost. Lesson: sow cilantro in spring or fall, not mid-summer.", "photo": False,
                "diagnosis": {
                    "issues": [{"name": "Heat-triggered bolting", "confidence": "high", "reasoning": "Cilantro flowers quickly when temperatures stay above 30 °C and days are long."}],
                    "immediate_actions": ["Harvest any usable leaves now", "Let a few flowers set seed (coriander) if you like"],
                    "watch_for": ["Next time: sow in spring or fall, in partial shade"],
                },
            },
        ],
        "harvests": [],
        "reminders": [{"id": "r11", "type": "water", "title": "Water Cilantro", "every": 2, "time": "08:00", "weather_aware": True, "active": False, "inapp": True, "email": False, "next_due": "2026-08-16", "history": [{"date": "2026-08-01", "status": "done"}]}],
    },
]

