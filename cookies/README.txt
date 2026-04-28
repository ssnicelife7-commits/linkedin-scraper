ONE-TIME SETUP — Export your LinkedIn cookies from Opera
=========================================================

You only need to do this ONCE. After the first run, the scraper
saves your session permanently and this file is no longer needed.

STEPS
-----
1. Open Opera and make sure you are logged into your LinkedIn
   scraper account (the burner account).

2. Install the "Cookie-Editor" extension in Opera if you don't
   have it already:
   https://cookie-editor.com

3. Navigate to https://www.linkedin.com in Opera.

4. Click the Cookie-Editor icon in your toolbar.

5. Click "Export" → "Export as JSON".

6. Save the file as:
       linkedin_cookies.json
   inside this folder (cookies/).

7. Run the scraper (run_scraper.bat).
   The scraper will import all cookies into its persistent profile
   and rename this file to linkedin_cookies.json.imported.
   You will see a confirmation message in the console.

8. That's it — never export cookies again. The session is saved.


WHAT IF THE SESSION EXPIRES LATER?
-----------------------------------
If the scraper says "Session not recognised" after weeks of use,
just repeat steps 3-7 above. This should be rare if you use a
residential proxy and don't log the scraper account out manually.


SECURITY NOTE
--------------
linkedin_cookies.json contains your session credentials.
Do not share it, upload it, or commit it to Git.
(.gitignore already excludes it.)
