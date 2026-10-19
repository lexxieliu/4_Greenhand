1. How the data is captured :
    Weather Data : Weather (Open-Meteo), coordinates from a city or ZIP, reminder outcomes, answer ratings
    Photos       : Timeline photos, problem photos, diagnosis uploads, post images
    Free Text    : Tutor chat messages, timeline notes, problem descriptions, posts and comments
    Structured forms : Onboarding (location, space type, sunlight, experience), Start Growing (plant, planting date, seed or seedling, indoor or outdoor), care logs (“Watered ✓”), harvest quantity and unit
2. Cleaning data before it reaches the LLM
    At entry (Django forms and DRF serializers):
        - Choice fields only accept allowed values.
        - Dates are sanity-checked, so a planting date can’t be in the future.
        - Length caps: chat messages up to 2,000 characters, notes up to 1,000.
   
    Text cleaning:
        - Strip HTML (with the bleach library) and normalize Unicode.
        - Remove invisible characters, such as zero-width and control characters, that are often used to hide injected instructions.
        - Collapse repeated whitespace.
        - Mask emails and phone numbers before the text goes to the LLM.

    Photos:
        - Confirm the file is really an image by opening it with Pillow, and convert iPhone HEIC photos to JPEG.
        - Fix the orientation, then remove EXIF data, which includes GPS location.
        - Resize to at most about 1,600 px on the longest side.
        - Reject blurry photos (simple sharpness check) and ask the user to retake them.

3. Safety guardrails

    Blocking malicious input
      - Limits: rate limits per user (50 tutor messages and 10 photo diagnoses a day), upload limits (images only, up to 10 MB), and length caps.
      - Prompt injection:
      - Wrap all user text, retrieved excerpts and community posts in tags.
      - The system prompt says that anything inside those tags is data, never instructions.
      - Contain the damage:
      - The context only ever contains that user’s own data, so even a successful injection can’t leak anyone else’s information.
      - The model can’t take actions by itself. It can only suggest actions, like creating a reminder. The server then checks each suggestion against an allowed list (“create a reminder for a plant this user owns”) before showing a confirm button.
      - Moderation check: a fast moderation model or API screens messages for abuse or self-harm. Off-topic requests get a friendly redirect back to gardening. Photos are screened for inappropriate content.

    Handling broken or harmful output
    Structured output with validation:
      - Diagnoses and suggested actions must come back as JSON and are checked against a schema.
      - If the check fails, retry once and include the error. If it fails again, fall back to a plain-text answer.

    Truncated or failed calls:
      - Detect replies that hit the length limit and were cut off.
      - Time out after 30 seconds, retry with increasing delays, then show a friendly error or cached tips.
      - Never save half-written diagnoses.
    Safe display: 
      - sanitize the model’s markdown before showing it, so it can’t inject HTML or scripts. Only allow links to approved domains.
    Domain safety rules:
      - Warn about toxic plant parts, such as tomato and potato leaves.
      - Never suggest mixing chemicals; always say to follow the pesticide label.
      - Refuse to identify wild plants or mushrooms as safe to eat.
      - For serious issues, point users to their local agricultural extension office.
      - A post-check that looks for dangerous terms adds a warning or blocks the reply.
    Honesty about uncertainty:
      - Every diagnosis shows a confidence level. Low confidence means asking for another photo.
      - Answers say which plant guide they came from.
      - Everything the AI writes is labeled as AI.
    Monitoring:
      - Log the exact context sent with each message (already planned as context_snapshot in the database).
      - Review answers users rate 👎 and flagged replies.
      - Keep a test set of about 100 gardening questions and injection attempts, and run it automatically (in CI) before any prompt or model change.