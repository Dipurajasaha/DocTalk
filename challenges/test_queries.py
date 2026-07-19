import asyncio
import csv
import json
import logging
import requests
import websockets

logging.basicConfig(level=logging.INFO)

API_BASE = "http://localhost:8000/api"
WS_BASE = "ws://localhost:8000/api"

def get_token():
    try:
        res = requests.post(f"{API_BASE}/auth/patient/login", json={
            "username": "patientdipu",
            "password": "raja1234Raja@"
        })
        res.raise_for_status()
        return res.json()["access_token"]
    except Exception as e:
        logging.error(f"Failed to get token: {e}")
        return None

def create_doctor_slots():
    try:
        # Login doctor
        res = requests.post(f"{API_BASE}/auth/doctor/login", json={
            "doctor_id": "DocDipu",
            "password": "D94461328d@"
        })
        res.raise_for_status()
        doc_token = res.json()["access_token"]
        
        # Create slots (using +05:30 since user is in IST and refers to local time)
        headers = {"Authorization": f"Bearer {doc_token}"}
        slots = [
            {"startTime": "2026-07-04T16:00:00+05:30", "endTime": "2026-07-04T16:30:00+05:30"},
            {"startTime": "2026-07-04T16:30:00+05:30", "endTime": "2026-07-04T17:00:00+05:30"},
            {"startTime": "2026-07-04T21:30:00+05:30", "endTime": "2026-07-04T22:00:00+05:30"}
        ]
        res = requests.post(f"{API_BASE}/appointments/slots", json=slots, headers=headers)
        if res.status_code in (200, 201):
            print("Successfully created slots for doctor DocDipu.")
        else:
            print(f"Failed to create slots: {res.text}")
    except Exception as e:
        logging.error(f"Failed to create doctor slots: {e}")

async def test_queries():
    create_doctor_slots()
    token = get_token()
    if not token:
        print("Failed to authenticate.")
        return

    queries = []
    with open('valid_queries.csv', mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append(row['query'])

    results = []

    # Need to clear chats between requests to isolate them.
    import subprocess
    
    ws_url = f"{WS_BASE}/chat/ai/patient/ws?token={token}"
    
    for query in queries:
        print(f"Clearing previous chats...")
        subprocess.run(["d:\\DocTalk\\.venv\\Scripts\\python.exe", "d:\\DocTalk\\backend\\clear_ai_chats.py"], capture_output=True)
        
        print(f"Testing: {query}")
        final_response = None
        status_ok = False
        
        try:
            async with websockets.connect(ws_url) as ws:
                # wait for history payload which is sent initially
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(msg)
                    if data.get("type") == "history":
                        break
                        
                await ws.send(query)
                
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=180.0)
                        
                        try:
                            data = json.loads(msg)
                        except json.JSONDecodeError:
                            final_response = msg
                            status_ok = True
                            break
                        
                        if isinstance(data, dict):
                            if data.get("type") == "final":
                                final_response = data.get("content", "")
                                status_ok = True
                                break
                        else:
                            final_response = msg
                            status_ok = True
                            break
                    except asyncio.TimeoutError:
                        final_response = "TIMEOUT"
                        status_ok = False
                        break
                    except Exception as e:
                        final_response = f"ERROR: {e}"
                        status_ok = False
                        break
        except Exception as e:
            final_response = f"WS ERROR: {e}"
            status_ok = False
            
        # Format output to remove newlines for cleaner CSV viewing
        formatted_response = final_response.replace('\n', '\\n').replace('\r', '') if final_response else ""
            
        print(f"Result: {'Success' if status_ok else 'Failed'}")
        results.append({
            "input": query,
            "output": formatted_response,
            "success or failed": "Success" if status_ok else "Failed"
        })

    try:
        with open('test_results.csv', mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["input", "output", "success or failed"])
            writer.writeheader()
            writer.writerows(results)
        print(f"Finished testing {len(results)} queries. Results saved to test_results.csv")
    except PermissionError:
        print("Permission denied when writing to test_results.csv (file might be open in an editor).")
        print("Saving to test_results_fallback.csv instead...")
        with open('test_results_fallback.csv', mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["input", "output", "success or failed"])
            writer.writeheader()
            writer.writerows(results)
        print(f"Finished testing {len(results)} queries. Results saved to test_results_fallback.csv")

if __name__ == "__main__":
    asyncio.run(test_queries())
