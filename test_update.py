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

def update_post_title(token, post_id, new_title):
    try:
        url = f"{BASE_URL}/posts/{post_id}"
        update_data = {
            "title": new_title
        }
        data = json.dumps(update_data).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }, method='PUT')
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"✓ Update successful!")
            print(f"  New title in response: {result.get('title')}")
            return result
    except urllib.error.HTTPError as e:
        print(f"✗ Update failed: {e.code} {e.reason}")
        error_body = e.read().decode('utf-8')
        print(f"  Error details: {error_body}")
        return None

def get_single_post(token, post_id):
    try:
        url = f"{BASE_URL}/posts/{post_id}"
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {token}'
        }, method='GET')
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except urllib.error.HTTPError as e:
        print(f"Get post failed: {e.code}")
        return None

if __name__ == "__main__":
    print("Testing post title update functionality...\n")
    token = login()
    if token:
        print("✓ Login successful\n")
        posts = get_posts(token)
        if posts and len(posts) > 0:
            print(f"✓ Found {len(posts)} posts\n")
            # Get the first post
            test_post = posts[0]
            original_title = test_post['title']
            post_id = test_post['id']
            
            print(f"Testing with post ID {post_id}")
            print(f"Original title: '{original_title}'")
            
            # Update the title
            new_title = f"{original_title} - UPDATED"
            print(f"\nUpdating title to: '{new_title}'")
            updated = update_post_title(token, post_id, new_title)
            
            if updated:
                # Verify by fetching the post again
                print("\nVerifying update by fetching post again...")
                verified = get_single_post(token, post_id)
                if verified:
                    print(f"✓ Verified title in database: '{verified.get('title')}'")
                    if verified.get('title') == new_title:
                        print("✓ SUCCESS: Title was updated in database!")
                    else:
                        print("✗ FAILED: Title in database doesn't match!")
                        
                # Restore original title
                print(f"\nRestoring original title: '{original_title}'")
                update_post_title(token, post_id, original_title)
        else:
            print("No posts found to test with")
    else:
        print("Could not login")
