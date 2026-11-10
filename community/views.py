from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import BooleanField, Count, Exists, OuterRef, Q, Value
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.timesince import timesince
from django.views.decorators.http import require_POST

from analytics.services import track
from garden.images import clean_photo
from garden.models import UserPlant
from greenhand import mock_data as data
from plants.models import Plant
from notifications.models import Notification
from notifications.services import notify
from tutor.guardrails import rate_limited

from .models import MAX_POST_IMAGES, Comment, Post, PostImage, PostLike, PostSave, Report
from .services import schedule_ai_suggestion

REPORT_REASONS = dict(Report.REASONS)
FEEDS = ("latest", "same", "saved")
FEED_SIZE = 50
TRENDING_SIZE = 4
DAILY_POST_LIMIT = 20      # PRD 6.6
GRADIENTS = ("from-lime-200 to-emerald-400", "from-sky-200 to-indigo-300", "from-amber-200 to-orange-300", "from-rose-200 to-pink-300")


def _author_info(user):
    return {"initials": user.username[:2].upper(), "grad": GRADIENTS[user.pk % len(GRADIENTS)]}


def _visible_posts(user):
    """Feed queryset with counts and this viewer's like/save flags. Hidden posts are never included."""
    posts = (Post.objects.filter(is_hidden=False).select_related("author", "plant").prefetch_related("images", "comments__author")
             .annotate(num_likes=Count("likes", distinct=True)))
    if user.is_authenticated:
        return posts.annotate(liked=Exists(PostLike.objects.filter(post=OuterRef("pk"), user=user)),
                              saved=Exists(PostSave.objects.filter(post=OuterRef("pk"), user=user)))
    return posts.annotate(liked=Value(False, BooleanField()), saved=Value(False, BooleanField()))


def _decorate(post, user):
    comments = [c for c in post.comments.all() if not c.is_hidden]
    return {
        "id": post.pk, "author": post.author.username, "author_info": _author_info(post.author),
        "type_info": data.POST_TYPES[post.post_type], "created": timesince(post.created_at).split(",")[0],
        "body": post.body, "ai_suggestion": post.ai_suggestion,
        "plant_name": post.plant.common_name if post.plant else "", "plant_slug": post.plant.slug if post.plant else "",
        "plant_icon": "i-leaf", "likes": post.num_likes, "liked": post.liked, "saved": post.saved,
        "images": [{"url": i.image.url, "alt": i.alt_text or f"Photo shared by {post.author.username}"} for i in post.images.all()],
        "comments": [{"id": c.pk, "author": c.author.username, "author_info": _author_info(c.author), "body": c.body,
                      "created": timesince(c.created_at).split(",")[0], "mine": c.author_id == user.pk} for c in comments],
        "mine": post.author_id == user.pk,
    }


@login_required
def post_list(request):
    user = request.user
    feed = request.GET.get("feed", "latest")
    if feed not in FEEDS or not user.is_authenticated:
        feed = "latest"
    post_type = request.GET.get("type", "")
    posts = _visible_posts(user)
    my_plants = UserPlant.objects.none()
    if user.is_authenticated:
        my_plants = UserPlant.objects.filter(user=user).exclude(status__in=("failed", "archived")).select_related("plant")
    if feed == "same":
        posts = posts.filter(plant__in=UserPlant.objects.filter(user=user).values("plant"))
    elif feed == "saved":
        posts = posts.filter(saved=True)
    if post_type in data.POST_TYPES:
        posts = posts.filter(post_type=post_type)
    trending = Plant.objects.annotate(count=Count("posts", filter=Q(posts__is_hidden=False))).filter(count__gt=0).order_by("-count")[:TRENDING_SIZE]
    share_type = request.GET.get("share_type", "")
    prefill = {  # FR-26: "Share to Posts" from My Garden opens the composer filled in
        "body": request.GET.get("share_text", "")[:2000],
        "post_type": share_type if share_type in data.POST_TYPES else "",
        "user_plant": request.GET.get("share_plant", ""),
    }
    return render(request, "community/post_list.html", {
        "prefill": prefill,
        "posts": [_decorate(p, user) for p in posts[:FEED_SIZE]],
        "feed": feed,
        "post_type": post_type,
        "post_types": data.POST_TYPES,
        "my_plants": [{"id": str(p.pk), "nickname": p.nickname} for p in my_plants],
        "report_reasons": REPORT_REASONS,
        "trending": [{"name": p.common_name, "slug": p.slug, "count": p.count} for p in trending],
    })


@login_required
@require_POST
def create_post(request):
    body = request.POST.get("body", "").strip()
    post_type = request.POST.get("post_type", "progress")
    if post_type not in data.POST_TYPES:
        post_type = "progress"
    if not body:
        messages.error(request, "Write something before posting.")
        return redirect("community:feed")
    if rate_limited(f"posts:{request.user.pk}", limit=DAILY_POST_LIMIT):
        messages.error(request, "You have reached today's post limit. Please come back tomorrow.")
        return redirect("community:feed")
    try:
        photos = [clean_photo(f) for f in request.FILES.getlist("images")[:MAX_POST_IMAGES]]
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect("community:feed")
    plant_id = request.POST.get("user_plant", "")
    garden = UserPlant.objects.filter(user=request.user, pk=plant_id).select_related("plant").first() if plant_id.isdigit() else None
    alt_text = request.POST.get("image_alt", "").strip()[:200]
    with transaction.atomic():
        post = Post.objects.create(author=request.user, user_plant=garden, plant=garden.plant if garden else None,
                                   post_type=post_type, body=body[:2000])
        for order, photo in enumerate(photos):
            image = PostImage(post=post, order=order, alt_text=alt_text)
            image.image.save(photo.name, photo, save=True)
    track("post_created", request.user, post_type=post_type, images=len(photos))
    if post_type == "question":
        schedule_ai_suggestion(post)
    messages.success(request, "Posted to the community.")
    return redirect(f"{reverse('community:feed')}#post-{post.pk}")


@login_required
@require_POST
def add_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id, is_hidden=False)
    body = request.POST.get("body", "").strip()
    if body:
        Comment.objects.create(post=post, author=request.user, body=body[:1000])
        if post.author_id != request.user.pk:
            notify(post.author, Notification.Type.COMMENT, f"{request.user.username} commented on your post", body[:100],
                   f"{reverse('community:feed')}#post-{post.pk}")
        track("comment_created", request.user, post_id=post.pk)
        messages.success(request, "Comment added.")
    return redirect(f"{reverse('community:feed')}?{request.GET.urlencode()}#post-{post_id}")


@login_required
@require_POST
def toggle(request, post_id, field):
    """Like / save toggles (FR-52). Returns JSON for the page script."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login_required"}, status=401)
    post = get_object_or_404(Post, pk=post_id, is_hidden=False)
    model = {"like": PostLike, "save": PostSave}[field]
    row, created = model.objects.get_or_create(user=request.user, post=post)
    if not created:
        row.delete()
    elif field == "like" and post.author_id != request.user.pk:
        notify(post.author, Notification.Type.LIKE, f"{request.user.username} liked your post", post.body[:100],
               f"{reverse('community:feed')}#post-{post.pk}", dedupe_key=f"like-{post.pk}-{request.user.pk}")
    return JsonResponse({"active": created, "count": model.objects.filter(post=post).count()})


def _report(request, target, anchor_post_id):
    reason = request.POST.get("reason")
    if reason not in REPORT_REASONS:
        messages.error(request, "Please choose a reason.")
    else:
        Report.objects.get_or_create(reporter=request.user, content_type=ContentType.objects.get_for_model(target),
                                     object_id=target.pk, defaults={"reason": reason})
        messages.success(request, "Thanks for reporting. Our moderators will review this.")
    return redirect(f"{reverse('community:feed')}#post-{anchor_post_id}")


@login_required
@require_POST
def report_post(request, post_id):
    return _report(request, get_object_or_404(Post, pk=post_id, is_hidden=False), post_id)


@login_required
@require_POST
def report_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, is_hidden=False, post__is_hidden=False)
    return _report(request, comment, comment.post_id)
