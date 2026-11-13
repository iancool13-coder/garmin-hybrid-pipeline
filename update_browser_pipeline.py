import os
import json
import base64
import pickle
from datetime import datetime, timedelta
from fpdf import FPDF
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "garmin_state.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.pickle")
PDF_FILE = os.path.join(BASE_DIR, "Training_Plan_Week1.pdf")

# Decode GitHub Actions Secrets into local temp files when running in the cloud
if os.environ.get("GARMIN_STATE_B64"):
    with open(STATE_FILE, "wb") as f:
        f.write(base64.b64decode(os.environ["GARMIN_STATE_B64"]))

if os.environ.get("GOOGLE_TOKEN_B64"):
    with open(TOKEN_FILE, "wb") as f:
        f.write(base64.b64decode(os.environ["GOOGLE_TOKEN_B64"]))

print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] >>> STARTING ADAPTIVE HYBRID PIPELINE <<<")

if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "rb") as token:
        creds = pickle.load(token)
else:
    creds = None

def min_km_to_ms(min_per_km):
    return round(1000.0 / (min_per_km * 60.0), 4)

def vo2max_to_hm_seconds(vo2):
    estimated_sec = 7080 - ((vo2 - 46.0) * 172.0)
    return max(4200, min(9000, int(estimated_sec)))

def get_dynamic_plan(half_marathon_seconds=7070, source_label="Baseline (1:57:50 HM)"):
    base_min_per_km = (half_marathon_seconds / 21.0975) / 60.0

    fartlek_pace = round(base_min_per_km * 0.95, 2)
    base_pace = round(base_min_per_km * 1.12, 2)
    recovery_pace = round(base_min_per_km * 1.22, 2)
    long_pace = round(base_min_per_km * 1.08, 2)

    return {
        "_meta": {
            "hm_seconds": half_marathon_seconds,
            "source": source_label,
            "base_min_km": round(base_min_per_km, 2)
        },
        "Monday": {
            "weekday": 0,
            "type": "run",
            "title": "Sub-2:00 Fartlek Intervals",
            "description": "10 min warmup, 6 miles Fartlek intervals, 5 min cooldown",
            "target_pace": f"approx {fartlek_pace} min/km",
            "distance_m": 9656.0,
            "pace_ms_low": min_km_to_ms(fartlek_pace + 0.15),
            "pace_ms_high": min_km_to_ms(fartlek_pace - 0.15)
        },
        "Tuesday": {
            "weekday": 1,
            "type": "lift",
            "title": "Lower Body Power",
            "description": (
                "- Barbell Back Squats: Warmup sets, then 3 working sets x 5 reps (RPE 8)\n"
                "- Landmine RDLs: 3 sets x 8-10 reps per leg\n"
                "- Core Stabilization (Plank / Pallof Press): 3 sets x 45 sec hold"
            )
        },
        "Wednesday": {
            "weekday": 2,
            "type": "run",
            "title": "Sub-2:00 Base + Strides",
            "description": "4 miles easy aerobic base + 4 strides",
            "target_pace": f"approx {base_pace} min/km",
            "distance_m": 6437.0,
            "pace_ms_low": min_km_to_ms(base_pace + 0.15),
            "pace_ms_high": min_km_to_ms(base_pace - 0.15)
        },
        "Thursday": {
            "weekday": 3,
            "type": "lift",
            "title": "Upper Body & Back",
            "description": (
                "- Pull-ups (Weighted or Bodyweight): 3 sets x max reps (leave 2 in tank)\n"
                "- Landmine Single-Arm Presses: 3 sets x 8 reps per arm\n"
                "- Barbell Bent-Over Rows: 4 sets x 6-8 reps (heavy)"
            )
        },
        "Friday": {
            "weekday": 4,
            "type": "run",
            "title": "Sub-2:00 Recovery",
            "description": "3 miles easy recovery jog",
            "target_pace": f"approx {recovery_pace} min/km",
            "distance_m": 4828.0,
            "pace_ms_low": min_km_to_ms(recovery_pace + 0.20),
            "pace_ms_high": min_km_to_ms(recovery_pace - 0.15)
        },
        "Saturday": {
            "weekday": 5,
            "type": "lift",
            "title": "Mobility & Core",
            "description": (
                "- Landmine Russian Twists: 3 sets x 15 reps/side\n"
                "- Hip Flexor Release & Dynamic Flow Stretching: 15 mins"
            )
        },
        "Sunday": {
            "weekday": 6,
            "type": "run",
            "title": "Sub-2:00 Long Run",
            "description": "8 miles steady state baseline",
            "target_pace": f"approx {long_pace} min/km",
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

def fetch_live_fitness_baseline(page, prefix, headers):
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

    if act_res["status"] == 200:
        activities = json.loads(act_res["body"])
        for act in activities:
            dist_m = act.get("distance") or 0
            dur_s = act.get("duration") or 0
            name = (act.get("activityName") or "").lower()
            event_type = (act.get("eventType", {}) or {}).get("typeKey", "")
            is_race = (event_type == "race") or any(k in name for k in ["21k", "half", "10k", "5k", "race", "marathon"])

            if 20800 <= dist_m <= 21500 and dur_s > 3600:
                mins, secs = divmod(int(dur_s), 60)
                hrs, mins = divmod(mins, 60)
                return int(dur_s), f"Live Race ({act.get('activityName')}: {hrs}:{mins:02d}:{secs:02d})"

            if is_race and 4800 <= dist_m <= 10500 and dur_s > 900:
                equiv_hm = int(dur_s * ((21097.5 / dist_m) ** 1.06))
                mins, secs = divmod(equiv_hm, 60)
                hrs, mins = divmod(mins, 60)
                return equiv_hm, f"Scaled from {act.get('activityName')} (Equiv HM {hrs}:{mins:02d}:{secs:02d})"

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
                hm_sec = vo2max_to_hm_seconds(float(vo2_val))
                return hm_sec, f"Watch VO2 Max ({vo2_val})"
        except Exception:
            pass

    return 7070, "Default Baseline (1:57:50 HM)"

def generate_pdf(training_plan):
    meta = training_plan.get("_meta", {})
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Dynamic Hybrid Plan - 3-Week Rolling Schedule", ln=True, align="C")
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 6, f"Updated: {datetime.now().strftime('%b %d, %Y')} | Calibration: {meta.get('source', 'Baseline')}", ln=True, align="C")
    pdf.cell(0, 6, "Runs -> Garmin Calendar (Auto-Updated Paces) | Lifts -> Drive PDF", ln=True, align="C")
    pdf.ln(4)

    for day, data in training_plan.items():
        if day.startswith("_"):
            continue
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, f"{day} - {data['title']} ({data['type'].upper()})", ln=True)
        pdf.set_font("Arial", "", 10)
        for line in data["description"].split("\n"):
            pdf.cell(0, 5, f"  {line}", ln=True)
        if "target_pace" in data:
            pdf.set_font("Arial", "I", 9)
            pdf.cell(0, 5, f"  Target Pace: {data['target_pace']}", ln=True)
        pdf.ln(3)

    pdf.output(PDF_FILE)
    print(f"PDF generated successfully (Calibration: {meta.get('source')}).")

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

            hm_seconds, source_label = fetch_live_fitness_baseline(page, captured["prefix"], captured["headers"])
            print(f"Fitness Calibration -> {source_label}")
            training_plan = get_dynamic_plan(hm_seconds, source_label)

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

            generate_pdf(training_plan)
            if creds:
                service = build("drive", "v3", credentials=creds)
                file_metadata = {"name": "Training_Plan_Week1.pdf"}
                media = MediaFileUpload(PDF_FILE, mimetype="application/pdf")
                results = service.files().list(q="name='Training_Plan_Week1.pdf'", fields="files(id)").execute()
                files = results.get("files", [])
                if files:
                    service.files().update(fileId=files[0]["id"], media_body=media).execute()
                    print("Updated Training_Plan_Week1.pdf in Google Drive.")
                else:
                    service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                    print("Created Training_Plan_Week1.pdf in Google Drive.")

        except Exception as e:
            print(f"Pipeline error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_pipeline()
