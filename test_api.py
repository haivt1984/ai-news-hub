import requests

API_KEY = "AQ.Ab8RN6Kj1xNA69K9pKnN6b8v8bbl63wp3f2u51xZtkafuB2g6Q"
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
headers = {
    "x-goog-api-key": API_KEY,
    "Content-Type": "application/json"
}
payload = {"contents": [{"parts": [{"text": "Xin chao, phan hoi 1 chu: OK"}]}]}

res = requests.post(url, headers=headers, json=payload)
print("Status Code:", res.status_code)
print("Response:", res.text)