"""AI suggestion on question posts (FR-54). It runs after the response: the local model can take a minute."""
import logging
import threading

from django.db import close_old_connections, transaction

from tutor.services import suggest_for_post

from .models import Post

logger = logging.getLogger(__name__)


def attach_ai_suggestion(post_id):
    post = Post.objects.select_related("plant").get(pk=post_id)
    suggestion = suggest_for_post(post.body, post.plant.plant_name if post.plant else "")
    if suggestion:
        Post.objects.filter(pk=post_id).update(ai_suggestion=suggestion)


def _run(post_id):
    try:
        attach_ai_suggestion(post_id)
    except Exception:
        logger.exception("AI suggestion failed for post %s", post_id)
    finally:
        close_old_connections()


def schedule_ai_suggestion(post):
    transaction.on_commit(lambda: threading.Thread(target=_run, args=(post.pk,), daemon=True).start())
