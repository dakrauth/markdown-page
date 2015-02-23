from functools import wraps
from django import http
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from taggit.utils import parse_tags

from .settings import get_mdpage_setting, mdpage_settings
from .models import MarkdownPage, MarkdownPageType
from .forms import MarkdownPageForm, ContentForm


#-------------------------------------------------------------------------------
@login_required
def _mdpage_new_page(request, vh, title):
    vh.page = MarkdownPage(type=vh.mdp_type, title=title)
    if request.POST:
        form = MarkdownPageForm(request.POST, instance=vh.page)
        if form.is_valid():
            vh.page = form.save(request)
            return vh.redirect()
    else:
        form = MarkdownPageForm(instance=vh.page)
    
    return vh.render('edit.html', form=form)


#===============================================================================
class ViewHandler(object):

    #---------------------------------------------------------------------------
    def __init__(self, request, prefix, slug=None, raise_404=True):
        self.request = request
        self.mdp_type = get_object_or_404(MarkdownPageType.published, prefix=prefix)
        self.page = None
        if slug:
            self.load_page(slug, raise_404)

    #---------------------------------------------------------------------------
    def load_page(self, slug, raise_404=True):
        try:
            self.page = MarkdownPage.published.get(type=self.mdp_type, slug=slug)
            return True
        except MarkdownPage.DoesNotExist:
            if raise_404:
                raise http.Http404

        self.page = None
        return False

    #---------------------------------------------------------------------------
    def render(self, tmpl_part, **kws):
        kws.update(
            mdp_type=self.mdp_type,
            page=self.page,
            mdpage={k: v for k,v in mdpage_settings.items() if k.startswith('show_')},
        )

        template_list = [
            'mdpage/types/{}/{}'.format(self.mdp_type.prefix or '__root__', tmpl_part),
            'mdpage/{}'.format(tmpl_part)
        ]

        return render(self.request, template_list, kws)

    #---------------------------------------------------------------------------
    def redirect(self):
        return http.HttpResponseRedirect(self.page.get_absolute_url())
    
    #---------------------------------------------------------------------------
    def home_new(self, title):
        title = title or ''
        self.page = self.mdp_type.markdownpage_set.find(title)
        if self.page:
            return self.redirect()

        return _mdpage_new_page(self.request, self, title)

    #---------------------------------------------------------------------------
    def home_search(self, search):
        return self.render('search.html',
            pages=self.mdp_type.markdownpage_set.search(search),
            search=search
        )

    #---------------------------------------------------------------------------
    def home_recent(self, *args):
        return self.render('recent.html',
            pages=self.mdp_type.markdownpage_set.order_by('-updated')
        )

    #---------------------------------------------------------------------------
    def home_listing(self, *args):
        return self.render('home.html',
            pages=self.mdp_type.markdownpage_set.order_by('title'),
            title='Page Listing'
        )

    #---------------------------------------------------------------------------
    def home_topic(self, tag):
        return self.render('home.html',
            pages=self.mdp_type.tagged_by(tag).order_by('title') if tag else [],
            title='Pages for topic "{}"'.format(tag),
            tag=tag
        )


################################################################################


#-------------------------------------------------------------------------------
def mdpage_home(request, prefix):
    vh = ViewHandler(request, prefix)
    for key in ('search', 'new', 'recent', 'topic', 'listing'):
        if key in request.GET:
            func = getattr(vh, 'home_{}'.format(key))
            return func(request.GET.get(key))
    
    home_slug = get_mdpage_setting('home_slug')
    if home_slug is not None:
        if vh.load_page(home_slug, raise_404=False):
            return vh.render('page.html')

    return vh.home_listing(None)


#-------------------------------------------------------------------------------
def mdpage_history(request, prefix, slug, version=None):
    vh = ViewHandler(request, prefix, slug)
    arc = None if version is None else vh.page.markdownpagearchive_set.get(version=version)
    return vh.render('history.html', archive=arc)


#-------------------------------------------------------------------------------
def mdpage_view(request, prefix, slug):
    vh = ViewHandler(request, prefix)
    if vh.load_page(slug, raise_404=False):
        return vh.render('page.html')

    if not request.user.is_authenticated():
        raise http.Http404('Page not found')
    
    return _mdpage_new_page(request, vh, slug.capitalize())


#-------------------------------------------------------------------------------
def mdpage_text(request, prefix, slug):
    vh = ViewHandler(request, prefix, slug)
    return http.HttpResponse(vh.page.text, content_type="text/plain; charset=utf8")


#-------------------------------------------------------------------------------
def mdpage_attach(request, prefix, slug):
    vh = ViewHandler(request, prefix, slug)
    if request.method == 'POST':
        form = ContentForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(vh.page)
            return vh.redirect()
    else:
        form =  ContentForm()

    return vh.render('attach.html', form=form)


#-------------------------------------------------------------------------------
def mdpage_edit(request, prefix, slug):
    vh = ViewHandler(request, prefix, slug)
    if request.method == 'POST':
        if 'cancel' in request.POST:
            vh.page.unlock(request)
            return vh.redirect()
            
        form = MarkdownPageForm(request.POST, instance=vh.page)
        if form.is_valid():
            form.save(request)
            return vh.redirect()
    else:
        if vh.page.lock(request):
            vh.page.unlock(request)
            # return mdpage_render(request, 'locked.html', mdp_type, data)
            
        form = MarkdownPageForm(instance=vh.page)

    return vh.render('edit.html', form=form)


