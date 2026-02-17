import urllib.request
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

def get_posts(token):
    try:
        url = f"{BASE_URL}/posts"
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {token}'
        }, method='GET')
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except urllib.error.HTTPError as e:
        print(f"Get posts failed: {e.code}")
        print(e.read().decode('utf-8'))
        return None

def delete_post(token, post_id):
    try:
        url = f"{BASE_URL}/posts/{post_id}"
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {token}'
        }, method='DELETE')
        
        with urllib.request.urlopen(req) as response:
            print(f"Delete successful! Status code: {response.status}")
            return True
    except urllib.error.HTTPError as e:
        print(f"Delete failed: {e.code} {e.reason}")
        print(e.read().decode('utf-8'))
        return False

if __name__ == "__main__":
    print("Testing delete functionality...")
    token = login()
    if token:
        print("✓ Login successful")
        posts = get_posts(token)
        if posts and len(posts) > 0:
            print(f"✓ Found {len(posts)} posts")
            # Try to delete the last post
            last_post = posts[-1]
            print(f"\nAttempting to delete post ID {last_post['id']}: '{last_post['title']}'")
            if delete_post(token, last_post['id']):
                print("✓ Delete successful!")
                # Verify it's gone
                posts_after = get_posts(token)
                if posts_after is not None:
                    print(f"✓ Posts remaining: {len(posts_after)}")
            else:
                print("✗ Delete failed")
        else:
            print("No posts to delete")
    else:
        print("Could not login")
