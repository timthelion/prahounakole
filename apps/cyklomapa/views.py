# views.py

from django.conf import settings
from django.contrib.gis.shortcuts import render_to_kml
from django.contrib.sites.shortcuts import get_current_site
from django.core.cache import cache
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import cache_page, never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.gzip import gzip_page
from django.views.generic import TemplateView

from django_comments.models import Comment

from webmap.models import Legend, MapPreset, Marker, OverlayLayer

from .models import Mesto, Poi


@gzip_page
@cache_page(24 * 60 * 60)  # cachujeme view v memcached s platnosti 24h
@csrf_protect
def mapa_view(request, poi_id=None):
    vrstvy = OverlayLayer.objects.filter(status__show=True)
    # volitelne poi_id zadane mape jako bod, na ktery se ma zazoomovat
    center_poi = None
    if poi_id:
        try:
            center_poi = Poi.visible.get(id=poi_id)
        except Poi.DoesNotExist:
            pass

    context = {
        'vrstvy': vrstvy,
        'center_poi': center_poi,
        'mesto': request.mesto,
        'presets': MapPreset.objects.filter(status__show=True),
        'mesta': Mesto.objects.filter(aktivni=True).order_by('sektor__name').all(),
    }
    if not (request.mesto and request.mesto.aktivni) and not request.user.is_authenticated:
        return render(request, 'neaktivni.html', context=context)

    return render(request, 'mapa.html', context=context)


def cache_page_mesto(expiration):
    def cache_page_mesto_dc(fn):
        def wrapper(*args, **kwargs):
            cache_key = 'kml_view_' + args[1] + '_' + args[0].mesto.sektor.slug
            result = cache.get(cache_key)
            if result is None:
                result = fn(*args, **kwargs)
                cache.set(cache_key, result, expiration)
            return result
        return wrapper
    return cache_page_mesto_dc


@gzip_page
@never_cache              # zabranime prohlizeci cachovat si kml
@cache_page_mesto(24 * 60 * 60)  # cachujeme view v memcached s platnosti 24h
def kml_view(request, nazev_vrstvy):
    # najdeme vrstvu podle slugu. pokud neexistuje, vyhodime 404
    v = get_object_or_404(OverlayLayer, slug=nazev_vrstvy, status__show=True)

    # vsechny body co jsou v teto vrstve a jsou zapnute
    points = Poi.visible.filter(marker__layer=v)
    return render_to_kml(
        "webmap/gis/kml/layer.kml", {
            'places': points,
            'site': get_current_site(request).domain,
        },
    )


@gzip_page
def popup_view(request, poi_id):
    poi = get_object_or_404(Poi, id=poi_id)

    return render(
        request,
        "gis/popup.html",
        context={
            'poi': poi,
            'fotky': poi.photos.filter(status__show=True),
            'settings': settings,
            'can_change': request.user.has_perm('webmap.change_poi'),  # and poi.has_change_permission(request.user),
        },
        content_type="application/xml",
    )


# vypisy uzavirek a metra pouzite na hlavnim webu PNK
@cache_page(24 * 60 * 60)  # cachujeme view v memcached s platnosti 24h
def uzavirky_view(request):
    poi = Poi.objects.select_related('marker').filter(status__show=True, marker__slug='vyluka_akt')
    return render(
        request,
        'uzavirky.html',
        context={'uzavirky': poi},
    )


@cache_page(24 * 60 * 60)  # cachujeme view v memcached s platnosti 24h
def metro_view(request):
    poi = Poi.objects.select_related('marker').filter(status__show=True, marker__slug__in=['metro_a', 'metro_b', 'metro_c']).order_by('marker__slug', 'id')
    return render(
        request,
        'metro.html',
        context={'poi': poi},
    )


# View pro podrobny vypis vrstev
@cache_page(24 * 60 * 60)  # cachujeme view v memcached s platnosti 24h
def znacky_view(request):
    vrstvy = OverlayLayer.objects.filter(status__show=True)
    znacky = Marker.objects.select_related('layer').filter(status__show=True)
    legenda = Legend.objects.all()
    return render(
        request,
        'znacky.html',
        context={'vrstvy': vrstvy, 'znacky': znacky, 'legenda': legenda},
    )


class PanelMapaView(TemplateView):
    template_name = "panel-mapa.html"

    def get_context_data(self, **kwargs):
        context = super(PanelMapaView, self).get_context_data(**kwargs)
        context['mesto'] = self.request.mesto
        return context


class PanelHledaniView(TemplateView):
    template_name = "panel-hledani.html"


class PopupListView(TemplateView):
    template_name = "popup-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['popups'] = Poi.objects.filter(status__show=True).order_by('last_modification').reverse()
        return context


class PanelInformaceView(TemplateView):
    template_name = "panel-informace.html"

    def get_context_data(self, **kwargs):
        context = super(PanelInformaceView, self).get_context_data(**kwargs)
        if self.request.mesto:
            context['historie'] = Poi.objects.filter(status__show=True, geom__bboverlaps=self.request.mesto.sektor.geom).order_by('last_modification').reverse()[:10]
            context['mesto'] = self.request.mesto
        context['uzavirky'] = Poi.objects.select_related('marker').filter(status__show=True, geom__bboverlaps=self.request.mesto.sektor.geom, marker__slug='vyluka_akt')[:10]
        # the lookup was "intersects", but it does not work for GeometryCollections
        pois_in_city = Poi.objects.select_related('marker').filter(geom__bboverlaps=self.request.mesto.sektor.geom)

        # TODO: This is workaround about following bug in Django: https://code.djangoproject.com/ticket/20271 Remove this code block once it is fixed for optimal query.
        pois_ids_in_city = cache.get('info-cache-pois-' + self.request.mesto.sektor.slug)
        if not pois_ids_in_city:
            pois_ids_in_city = [p.pk for p in pois_in_city]
            cache.set('info-cache-pois-' + self.request.mesto.sektor.slug, pois_ids_in_city, 3600)
        pois_in_city = pois_ids_in_city

        context['komentare'] = Comment.objects.filter(object_pk__in=pois_in_city).order_by('-submit_date')[:10]
        context['legenda'] = Legend.objects.all()

        return context
