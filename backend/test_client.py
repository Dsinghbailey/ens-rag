import requests
import json
import sseclient


def test_regular_chat():
    """Test the regular chat endpoint"""
    print("Testing regular chat endpoint...")
    url = "http://localhost:3001/chat"
    headers = {
        "Content-Type": "application/json",
    }

    data = {"messages": [{"role": "user", "content": "What is ENS?"}], "customerId": 1}

    response = requests.post(url, headers=headers, json=data, stream=True)
    client = sseclient.SSEClient(response)

    for event in client.events():
        try:
            print(f"RAW DATA: {event.data}")
            json_data = json.loads(event.data)
            print(f"JSON: {json_data}")
            if "text" in json_data:
                print(f"TEXT: {json_data['text']}")
            elif "content" in json_data:
                print(f"CONTENT: {json_data['content']}")
            elif "choices" in json_data and "delta" in json_data["choices"][0]:
                print(f"OPENAI DELTA: {json_data['choices'][0]['delta']['content']}")
            print("---")
        except json.JSONDecodeError:
            print(f"Not JSON: {event.data}")
            print("---")


def test_debug_sse():
    """Test the debug SSE endpoint"""
    print("Testing debug SSE endpoint...")
    url = "http://localhost:3001/debug-sse"
    headers = {
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, stream=True)
    client = sseclient.SSEClient(response)

    for event in client.events():
        try:
            print(f"RAW DATA: {event.data}")
            json_data = json.loads(event.data)
            print(f"JSON: {json_data}")
            if "text" in json_data:
                print(f"TEXT: {json_data['text']}")
            elif "content" in json_data:
                print(f"CONTENT: {json_data['content']}")
            elif "choices" in json_data and "delta" in json_data["choices"][0]:
                print(f"OPENAI DELTA: {json_data['choices'][0]['delta']['content']}")
            print("---")
        except json.JSONDecodeError:
            print(f"Not JSON: {event.data}")
            print("---")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        test_debug_sse()
    else:
        test_regular_chat()
