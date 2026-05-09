"""Fastlane API client."""

import os
import time
import requests


class FastlaneNotConfigured(Exception):
    pass


def _check_key():
    if not os.getenv("FASTLANE_API_KEY"):
        raise FastlaneNotConfigured("FASTLANE_API_KEY not configured")


BASE_URL = os.getenv("FASTLANE_BASE_URL", "https://api.usefastlane.ai/api/v1")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('FASTLANE_API_KEY')}",
        "Content-Type": "application/json",
    }


def _get(path: str, params: dict = None) -> dict:
    _check_key()
    r = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params, timeout=30)
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", 60))
        time.sleep(retry_after)
        return _get(path, params)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    _check_key()
    r = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=body, timeout=30)
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", 60))
        time.sleep(retry_after)
        return _post(path, body)
    r.raise_for_status()
    return r.json()


def _patch(path: str, body: dict) -> dict:
    _check_key()
    r = requests.patch(f"{BASE_URL}{path}", headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> dict:
    _check_key()
    r = requests.delete(f"{BASE_URL}{path}", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def list_angles() -> list:
    return _get("/blitz/angles")["data"]


def create_angle(title: str, description: str, target_audience: str) -> dict:
    return _post("/blitz/angles", {
        "title": title,
        "description": description,
        "targetAudience": target_audience,
    })["data"]


def get_preferences() -> dict:
    return _get("/blitz/preferences")["data"]


def set_preferences(prefs: dict) -> dict:
    return _patch("/blitz/preferences", prefs)["data"]


def blitz_pop() -> dict:
    try:
        result = _post("/blitz", {})
        data = result["data"]
        return {
            "content_id": data["contentId"],
            "content_type": data["suggestion"]["contentType"],
            "generated_text": data["suggestion"]["generatedText"],
            "ai_explanation": data["suggestion"]["aiExplanation"],
            "swipes_remaining": data["swipesRemaining"],
        }
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None
        if e.response.status_code == 429:
            err = e.response.json().get("error", {})
            if err.get("code") == "blitz_quota_exceeded":
                reset_at = err.get("details", {}).get("resetAt", 0)
                return {"error": "quota_exceeded", "reset_at": reset_at}
        raise


def poll_content(content_id: str, max_wait_s: int = 180) -> dict:
    elapsed = 0
    while elapsed < max_wait_s:
        result = get_content(content_id)
        status = result.get("status")
        if status == "CREATED":
            return result
        elif status == "FAILED":
            return None
        time.sleep(10)
        elapsed += 10
    return None


def list_content(limit: int = 20, content_type: str = None, status: str = None) -> list:
    params = {"limit": limit}
    if content_type:
        params["type"] = content_type
    if status:
        params["status"] = status
    return _get("/content", params)["data"]


def get_content(content_id: str) -> dict:
    return _get(f"/content/{content_id}")["data"]


def delete_content(content_id: str) -> bool:
    return _delete(f"/content/{content_id}")["data"]["deleted"]


def list_posts(limit: int = 20, status: str = None) -> list:
    params = {"limit": limit}
    if status:
        params["status"] = status
    return _get("/posts", params)["data"]


def get_post(post_id: str) -> dict:
    return _get(f"/posts/{post_id}")["data"]


def schedule_content(content_id: str, platform: str, utc_datetime: str,
                     caption: str, connection_id: str = None) -> str:
    body = {
        "platform": platform,
        "utc_datetime": utc_datetime,
        "caption": caption,
    }
    if connection_id:
        body["connectionId"] = connection_id
    return _post(f"/content/{content_id}/schedule", body)["data"]["postId"]


def cancel_posts(post_ids: list) -> int:
    return _post("/posts/cancel", {"postIds": post_ids})["data"]["cancelled"]


def get_post_analytics(post_ids: list) -> list:
    return _post("/analytics/posts", {"postIds": post_ids})["data"]


def list_connections() -> list:
    return _get("/connections")["data"]


def setup_vici_workspace():
    from brand import FASTLANE_ANGLES
    import json

    print("Setting up Fastlane workspace for Vici Peptides...")

    existing = list_angles()
    existing_titles = {a["title"] for a in existing}

    created_ids = []
    for angle in FASTLANE_ANGLES:
        if angle["title"] in existing_titles:
            match = next(a for a in existing if a["title"] == angle["title"])
            created_ids.append(match["_id"])
            print(f"  -> Angle already exists: {angle['title']}")
        else:
            result = create_angle(angle["title"], angle["description"], angle["targetAudience"])
            created_ids.append(result["_id"])
            print(f"  + Created angle: {angle['title']}")
            time.sleep(1)

    if created_ids:
        n = len(created_ids)
        base = 100 // n
        remainder = 100 - base * n
        weights = {}
        for i, aid in enumerate(created_ids):
            weights[aid] = base + (1 if i < remainder else 0)

        set_preferences({
            "slideshowWeight": 35,
            "wallOfTextWeight": 35,
            "greenScreenWeight": 15,
            "videoHookWeight": 15,
            "remixPercentage": 40,
            "ownMediaPercentage": 60,
            "mentionBusinessPercentage": 30,
            "genderFilter": None,
            "angleWeights": weights,
        })
        print("  + Blitz preferences configured")

    os.makedirs("data", exist_ok=True)
    with open("data/fastlane_angles.json", "w") as f:
        json.dump(list_angles(), f, indent=2)

    print("Fastlane workspace ready")
