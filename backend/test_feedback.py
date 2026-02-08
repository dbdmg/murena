
import requests
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1"

def test_feedback_backup():
    # We need a valid run_id. Let's try to get one from the db or a known recent one.
    # For testing, we'll assume a dummy run exists or just check if the endpoint returns 404 (which still proves the logic branch before backup).
    # But to really test backup we need a real run.
    
    run_id = "test_run_" + str(uuid.uuid4())[:8]
    print(f"Testing with dummy run_id (expected 404 but checking if logic runs): {run_id}")
    
    payload = {
        "run_id": "dummy_run", # This might fail if dummy_run doesn't exist
        "agent_name": "Test Agent",
        "rating": 5,
        "comment": "Automated test feedback"
    }
    
    try:
        # First, let's try to find an existing run_id to join
        runs_resp = requests.get(f"{BASE_URL}/analysis/history?limit=1")
        if runs_resp.status_code == 200 and runs_resp.json():
            run_id = runs_resp.json()[0]['run_id']
            payload['run_id'] = run_id
            print(f"Using real run_id: {run_id}")
        
        resp = requests.post(f"{BASE_URL}/feedback/agent", json=payload)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code in [201, 200]:
            print("Feedback submitted successfully!")
            return True
        else:
            print(f"Error: {resp.text}")
            return False
    except Exception as e:
        print(f"Request failed: {e}")
        return False

if __name__ == "__main__":
    test_feedback_backup()
