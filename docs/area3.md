# Area 3: weather, reminders, calendar and notifications

Implemented on `yidan2`, starting at local `newDev` (`593b63f`). The pre-existing
`yidan` branch and the original working directory/database are unchanged.

## Run locally

Use Python 3.12+ and the project's existing requirements. For an Area 3-only
environment, Django 6.1.1 and django-environ 0.14.0 are sufficient. The complete
unit suite also needs NumPy 2.5.3; model weights are not needed for these tests.

Set `SECRET_KEY` in the environment (or use the project's `.env` mechanism), then:

```sh
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Sign in with an existing account's unique email and password. Visit:

- `/weather/setup/`: add city-level coordinates and IANA timezone, then associate
  each existing garden plant with its location, indoor/outdoor setting and frost threshold.
- `/calendar/reminders/new/`: create a one-time, daily or weekly care reminder.
- `/calendar/`: month navigation, garden/plant filters, manual lifecycle events,
  Done, Skip, Restore task and Pause actions.
- `/weather/`: cached current conditions, local seven-day temperatures, active
  alerts, acknowledgement, and explicit missing/stale data states.
- `/notifications/` and `/notifications/settings/`: persisted read state,
  timezone, email preferences, quiet hours and optional weekly digest.
- `/garden/`: weather summary, actual plant weather badges, today's occurrences
  and persisted calendar events. Other dashboard panels remain the existing demo.

Fetch initial data and process tasks explicitly during local development:

```sh
python manage.py refresh_weather
python manage.py process_reminders
python manage.py send_notifications
python manage.py send_weekly_digest
```

These commands do not install a scheduler or start a worker. No user emails were
sent during implementation/testing. Development's default email backend prints
messages to the console; configure SMTP to deliver actual mail.

## Scheduling decision

Use management commands plus cron for this MVP. No Redis/Celery deployment or new
runtime dependency is necessary. Database snapshots provide the shared, durable
three-hour location cache. This is deliberately a **single-host Linux/macOS** job
runner: all four commands share a nonblocking `flock` on `data/area3.lock` so cron
cannot overlap SQLite writes or email workers. A competing command exits nonzero
and must retry. Example crontab (server timezone UTC; adapt paths and logging):

```cron
*/15 * * * * cd /srv/greenhand && .venv/bin/python manage.py process_reminders >> /var/log/greenhand-reminders.log 2>&1
5 */3 * * * cd /srv/greenhand && .venv/bin/python manage.py refresh_weather >> /var/log/greenhand-weather.log 2>&1
10 8 * * 1 cd /srv/greenhand && .venv/bin/python manage.py send_weekly_digest >> /var/log/greenhand-digest.log 2>&1
```

`process_reminders` also flushes queued emails, so frost notifications generated
by the weather command are delivered at the next 15-minute tick. The digest
command creates at most one digest per recipient's local ISO week; delivery
still respects local quiet hours and the daily cap. Monitor exit codes/logs.
For multiple scheduler hosts or Windows, replace the local lock with a distributed
scheduler/lock before enabling concurrent workers.

## Data and integration boundaries

The repository currently calls individual user plants `garden.Garden`, not
`UserPlant`. New models reference that existing table. `weather.Location` and
`PlantWeatherSettings` supply the missing per-plant weather metadata without
renaming the models owned by other work areas. `NotificationPreference` holds
timezone and delivery preferences because the existing Profile lacks them.
A minimal `garden.CareLog` is created exactly once when a plant reminder is Done;
`ReminderOccurrence.care_log` links it. Reconcile these models with the other
areas when their richer Location/Profile/CareLog implementations land.

The existing sign-in stub did not authenticate. Login/logout now use Django
sessions; sign-up/onboarding and the mock My Garden editor are still owned by
Area 1/2. New accounts/plants must exist in the database (Django shell/admin or
the owning area's implementation) before they can be selected here. There is no
migration that copies mock demo plants into users' gardens.

Other areas can create CalendarEvent records with an icon and `source_type` +
`source_id`; that pair prevents duplicate source events. The month view combines
stored events with a read-only recurrence projection, including months beyond
the background job's 35-day materialization horizon. Automatic stage-based task
regeneration belongs to the garden lifecycle integration and is not installed
as implicit signals here.

## Rules and time behavior

- Open-Meteo receives only coordinates rounded to 0.1 degrees. Calls for the same
  rounded location share one snapshot, even across users and location timezones.
  The adapter requests UTC hourly data, uses exact 24h/12h/48h windows, sums rain
  plus showers (excluding snow), and validates missing/nonfinite data. An eight-
  second timeout or malformed response falls back to the latest stored snapshot.
- Cached data older than three hours is labeled stale and never triggers a new
  automatic skip or weather alert. No cached data produces an explicit empty state.
- Outdoor, weather-aware watering skips at rain >=5 mm/24h **or** probability
  >=70%/12h, only on the occurrence's plant-local date. Indoor plants skip all
  outdoor rules. Frost-sensitive outdoor plants alert at their threshold
  (default 2 C) within 48h; heat starts at 32 C. Terminal garden plants are excluded
  from scheduled weather evaluation.
- Alert and notification keys prevent duplicates on retries. Restore task logs
  the previous skip, actor, reason and timestamp and marks the alert overridden;
  subsequent weather jobs cannot skip that occurrence again.
- RRULE supports DAILY/WEEKLY with INTERVAL (1–365), or blank for a one-time task.
  Unsupported RRULE options fail validation rather than being silently ignored.
  UTC due times are computed from the reminder's saved IANA timezone and local
  clock: spring gaps move to the first valid minute, autumn folds fire once.
  The form defaults to the user's notification timezone. Changing preferences
  does not silently reschedule existing reminders.
- Tasks over 24 hours late are marked missed on catch-up. Sent means the in-app
  reminder was generated; email delivery is tracked separately on Notification.

## Email configuration and limits

Configure `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`,
`EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`,
`DEFAULT_FROM_EMAIL`, and the public HTTPS `SITE_URL`. Never commit SMTP credentials.
SMTP timeout is ten seconds. Configure SPF/DKIM with the deployment provider.

Notifications remain in-app during quiet hours (default 21:00–07:00). Email is
queued until eligible. Frost can bypass quiet hours unless disabled. At most
three emails are accepted by the backend per recipient-local day, prioritizing
frost, reminders, then digest. Social/system/non-frost weather alerts are in-app
only. Completed/skipped occurrences do not send queued ordinary reminder emails.
Preferences and plant suppression are rechecked before each send.

Every care email has signed no-login links for plant/all suppression. GET is a
confirmation page; POST suppresses email and preserves in-app tasks. Digest has
separate opt-in (off by default), signed unsubscribe, List-Unsubscribe headers,
and requires `EMAIL_POSTAL_ADDRESS` before delivery. The supplied revised PRD
places digest after MVP; it is included here because the task explicitly asks
for it. No product-update or web-push delivery is implemented.

Successful sends record `emailed_at`; failures remain retryable. Database dedupe
and the shared job lock prevent ordinary retry/concurrency duplicates. SMTP
cannot guarantee exactly-once delivery if a worker dies after the provider
accepts a message but before the database commits. A production provider with
idempotency keys is needed to close that crash window.

## Verification

```sh
python manage.py check
python manage.py makemigrations weather calendar_app garden notifications --check --dry-run
python manage.py test --noinput
coverage run --source=weather,calendar_app,notifications manage.py test weather calendar_app notifications --noinput
coverage report --omit='*/tests.py,*/test_helpers.py,*/migrations/*'
ruff check --isolated --select E4,E7,E9,F,I weather calendar_app notifications
```

40 Area 3 tests and 71 total tests passed. Core Area 3 coverage (excluding tests,
fixtures and migrations) is 95%. Coverage
covers actual hourly parsing, fallback, threshold boundaries, indoor/tolerant
plants, per-date skips, retries, override persistence, DST, one-time/recurring
reminders, care-log idempotency, month projection, user ownership, signed
unsubscribe, quiet hours, caps, failed mail retries, digest opt-in, commands and
job locks. Fresh-database migrations, browser login/restore/done/notification
flow and a live Open-Meteo city-coordinate request were verified separately.

Repository-wide `makemigrations --check` also reports an existing unrelated
Profile.user related-name drift (`userprofile`); it is not introduced or migrated
by Area 3. SMTP delivery to a real provider and an installed production cron
schedule require deployment configuration and were not exercised.

Provider field reference: https://open-meteo.com/en/docs
