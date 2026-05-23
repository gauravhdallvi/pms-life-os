# PMS Life OS

Owner: Gauravh Dallvi

## What is included

- Streamlit dashboard
- SQLite database created automatically on first run
- Reminder OS with recurring fields and morning/evening views
- Follow-up engine with aging calculation and auto escalation when aging is greater than 3 days
- Communication AI assistant for tone review, leadership score, professional rewrite, risk review, and perception notes
- Perception Management weekly score engine
- Contractor Intelligence with Red / Yellow / Green traffic logic
- Boss Reporting daily summary
- Memory OS, Life OS areas, and Content System
- Excel export and Google Form CSV import

## Run

Dependency-free local version:

```powershell
.\run_pms_life_os.ps1
```

If PowerShell blocks scripts, double-click `RUN_PMS_LIFE_OS.bat` instead.

Then open:

```text
http://127.0.0.1:8501
```

Streamlit version:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run pms_life_os.py
```

Both versions create `pms_life_os.db` in this folder.

## Automation notes

The app applies the important automation rules whenever it runs:

- Task created -> reminder record
- Aging greater than 3 days -> status becomes `ESCALATE`
- Morning dashboard -> 8:30 executive summary view
- Evening review -> 9 PM reflection prompt

For true background notifications, keep the app running and connect Windows Task Scheduler, email, WhatsApp, or Google Calendar in the next phase.
