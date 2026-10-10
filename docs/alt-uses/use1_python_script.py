"""Use 1: call the public Greenhand API from a plain Python script
and do simple aggregations on the result."""
import requests

API_URL = "https://lexxieliu.pythonanywhere.com/api/summary/"

response = requests.get(API_URL, timeout=10)
response.raise_for_status()
rows = response.json()          # [{"category": "Fern", "value": 2}, ...]

print(f"GET {API_URL} -> {response.status_code}")
print(f"Rows received: {len(rows)}\n")

print(f"{'Category':<20}{'Plants':>6}")
for row in rows:
    print(f"{row['category']:<20}{row['value']:>6}")

total = sum(row["value"] for row in rows)
largest = max(rows, key=lambda row: row["value"])
average = total / len(rows)

print("\n--- Aggregations ---")
print(f"Total plants in database : {total}")
print(f"Number of categories     : {len(rows)}")
print(f"Largest category         : {largest['category']} ({largest['value']} plants)")
print(f"Average plants/category  : {average:.2f}")