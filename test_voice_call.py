import requests
import time

BASE_URL = "http://127.0.0.1:8000"

def simulate_call():
    print("📞 Simulating incoming call from customer...")
    
    # 1. Simulate the initial Twilio webhook hit
    print("\n[1] Twilio hits /support/voice/inbound/")
    inbound_res = requests.post(f"{BASE_URL}/support/voice/inbound/")
    print(f"Twilio TwiML Response:\n{inbound_res.text}")
    
    time.sleep(2)
    
    # 2. Simulate the user speaking
    mock_transcript = "Hi, my name is Sarah Jenkins. I am interested in upgrading my enterprise plan, and I would like to schedule a demo for next Thursday at 3pm."
    caller_phone = "+1234567890"
    call_sid = "CA1234567890abcdef1234567890abcdef"
    
    print(f"\n[2] User speaks: '{mock_transcript}'")
    print("Twilio sends transcript to /support/voice/process-speech/...")
    
    speech_res = requests.post(
        f"{BASE_URL}/support/voice/process-speech/",
        data={
            "SpeechResult": mock_transcript,
            "From": caller_phone,
            "CallSid": call_sid
        }
    )
    
    print(f"\n[3] AI Engine processed call. TwiML Response to caller:\n{speech_res.text}")
    
    print("\n✅ Done! Check your 'Voice & Appointments' dashboard in the browser to see the recorded call and booked appointment!")

if __name__ == "__main__":
    simulate_call()
