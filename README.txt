DOOMSDAY WATCH
==============
Checks BookMyShow for Avengers: Doomsday (English) night shows in Chennai,
17-27 Dec 2026, at Palazzo, Phoenix Velachery, Sathyam, Escape (Express Avenue)
and VR Mall. When a sold-out night show gets seats, or a new one appears,
your phone gets a loud alert. Tap it and BookMyShow opens on that date.

Your private alert channel: doomsday-chennai-a033e25381
(Anyone who knows this name can read your alerts, so don't post it.)


1. GET ALERTS ON YOUR PHONE (2 min)
   - Install "ntfy" from the Play Store or App Store.
   - Tap +, enter the channel name above, and subscribe.
   - Android: open the channel's settings and allow it to override
     Do Not Disturb so alerts ring.


2. RUN IT 24/7 IN THE CLOUD, FREE (10 min)
   - On github.com, create a new PUBLIC repository (public = unlimited free runs).
   - Click "uploading an existing file" and drag in every file and folder from
     this zip, INCLUDING the .github folder. Do NOT upload ntfy_topic.txt.
     (If your computer hides the .github folder: on Mac press Cmd+Shift+.
      in Finder; on Windows turn on View > Hidden items.)
   - Settings > Secrets and variables > Actions > New repository secret:
       Name:  NTFY_TOPIC
       Value: doomsday-chennai-a033e25381
   - Actions tab > enable workflows > "Doomsday Watch" > Run workflow.
     After that it runs by itself every ~5-15 minutes.
   - Phone dashboard: Settings > Pages > Source "Deploy from a branch",
     branch main, folder /docs. Open the link it gives you on your phone,
     then Share > Add to Home Screen.


3. OPTIONAL: FASTER CHECKS FROM YOUR LAPTOP
   GitHub's schedule is often 5-15 minutes late. While your laptop is on,
   double-click start-mac.command (Mac) or start-windows.bat (Windows) to
   check every ~3 minutes. Needs Python 3 installed (python.org).
   On Mac, the first time: right-click > Open, because it isn't from the App Store.

   Test that alerts reach your phone:   python3 watcher.py --test-notify


CHANGING WHAT IT WATCHES
   Edit config.json: dates, weekend_dates, theatres (name -> words to match),
   night_from. Set "alert_on_any_theatre": true to hear about every Chennai theatre.


IF BOOKMYSHOW BLOCKS IT
   After 4 failed checks in a row you get one "Doomsday watch is blind" alert,
   and the dashboard turns red. GitHub's servers are more likely to be blocked
   than your home internet, so run the laptop version if that happens.
