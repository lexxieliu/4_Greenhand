from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.template import loader
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView, UpdateView
from .models import Profile

# ====================================================
# A) Function-Based Views (FBV)
# ====================================================

# 1. HttpResponse (Manual)
def profile_manual_view(request):
    profiles = Profile.objects.all()
    template = loader.get_template('userprofile/profile_list.html')
    context = {'profiles': profiles}
    return HttpResponse(template.render(context, request))

# 2. render() (Shortcut)
def profile_render_view(request):
    profiles = Profile.objects.all()
    return render(request, 'userprofile/profile_list.html', {'profiles': profiles})


# ====================================================
# B) Class-Based Views (CBV)
# ====================================================

# 3. Base CBV
class ProfileBaseView(View):
    def get(self, request):
        profiles = Profile.objects.all()
        return render(request, 'userprofile/profile_list.html', {'profiles': profiles})

# 4. Generic CBVs

# 1: DetailView
class ProfileGenericDetailView(DetailView):
    model = Profile
    template_name = 'userprofile/profile_detail.html'
    context_object_name = 'profile'
    pk_url_kwarg = 'pk'

# 2: UpdateView
class ProfileGenericUpdateView(UpdateView):
    model = Profile
    fields = ['bio', 'birthdate', 'pronouns']
    template_name = 'userprofile/profile_form.html'
    pk_url_kwarg = 'pk'

    def get_success_url(self):
        return reverse_lazy('profile-cbv-generic-detail', kwargs={'pk': self.object.pk})