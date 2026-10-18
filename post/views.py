from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from post.models import Post


# Create your views here.
#Function based view on Post View
def post_list_long(request):
    posts = Post.objects.all()
    context = {'posts': posts}
    template = loader.get_template("posts/post_list.html")
    output = template.render(context)
    return HttpResponse(output)

def post_list_short(request):
    posts = Post.objects.all()
    return render(request, 'posts/post_list.html', {'posts': posts})