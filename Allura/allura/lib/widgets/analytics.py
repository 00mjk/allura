import ew

class GoogleAnalytics(ew.Widget):
    template='jinja:allura:templates/widgets/analytics.html'
    defaults=dict(
        ew.Widget.defaults,
        accounts=['UA-XXXXX-X'])
