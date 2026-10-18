from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from greenhand import mock_data as data

REPORT_REASONS = {"spam": "Spam", "harmful_advice": "Harmful advice", "harassment": "Harassment", "other": "Something else"}


def _post(post_id):
    post = next((p for p in data.POSTS if p["id"] == post_id), None)
    if not post:
        raise Http404("Post not found")
    return post


def _decorate(p):
    plant = data.CATALOG_BY_SLUG.get(p["plant_slug"])
    return {
        **p,
        "author_info": data.AUTHORS[p["author"]],
        "type_info": data.POST_TYPES[p["post_type"]],
        "plant_name": plant["common_name"] if plant else "",
        "plant_icon": plant["icon"] if plant else "i-leaf",
        "comments": [{**c, "author_info": data.AUTHORS.get(c["author"], data.AUTHORS["balcony_maya"])} for c in p["comments"]],
        "mine": p["author"] == data.USER["username"],
    }


def post_list(request):
    feed = request.GET.get("feed", "latest")
    post_type = request.GET.get("type", "")
    my_slugs = {g["plant_slug"] for g in data.GARDEN}
    posts = sorted(data.POSTS, key=lambda p: -p["id"])
    if feed == "same":
        posts = [p for p in posts if p["plant_slug"] in my_slugs]
    elif feed == "saved":
        posts = [p for p in posts if p["saved"]]
    if post_type in data.POST_TYPES:
        posts = [p for p in posts if p["post_type"] == post_type]
    return render(request, "community/post_list.html", {
        "posts": [_decorate(p) for p in posts],
        "feed": feed if feed in ("latest", "same", "saved") else "latest",
        "post_type": post_type,
        "post_types": data.POST_TYPES,
        "my_plants": [g for g in data.GARDEN if g["status"] not in ("failed", "archived")],
        "report_reasons": REPORT_REASONS,
        "trending": [{"name": data.CATALOG_BY_SLUG[s]["common_name"], "slug": s, "count": sum(1 for p in data.POSTS if p["plant_slug"] == s)} for s in ("cherry-tomato", "basil", "lettuce", "kale")],
    })


@require_POST
def create_post(request):
    body = request.POST.get("body", "").strip()
    post_type = request.POST.get("post_type", "progress")
    if not body:
        messages.error(request, "Write something before posting.")
        return redirect("community:feed")
    garden_plant = next((g for g in data.GARDEN if g["id"] == request.POST.get("user_plant")), None)
    new_id = max(p["id"] for p in data.POSTS) + 1
    ai = ""
    if post_type == "question":
        ai = "Thanks for the details! Based on similar posts, check light, watering, and drainage first. The tutor can give a plant-specific answer from your garden logs."
    data.POSTS.append({
        "id": new_id, "author": data.USER["username"], "plant_slug": garden_plant["plant_slug"] if garden_plant else "",
        "post_type": post_type if post_type in data.POST_TYPES else "progress", "created": "now", "body": body[:2000],
        "images": min(4, len(request.FILES.getlist("images"))), "likes": 0, "saves": 0, "liked": False, "saved": False,
        "ai_suggestion": ai, "comments": [],
    })
    messages.success(request, "Posted to the community.")
    return redirect(f"{reverse('community:feed')}#post-{new_id}")


@require_POST
def add_comment(request, post_id):
    post = _post(post_id)
    body = request.POST.get("body", "").strip()
    if body:
        post["comments"].append({"author": data.USER["username"], "body": body[:1000], "created": "now"})
        messages.success(request, "Comment added.")
    return redirect(f"{reverse('community:feed')}?{request.GET.urlencode()}#post-{post_id}")


@require_POST
def toggle(request, post_id, field):
    """Like / save toggles (FR-52). Returns JSON for the page script."""
    post = _post(post_id)
    flag, counter = {"like": ("liked", "likes"), "save": ("saved", "saves")}[field]
    post[flag] = not post[flag]
    post[counter] += 1 if post[flag] else -1
    return JsonResponse({"active": post[flag], "count": post[counter]})


@require_POST
def report_post(request, post_id):
    _post(post_id)
    reason = request.POST.get("reason")
    if reason not in REPORT_REASONS:
        messages.error(request, "Please choose a reason.")
    else:
        messages.success(request, "Thanks for reporting. Our moderators will review this post.")
    return redirect(f"{reverse('community:feed')}#post-{post_id}")
