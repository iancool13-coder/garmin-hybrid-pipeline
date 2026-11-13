import os
import json
import base64
from datetime import datetime, timedelta
from fpdf import FPDF
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "garmin_state.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
PDF_FILE = os.path.join(BASE_DIR, "Training_Plan_Week1.pdf")
HTML_FILE = os.path.join(BASE_DIR, "docs", "index.html")

def generate_web_dashboard(training_plan, sync_stats=None):
    os.makedirs(os.path.dirname(HTML_FILE), exist_ok=True)
    meta = training_plan.get("_meta", {})
    telemetry = meta.get("telemetry", {})
    sync_stats = sync_stats or {}
    hm_sec = meta.get("hm_seconds", 7070)
    hrs, rem = divmod(hm_sec, 3600)
    mins, secs = divmod(rem, 60)
    proj_hm = f"{hrs}:{mins:02d}:{secs:02d}"

    cards_html = ""
    for day, data in training_plan.items():
        if day.startswith("_"):
            continue
        is_run = data["type"] == "run"
        badge = "GARMIN RUN" if is_run else "HOME LIFT"
        accent = "#3b82f6" if is_run else "#f59e0b"
        pace_line = f"<div class=\"pace\">Target Pace: {data['target_pace']}</div>" if is_run else "<div class=\"pace lift-note\">Power Rack • 225 lb Barbell • Landmine</div>"
        cards_html += f"""
        <div class="card" style="border-left: 4px solid {accent};">
            <div class="card-top">
                <div>
                    <span class="day">{day}</span>
                    <span class="badge" style="background:{accent};">{badge}</span>
                </div>
                <span class="dist" style="color:{accent};">{data.get("distance_label", "")}</span>
            </div>
            <h3>{data["title"]}</h3>
            <p>{data["description"]}</p>
            {pace_line}
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hybrid Sub-2:00 Dashboard</title>
<style>
  :root {{ --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --muted: #94a3b8; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 16px; }}
  .container {{ max-width: 820px; margin: 0 auto; }}
  header {{ background: #111827; padding: 20px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 16px; }}
  header h1 {{ margin: 0 0 6px; font-size: 1.35rem; }}
  header .sub {{ color: var(--muted); font-size: 0.85rem; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin-bottom: 18px; }}
  .kpi {{ background: var(--card); padding: 14px; border-radius: 10px; border: 1px solid #334155; }}
  .kpi .lbl {{ font-size: 0.7rem; font-weight: 700; color: #60a5fa; letter-spacing: 0.05em; }}
  .kpi .val {{ font-size: 1.25rem; font-weight: 700; margin: 4px 0; }}
  .kpi .det {{ font-size: 0.78rem; color: var(--muted); }}
  .card {{ background: var(--card); padding: 16px; border-radius: 10px; margin-bottom: 12px; border: 1px solid #334155; }}
  .card-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
  .day {{ font-weight: 700; font-size: 0.95rem; margin-right: 8px; }}
  .badge {{ font-size: 0.68rem; font-weight: 700; padding: 3px 7px; border-radius: 4px; color: #fff; }}
  .dist {{ font-weight: 700; font-size: 0.85rem; }}
  .card h3 {{ margin: 4px 0 6px; font-size: 1.05rem; }}
  .card p {{ margin: 0 0 8px; color: #cbd5e1; font-size: 0.9rem; line-height: 1.4; }}
  .pace {{ font-size: 0.85rem; font-weight: 600; color: #60a5fa; }}
  .lift-note {{ color: #fbbf24; }}
  footer {{ text-align: center; color: var(--muted); font-size: 0.78rem; margin-top: 20px; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Hybrid Performance & Sub-2:00 Dashboard</h1>
    <div class="sub">Updated {datetime.now().strftime("%b %d, %Y at %I:%M %p")} • {meta.get("source", "Baseline")}</div>
  </header>
  <div class="kpis">
    <div class="kpi"><div class="lbl">PROJECTED HM</div><div class="val">{proj_hm}</div><div class="det">Target: &lt; 2:00:00</div></div>
    <div class="kpi"><div class="lbl">7D LOGGED / PLAN</div><div class="val">{telemetry.get("weekly_miles", "0.0 mi")} / 21 mi</div><div class="det">{telemetry.get("weekly_runs", 0)} runs logged (7d)</div></div>
    <div class="kpi"><div class="lbl">WATCH VO2 MAX</div><div class="val">{telemetry.get("vo2_max", "N/A")}</div><div class="det">Forerunner 165</div></div>
    <div class="kpi"><div class="lbl">RESTING HR</div><div class="val">{telemetry.get("rhr", "N/A")}</div><div class="det">+{sync_stats.get("scheduled", 0)} new / {sync_stats.get("skipped", 0)} active</div></div>
  </div>
  {cards_html}
  <footer>Auto-synced every Sunday 8:00 PM AST via GitHub Actions</footer>
</div>
</body>
</html>"""
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print("Web dashboard generated at docs/index.html")


# Decode GitHub Actions Secrets into local temp files when running in the cloud
if os.environ.get("GARMIN_STATE_B64"):
    with open(STATE_FILE, "wb") as f:
        f.write(base64.b64decode(os.environ["GARMIN_STATE_B64"]))

if os.environ.get("GOOGLE_TOKEN_B64"):
    with open(TOKEN_FILE, "wb") as f:
        f.write(base64.b64decode(os.environ["GOOGLE_TOKEN_B64"]))

print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] >>> STARTING ADAPTIVE HYBRID PIPELINE <<<")

creds = None
if os.path.exists(TOKEN_FILE):
    creds = Credentials.from_authorized_user_file(TOKEN_FILE)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

def min_km_to_ms(min_per_km):
    return round(1000.0 / (min_per_km * 60.0), 4)

def fmt_pace_both(min_per_km):
    km_m = int(min_per_km)
    km_s = int(round((min_per_km - km_m) * 60))
    if km_s == 60:
        km_m += 1
        km_s = 0
    min_per_mi = min_per_km * 1.60934
    mi_m = int(min_per_mi)
    mi_s = int(round((min_per_mi - mi_m) * 60))
    if mi_s == 60:
        mi_m += 1
        mi_s = 0
    return f"{km_m}:{km_s:02d}/km ({mi_m}:{mi_s:02d}/mi)"

def vo2max_to_hm_seconds(vo2):
    estimated_sec = 7080 - ((vo2 - 46.0) * 172.0)
    return max(4200, min(9000, int(estimated_sec)))

def get_dynamic_plan(half_marathon_seconds=7070, source_label="Baseline (1:57:50 HM)", telemetry=None):
    base_min_per_km = (half_marathon_seconds / 21.0975) / 60.0

    fartlek_pace = round(base_min_per_km * 0.95, 2)
    base_pace = round(base_min_per_km * 1.12, 2)
    recovery_pace = round(base_min_per_km * 1.22, 2)
    long_pace = round(base_min_per_km * 1.08, 2)

    return {
        "_meta": {
            "hm_seconds": half_marathon_seconds,
            "source": source_label,
            "base_min_km": round(base_min_per_km, 2),
            "telemetry": telemetry or {}
        },
        "Monday": {
            "weekday": 0,
            "type": "run",
            "title": "Sub-2:00 Fartlek Intervals",
            "distance_label": "6.0 mi (9.7 km)",
            "description": "10 min easy warmup | 6 miles Fartlek surge intervals | 5 min cooldown",
            "target_pace": fmt_pace_both(fartlek_pace),
            "distance_m": 9656.0,
            "pace_ms_low": min_km_to_ms(fartlek_pace + 0.15),
            "pace_ms_high": min_km_to_ms(fartlek_pace - 0.15)
        },
        "Tuesday": {
            "weekday": 1,
            "type": "lift",
            "title": "Lower Body Power (Rack & Landmine)",
            "distance_label": "45 min Strength",
            "description": (
                "Barbell Back Squats: Warmup + 3x5 @ RPE 8 (225 lb rack)  |  "
                "Landmine RDLs: 3x8-10/leg  |  Plank / Pallof Press: 3x45s"
            )
        },
        "Wednesday": {
            "weekday": 2,
            "type": "run",
            "title": "Sub-2:00 Aerobic Base + Strides",
            "distance_label": "4.0 mi (6.4 km)",
            "description": "4 miles steady aerobic Zone 2 base + 4x100m neuromuscular strides",
            "target_pace": fmt_pace_both(base_pace),
            "distance_m": 6437.0,
            "pace_ms_low": min_km_to_ms(base_pace + 0.15),
            "pace_ms_high": min_km_to_ms(base_pace - 0.15)
        },
        "Thursday": {
            "weekday": 3,
            "type": "lift",
            "title": "Upper Body & Back (Pull-Up Bar & Landmine)",
            "distance_label": "45 min Strength",
            "description": (
                "Pull-Ups (Power Rack): 3xMax (2 RIR)  |  "
                "Landmine Single-Arm Press: 3x8/arm  |  Barbell Bent-Over Rows: 4x6-8"
            )
        },
        "Friday": {
            "weekday": 4,
            "type": "run",
            "title": "Sub-2:00 Active Recovery Jog",
            "distance_label": "3.0 mi (4.8 km)",
            "description": "3 miles conversational recovery flush (strictly easy effort)",
            "target_pace": fmt_pace_both(recovery_pace),
            "distance_m": 4828.0,
            "pace_ms_low": min_km_to_ms(recovery_pace + 0.20),
            "pace_ms_high": min_km_to_ms(recovery_pace - 0.15)
        },
        "Saturday": {
            "weekday": 5,
            "type": "lift",
            "title": "Core Rotational Power & Mobility",
            "distance_label": "30 min Recovery",
            "description": (
                "Landmine Russian Twists: 3x15/side  |  "
                "Hip Flexor Release, Thoracic Opener & Dynamic Flow (15 min)"
            )
        },
        "Sunday": {
            "weekday": 6,
            "type": "run",
            "title": "Sub-2:00 Endurance Long Run",
            "distance_label": "8.0 mi (12.9 km)",
            "description": "8 miles steady-state aerobic endurance builder",
            "target_pace": fmt_pace_both(long_pace),
            "distance_m": 12875.0,
            "pace_ms_low": min_km_to_ms(long_pace + 0.15),
            "pace_ms_high": min_km_to_ms(long_pace - 0.15)
        }
    }

def build_garmin_workout_payload(run_data, workout_id=None):
    payload = {
        "sportType": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
        "subSportType": None,
        "workoutName": run_data["title"],
        "description": f"{run_data['description']} ({run_data['target_pace']})",
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "sportType": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
                "workoutSteps": [
                    {
                        "type": "ExecutableStepDTO",
                        "stepId": None,
                        "stepOrder": 1,
                        "stepType": {"stepTypeId": 1, "stepTypeKey": "warmup", "displayOrder": 1},
                        "childStepId": None,
                        "description": "10 min Easy Warmup",
                        "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True},
                        "endConditionValue": 600.0,
                        "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}
                    },
                    {
                        "type": "ExecutableStepDTO",
                        "stepId": None,
                        "stepOrder": 2,
                        "stepType": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
                        "childStepId": None,
                        "description": run_data["description"],
                        "endCondition": {"conditionTypeId": 3, "conditionTypeKey": "distance", "displayOrder": 3, "displayable": True},
                        "endConditionValue": run_data["distance_m"],
                        "targetType": {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone", "displayOrder": 6},
                        "targetValueOne": run_data["pace_ms_low"],
                        "targetValueTwo": run_data["pace_ms_high"]
                    },
                    {
                        "type": "ExecutableStepDTO",
                        "stepId": None,
                        "stepOrder": 3,
                        "stepType": {"stepTypeId": 2, "stepTypeKey": "cooldown", "displayOrder": 2},
                        "childStepId": None,
                        "description": "5 min Easy Cooldown",
                        "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True},
                        "endConditionValue": 300.0,
                        "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}
                    }
                ]
            }
        ]
    }
    if workout_id:
        payload["workoutId"] = workout_id
    return payload

def fetch_live_fitness_and_telemetry(page, prefix, headers):
    telemetry = {
        "vo2_max": "N/A",
        "rhr": "N/A",
        "weekly_miles": "0.0 mi",
        "weekly_runs": 0
    }
    hm_seconds = 7070
    source_label = "Default Baseline (1:57:50 HM)"
    found_race = False

    act_res = page.evaluate(
        """async ({prefix, headers}) => {
            const reqHeaders = Object.assign({'Accept': 'application/json'}, headers);
            const r = await fetch(`${prefix}/activitylist-service/activities/search/activities?activityType=running&limit=25`, {
                method: 'GET', headers: reqHeaders, credentials: 'include'
            });
            return {status: r.status, body: await r.text()};
        }""",
        {"prefix": prefix, "headers": headers}
    )

    seven_days_ago = datetime.now() - timedelta(days=7)
    weekly_meters = 0.0
    weekly_run_count = 0

    if act_res["status"] == 200:
        activities = json.loads(act_res["body"])
        for act in activities:
            dist_m = act.get("distance") or 0
            dur_s = act.get("duration") or 0
            start_local = act.get("startTimeLocal") or ""
            if start_local:
                try:
                    act_dt = datetime.strptime(start_local[:19], "%Y-%m-%d %H:%M:%S")
                    if act_dt >= seven_days_ago:
                        weekly_meters += dist_m
                        weekly_run_count += 1
                except Exception:
                    pass

            if not found_race:
                name = (act.get("activityName") or "").lower()
                event_type = (act.get("eventType", {}) or {}).get("typeKey", "")
                is_race = (event_type == "race") or any(k in name for k in ["21k", "half", "10k", "5k", "race", "marathon", "lola"])

                if 20800 <= dist_m <= 21500 and dur_s > 3600:
                    mins, secs = divmod(int(dur_s), 60)
                    hrs, mins = divmod(mins, 60)
                    hm_seconds = int(dur_s)
                    source_label = f"Live Race ({act.get('activityName')}: {hrs}:{mins:02d}:{secs:02d})"
                    found_race = True
                elif is_race and 4800 <= dist_m <= 10500 and dur_s > 900:
                    equiv_hm = int(dur_s * ((21097.5 / dist_m) ** 1.06))
                    mins, secs = divmod(equiv_hm, 60)
                    hrs, mins = divmod(mins, 60)
                    hm_seconds = equiv_hm
                    source_label = f"Scaled Race ({act.get('activityName')} -> {hrs}:{mins:02d}:{secs:02d})"
                    found_race = True

    telemetry["weekly_miles"] = f"{round(weekly_meters / 1609.34, 1)} mi"
    telemetry["weekly_runs"] = weekly_run_count

    today_str = datetime.now().strftime("%Y-%m-%d")
    vo2_res = page.evaluate(
        """async ({prefix, headers, todayStr}) => {
            const reqHeaders = Object.assign({'Accept': 'application/json'}, headers);
            const r = await fetch(`${prefix}/metrics-service/metrics/maxmet/latest/${todayStr}`, {
                method: 'GET', headers: reqHeaders, credentials: 'include'
            });
            return {status: r.status, body: await r.text()};
        }""",
        {"prefix": prefix, "headers": headers, "todayStr": today_str}
    )

    if vo2_res["status"] == 200 and vo2_res["body"]:
        try:
            vo2_data = json.loads(vo2_res["body"])
            if isinstance(vo2_data, list) and vo2_data:
                vo2_data = vo2_data[0]
            generic = vo2_data.get("generic") or {}
            vo2_val = generic.get("vo2MaxPreciseValue") or generic.get("vo2MaxValue")
            if vo2_val:
                telemetry["vo2_max"] = f"{round(float(vo2_val), 1)}"
                if not found_race:
                    hm_seconds = vo2max_to_hm_seconds(float(vo2_val))
                    source_label = f"Watch VO2 Max ({telemetry['vo2_max']})"
        except Exception:
            pass

    rhr_res = page.evaluate(
        """async ({prefix, headers, todayStr}) => {
            const reqHeaders = Object.assign({'Accept': 'application/json'}, headers);
            const r = await fetch(`${prefix}/userstats-service/wellness/daily/${todayStr}?fromDate=${todayStr}&untilDate=${todayStr}`, {
                method: 'GET', headers: reqHeaders, credentials: 'include'
            });
            return {status: r.status, body: await r.text()};
        }""",
        {"prefix": prefix, "headers": headers, "todayStr": today_str}
    )
    if rhr_res["status"] == 200 and rhr_res["body"]:
        try:
            rhr_data = json.loads(rhr_res["body"])
            if isinstance(rhr_data, list) and rhr_data:
                rhr_data = rhr_data[0]
            rhr_val = rhr_data.get("restingHeartRate")
            if rhr_val:
                telemetry["rhr"] = f"{rhr_val} bpm"
        except Exception:
            pass

    return hm_seconds, source_label, telemetry

def sanitize_pdf_text(text):
    return (
        str(text)
        .replace("—", "-")
        .replace("–", "-")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("→", "->")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )

def generate_pdf(training_plan, sync_stats=None):
    meta = training_plan.get("_meta", {})
    telemetry = meta.get("telemetry", {})
    sync_stats = sync_stats or {}

    hm_sec = meta.get("hm_seconds", 7070)
    hrs, rem = divmod(hm_sec, 3600)
    mins, secs = divmod(rem, 60)
    proj_hm_str = f"{hrs}:{mins:02d}:{secs:02d}"

    pdf = FPDF(orientation="P", unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # --- Top Executive Header Banner ---
    pdf.set_fill_color(17, 24, 39)
    pdf.rect(10, 10, 195.9, 24, "F")

    pdf.set_xy(14, 13)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(130, 7, "HYBRID PERFORMANCE & SUB-2:00 DASHBOARD", ln=False)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(96, 165, 250)
    pdf.cell(57.9, 7, f"SYNCED: {datetime.now().strftime('%b %d, %Y').upper()}", align="R", ln=True)

    pdf.set_x(14)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(209, 213, 219)
    cal_text = sanitize_pdf_text(f"Calibration: {meta.get('source', 'Baseline')}  |  4-Day Run + 3-Day Home Strength Split")
    pdf.cell(187.9, 6, cal_text, ln=True)

    # --- 4-Column Live Telemetry & KPI Strip ---
    kpis = [
        ("PROJECTED HM", proj_hm_str, "Goal: < 2:00:00", (22, 101, 52), (240, 253, 244)),
        ("PLANNED / 7D ACTUAL", f"21.0 mi / {telemetry.get('weekly_miles', '0.0 mi')}", f"{telemetry.get('weekly_runs', 0)} runs logged (7d)", (30, 64, 175), (239, 246, 255)),
        ("WATCH VO2 MAX", str(telemetry.get("vo2_max", "N/A")), "Garmin Forerunner 165", (107, 33, 168), (250, 245, 255)),
        ("RESTING HR / SYNC", f"{telemetry.get('rhr', 'N/A')}", f"+{sync_stats.get('scheduled', 0)} new / {sync_stats.get('skipped', 0)} active", (146, 64, 14), (255, 251, 235)),
    ]

    card_w = 46.7
    gap = 3.0
    y_kpi = 37
    for idx, (label, val, sub, accent_rgb, bg_rgb) in enumerate(kpis):
        x = 10 + idx * (card_w + gap)
        pdf.set_fill_color(*bg_rgb)
        pdf.set_draw_color(*accent_rgb)
        pdf.set_line_width(0.3)
        pdf.rect(x, y_kpi, card_w, 19, "DF")

        pdf.set_xy(x + 2.5, y_kpi + 2)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*accent_rgb)
        pdf.cell(card_w - 5, 4, sanitize_pdf_text(label), ln=True)

        pdf.set_x(x + 2.5)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(17, 24, 39)
        pdf.cell(card_w - 5, 6, sanitize_pdf_text(val), ln=True)

        pdf.set_x(x + 2.5)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(75, 85, 99)
        pdf.cell(card_w - 5, 4, sanitize_pdf_text(sub), ln=True)

    # --- Section Header ---
    y_curr = 60
    pdf.set_xy(10, y_curr)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(31, 41, 55)
    pdf.cell(120, 6, "WEEKLY ROLLING SCHEDULE (AUTO-SYNCED TO GARMIN CONNECT)", ln=False)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(75.9, 6, "Equipment: Power Rack, 225 lb Barbell, Landmine", align="R", ln=True)

    y_curr += 7
    row_h = 26.5

    for day, data in training_plan.items():
        if day.startswith("_"):
            continue
        is_run = data["type"] == "run"

        if is_run:
            bg = (248, 250, 252)
            border = (59, 130, 246)
            badge_bg = (37, 99, 235)
            badge_txt = "GARMIN RUN"
        else:
            bg = (252, 250, 248)
            border = (217, 119, 6)
            badge_bg = (180, 83, 9)
            badge_txt = "HOME LIFT"

        pdf.set_fill_color(*bg)
        pdf.set_draw_color(209, 213, 219)
        pdf.set_line_width(0.25)
        pdf.rect(10, y_curr, 195.9, row_h, "DF")

        # Left accent stripe
        pdf.set_fill_color(*border)
        pdf.rect(10, y_curr, 2.5, row_h, "F")

        # Day + Badge
        pdf.set_xy(15, y_curr + 2.5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(17, 24, 39)
        pdf.cell(26, 5.5, day.upper(), ln=False)

        pdf.set_fill_color(*badge_bg)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(23, 5, badge_txt, align="C", fill=True, ln=False)

        # Workout Title
        pdf.set_xy(67, y_curr + 2.5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(17, 24, 39)
        pdf.cell(92, 5.5, sanitize_pdf_text(data["title"]), ln=False)

        # Right-side Distance / Duration Pill
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*badge_bg)
        pdf.cell(43.9, 5.5, sanitize_pdf_text(data.get("distance_label", "")), align="R", ln=True)

        # Description line
        pdf.set_xy(15, y_curr + 9.5)
        pdf.set_font("Helvetica", "", 8.8)
        pdf.set_text_color(55, 65, 81)
        pdf.cell(187, 5, sanitize_pdf_text(data["description"]), ln=True)

        # Target Pace / Status line
        pdf.set_xy(15, y_curr + 16.5)
        if is_run:
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(29, 78, 216)
            pdf.cell(125, 5, sanitize_pdf_text(f"Target Pace Zone: {data['target_pace']}"), ln=False)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(22, 101, 52)
            pdf.cell(62, 5, "Status: Pushed to Watch Calendar", align="R", ln=True)
        else:
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(120, 53, 15)
            pdf.cell(187, 5, "Focus: Force production, posterior chain resilience & injury prevention", ln=True)

        y_curr += row_h + 2.2

    # --- Footer ---
    pdf.set_xy(10, 268)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(195.9, 4, "Automated via GitHub Actions Cloud Pipeline  |  Next Scheduled Recalibration: Sunday 8:00 PM AST", align="C")

    pdf.output(PDF_FILE)
    print(f"Upgraded Dashboard PDF generated successfully (Calibration: {meta.get('source')}).")

def run_pipeline():
    if not os.path.exists(STATE_FILE):
        print("ERROR: garmin_state.json missing.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            storage_state=STATE_FILE,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        captured = {"prefix": None, "headers": {}}
        allowed_keys = {"connect-csrf-token", "nk", "x-app-ver", "x-lang", "di-backend", "authorization"}

        def capture_request(request):
            if "connect.garmin.com" in request.url and ("/gc-api/" in request.url or "/modern/proxy/" in request.url):
                hdrs = request.headers
                if any(k in hdrs for k in ["authorization", "connect-csrf-token", "di-backend"]):
                    if "/gc-api/" in request.url:
                        captured["prefix"] = "https://connect.garmin.com/gc-api"
                    elif "/modern/proxy/" in request.url:
                        captured["prefix"] = "https://connect.garmin.com/modern/proxy"
                    for k, v in hdrs.items():
                        if k.lower() in allowed_keys:
                            captured["headers"][k.lower()] = v

        page.on("request", capture_request)

        try:
            page.goto("https://connect.garmin.com/app/calendar")
            page.wait_for_timeout(7000)

            if "signin" in page.url or "sso" in page.url:
                print("ALERT: Garmin session expired. Re-run locally once and update GARMIN_STATE_B64 secret.")
                return

            if not captured["prefix"]:
                captured["prefix"] = "https://connect.garmin.com/gc-api"

            hm_seconds, source_label, telemetry = fetch_live_fitness_and_telemetry(page, captured["prefix"], captured["headers"])
            print(f"Fitness Calibration -> {source_label} | Telemetry -> {telemetry}")
            training_plan = get_dynamic_plan(hm_seconds, source_label, telemetry)

            existing_res = page.evaluate(
                """async ({prefix, headers}) => {
                    const reqHeaders = Object.assign({'Accept': 'application/json', 'Content-Type': 'application/json'}, headers);
                    const r = await fetch(`${prefix}/workout-service/workouts?start=1&limit=50`, {
                        method: 'GET', headers: reqHeaders, credentials: 'include'
                    });
                    return {status: r.status, body: await r.text()};
                }""",
                {"prefix": captured["prefix"], "headers": captured["headers"]}
            )

            existing_map = {}
            if existing_res["status"] == 200:
                for w in json.loads(existing_res["body"]):
                    existing_map[w.get("workoutName")] = w.get("workoutId")
            else:
                print(f"Workouts list check returned status {existing_res['status']}")
                return

            workout_ids = {}
            for day_name, data in training_plan.items():
                if day_name.startswith("_") or data["type"] != "run":
                    continue
                title = data["title"]
                if title in existing_map:
                    w_id = existing_map[title]
                    payload = build_garmin_workout_payload(data, workout_id=w_id)
                    upd_res = page.evaluate(
                        """async ({prefix, headers, workoutId, payload}) => {
                            const reqHeaders = Object.assign({'Accept': 'application/json', 'Content-Type': 'application/json'}, headers);
                            const r = await fetch(`${prefix}/workout-service/workout/${workoutId}`, {
                                method: 'PUT', headers: reqHeaders, credentials: 'include', body: JSON.stringify(payload)
                            });
                            return {status: r.status, body: await r.text()};
                        }""",
                        {"prefix": captured["prefix"], "headers": captured["headers"], "workoutId": w_id, "payload": payload}
                    )
                    workout_ids[data["weekday"]] = w_id
                    print(f"  [TEMPLATE] Updated '{title}' (ID: {w_id}) -> {data['target_pace']} (Status {upd_res['status']})")
                else:
                    payload = build_garmin_workout_payload(data)
                    create_res = page.evaluate(
                        """async ({prefix, headers, payload}) => {
                            const reqHeaders = Object.assign({'Accept': 'application/json', 'Content-Type': 'application/json'}, headers);
                            const r = await fetch(`${prefix}/workout-service/workout`, {
                                method: 'POST', headers: reqHeaders, credentials: 'include', body: JSON.stringify(payload)
                            });
                            return {status: r.status, body: await r.text()};
                        }""",
                        {"prefix": captured["prefix"], "headers": captured["headers"], "payload": payload}
                    )
                    if create_res["status"] in (200, 201):
                        w_id = json.loads(create_res["body"]).get("workoutId")
                        workout_ids[data["weekday"]] = w_id
                        print(f"  [TEMPLATE] Created '{title}' (ID: {w_id}) -> {data['target_pace']}")

            today = datetime.now().date()
            end_date = today + timedelta(days=21)
            months_to_check = {(today.year, today.month - 1), (end_date.year, end_date.month - 1)}
            already_scheduled = set()

            for yr, mo in months_to_check:
                cal_res = page.evaluate(
                    """async ({prefix, headers, yr, mo}) => {
                        const reqHeaders = Object.assign({'Accept': 'application/json'}, headers);
                        const r = await fetch(`${prefix}/calendar-service/year/${yr}/month/${mo}`, {
                            method: 'GET', headers: reqHeaders, credentials: 'include'
                        });
                        return {status: r.status, body: await r.text()};
                    }""",
                    {"prefix": captured["prefix"], "headers": captured["headers"], "yr": yr, "mo": mo}
                )
                if cal_res["status"] == 200:
                    cal_data = json.loads(cal_res["body"])
                    for item in cal_data.get("calendarItems", []):
                        if item.get("itemType") == "workout":
                            already_scheduled.add((item.get("date"), item.get("workoutId")))

            scheduled_count = 0
            skipped_count = 0
            for offset in range(1, 22):
                target_date = today + timedelta(days=offset)
                wkday = target_date.weekday()
                if wkday in workout_ids and workout_ids[wkday]:
                    w_id = workout_ids[wkday]
                    date_str = target_date.strftime("%Y-%m-%d")
                    if (date_str, w_id) in already_scheduled:
                        skipped_count += 1
                        continue
                    sched_res = page.evaluate(
                        """async ({prefix, headers, workoutId, dateStr}) => {
                            const reqHeaders = Object.assign({'Accept': 'application/json', 'Content-Type': 'application/json'}, headers);
                            const r = await fetch(`${prefix}/workout-service/schedule/${workoutId}`, {
                                method: 'POST', headers: reqHeaders, credentials: 'include', body: JSON.stringify({date: dateStr})
                            });
                            return {status: r.status, body: await r.text()};
                        }""",
                        {"prefix": captured["prefix"], "headers": captured["headers"], "workoutId": w_id, "dateStr": date_str}
                    )
                    if sched_res["status"] in (200, 201, 204):
                        print(f"  [OK] Newly scheduled workout ID {w_id} on {date_str}")
                        scheduled_count += 1

            print(f"Sync summary -> Newly scheduled: {scheduled_count} | Already on calendar (skipped): {skipped_count}")
            context.storage_state(path=STATE_FILE)

            generate_pdf(training_plan, sync_stats={"scheduled": scheduled_count, "skipped": skipped_count})
            generate_web_dashboard(training_plan, sync_stats={"scheduled": scheduled_count, "skipped": skipped_count})
            if creds:
                service = build("drive", "v3", credentials=creds)
                folder_name = "training plans"
                folder_res = service.files().list(
                    q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="files(id)"
                ).execute()
                folders = folder_res.get("files", [])
                if folders:
                    folder_id = folders[0]["id"]
                else:
                    folder_meta = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
                    folder_id = service.files().create(body=folder_meta, fields="id").execute().get("id")

                media = MediaFileUpload(PDF_FILE, mimetype="application/pdf")
                results = service.files().list(
                    q=f"name='Training_Plan_Week1.pdf' and '{folder_id}' in parents and trashed=false",
                    orderBy="modifiedTime desc",
                    fields="files(id)"
                ).execute()
                files = results.get("files", [])
                if files:
                    service.files().update(fileId=files[0]["id"], media_body=media).execute()
                    print(f"Updated Training_Plan_Week1.pdf inside '{folder_name}'.")
                    for dup in files[1:]:
                        service.files().update(fileId=dup["id"], body={"trashed": True}).execute()
                        print("Moved duplicate Training_Plan_Week1.pdf to trash.")
                else:
                    file_metadata = {"name": "Training_Plan_Week1.pdf", "parents": [folder_id]}
                    service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                    print(f"Created Training_Plan_Week1.pdf inside '{folder_name}'.")

        except Exception as e:
            print(f"Pipeline error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_pipeline()
