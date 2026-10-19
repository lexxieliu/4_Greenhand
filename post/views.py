from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template import loader
from django.views import View
from django.views.generic import ListView

from tutor.guardrails import check_input, rate_limited

from . import pipeline
from .forms import PostForm
from .models import Post

# ----------------------------------------------------
# A) Function-Based Views (FBV)
# ----------------------------------------------------

# 1. HttpResponse (Manual)
def post_manual_view(request):
    posts = Post.objects.all()
    template = loader.get_template('post/post_list.html')
    context = {'posts': posts}
    return HttpResponse(template.render(context, request))

# 2. render() (Shortcut)
def post_render_view(request):
    posts = Post.objects.all()
    return render(request, 'post/post_list.html', {'posts': posts})

# ----------------------------------------------------
# B) Class-Based Views (CBV)
# ----------------------------------------------------

# 3. Base CBV (inherit from View)
class PostBaseView(View):
    def get(self, request):
        posts = Post.objects.all()
        return render(request, 'post/post_list.html', {'posts': posts})

# 4. Generic CBV (inherit from ListView)
class PostGenericListView(ListView):
    model = Post
    template_name = 'post/post_list.html'
    context_object_name = 'posts'


# ----------------------------------------------------
# C) AI feature: create a post, summarized by the hybrid pipeline (local model filter + Gemini)
# ----------------------------------------------------
RATE_LIMIT_MESSAGE = "You have reached the hourly limit for AI features. Please try again later."


@login_required
def post_create(request):
    form = PostForm(request.POST or None)
    error = None

    if request.method == "POST" and form.is_valid():
        text = form.cleaned_data["post_content"].strip()
        ok, reason = check_input(text)
        if not ok:
            error = reason
        elif rate_limited(request.user.id):
            error = RATE_LIMIT_MESSAGE
        else:
            result = pipeline.process_post(text)
            if result.status == pipeline.REJECTED:
                error = f"Your post was not published: {result.message}"
            else:
                Post.objects.create(user=request.user, post_content=text, ai_summary=result.summary)
                if result.message:
                    messages.info(request, result.message)
                else:
                    messages.success(request, "Your post was published with an AI summary.")
                return redirect("post-render")

    return render(request, "post/post_create.html", {"form": form, "error": error})

