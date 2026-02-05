from django.views.generic import TemplateView

from judge.utils.views import TitleMixin


class HomeView(TitleMixin, TemplateView):
    template_name = 'home.html'
    title = 'Home'

    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)
        return context
