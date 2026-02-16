import urllib.request
import urllib.parse
import urllib.error
import json

BASE_URL = "http://localhost:8000"

def login():
    try:
        url = f"{BASE_URL}/login"
        data = json.dumps({"username": "admin@123", "password": "fortunecityadmin@123"}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('access_token')
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.code} {e.reason}")
        print(e.read().decode('utf-8'))
        return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def create_post(token):
    try:
        url = f"{BASE_URL}/posts"
        post_data = {
            "title": "Debug Post",
            "content": "Initial content",
            "status": "draft"
        }
        data = json.dumps(post_data).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }, method='POST')
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except urllib.error.HTTPError as e:
        print(f"Create post failed: {e.code}")
        print(e.read().decode('utf-8'))
        return None

def update_post(token, post_id, new_title, new_status):
    try:
        url = f"{BASE_URL}/posts/{post_id}"
        # Update payload
        update_data = {
            "title": new_title,
            "content": "Updated content here",
            "status": new_status,
            "id": post_id, 
            "author_id": 1
        }
        data = json.dumps(update_data).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }, method='PUT')
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"Update returned Title: {result.get('title')}")
            print(f"Update returned Status: {result.get('status')}")
            return result
    except urllib.error.HTTPError as e:
        print(f"Update post failed: {e.code}")
        print(e.read().decode('utf-8'))
        return None

if __name__ == "__main__":
    token = login()
    if token:
        print("Login successful")
        post = create_post(token)
        if post:
            print(f"Created post {post['id']} with title '{post['title']}'")
            update_post(token, post['id'], "Updated Title Works", "published")
    else:
        print("Could not login. Please check admin credentials in main.py")
