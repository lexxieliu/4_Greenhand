from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views import View
from django.views.generic import ListView
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