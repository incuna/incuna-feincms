from django import template
from feincms.module.page.models import Page, PageManager
from feincms.module.page.templatetags.feincms_page_tags import is_equal_or_parent_of

register = template.Library()

class GetFeincmsPageNode(template.Node):
    """
    example usage:
        {% get_feincms_page path as varname %}
    """
    def __init__(self, path, var_name):
        self.path = template.Variable(path)
        self.var_name = var_name

    def render(self, context):
        self.path = self.path.resolve(context)
        try: 
            context[self.var_name] = Page.objects.page_for_path(path=self.path)
        except Page.DoesNotExist:
            pass

        return u''

def get_feincms_page(parser, token):
    bits = token.contents.split()
    if len(bits) != 4:
        raise template.TemplateSyntaxError("'%s' tag takes three arguments" % bits[0])
    if bits[2] != 'as':
        raise template.TemplateSyntaxError("second argument to '%s' tag must be 'as'" % bits[0])

    return GetFeincmsPageNode(bits[1], bits[3])

register.tag('get_feincms_page', get_feincms_page)

class FeincmsPageMenuNode(template.Node):
    """
    Render the page navigation.
    arguments: 
        feincms_page: The current feincms_page.
        css_id: The css (dom) id to be used for the menu.
        level: The level at which to start the navigation.
        depth: The depth of sub navigation to include.
        show_all_subnav: Whether to show all sub navigation items (or just the ones in the current pages branch).
    example usage:
        {% feincms_page_menu  feincms_page 'nav' 1 2 %}
    """
    def __init__(self,  feincms_page, css_id="", level=1, depth=1, show_all_subnav=False):
        self.feincms_page = feincms_page
        self.css_id = css_id
        self.level = level
        self.depth = depth
        self.show_all_subnav = show_all_subnav

    def render(self, context):
        feincms_page = self.feincms_page.resolve(context)

        if not isinstance(feincms_page, Page):
            return ''

        level = int(self.level.resolve(context)if isinstance(self.level, template.FilterExpression) else self.level)
        depth = int(self.depth.resolve(context) if isinstance(self.depth, template.FilterExpression) else self.depth)
        css_id = self.css_id.resolve(context) if isinstance(self.css_id, template.FilterExpression) else self.css_id
        show_all_subnav = self.show_all_subnav.resolve(context) if isinstance(self.show_all_subnav, template.FilterExpression) else self.show_all_subnav

        if not 'request' in context:
            raise ValueError("No request in the context. Try using RequestContext in the view.")
        request = context['request']

        entries = self.entries(feincms_page, level, depth, show_all_subnav)

        if not entries:
            return ''

        def get_item(item, next_level, extra_context=None):
            context.push()

            if extra_context:
                context.update(extra_context)

            context['item'] = item
            context['url'] = item.get_absolute_url()
            context['is_current'] = context['url'] == request.path
            context['title'] = item.title

            if 'css_class' in context:
                context['css_class'] += ' ' + item.slug
            else:
                context['css_class'] = item.slug

            if context['is_current'] or is_equal_or_parent_of(item, feincms_page):
                context['css_class'] += ' selected'

            if next_level > item.level:
                context['down'] = next_level - item.level
            elif next_level < item.level:
                context['up'] = item.level - next_level

            html = template.loader.get_template('incunafein/page/menuitem.html').render(context)
            context.pop()

            return html

        output = ''
        item = entries[0]
        for i, next in enumerate(entries[1:]):
            output += get_item(item, next.level, {'css_class': i==0 and 'first' or ''})
            item = next
            
        output += get_item(item, entries[0].level, {'css_class': len(entries)==1 and 'first last' or 'last'})

        if css_id:
            attrs = ' id="%s"' % css_id
        else:
            attrs = ''

        return '<ul%s>%s</ul>' % (attrs, output)

    def entries(self, instance, level=1, depth=1, show_all_subnav=False):
        if level <= 1:
            if depth == 1:
                return Page.objects.toplevel_navigation()
            elif show_all_subnav:
                return Page.objects.in_navigation().filter(level__lt=depth)
            else:
                return Page.objects.toplevel_navigation() | \
                        instance.get_ancestors().filter(in_navigation=True) | \
                        instance.get_siblings(include_self=True).filter(in_navigation=True, level__lt=depth) | \
                        instance.children.filter(in_navigation=True, level__lt=depth)

        # mptt starts counting at 0, NavigationNode at 1; if we need the submenu
        # of the current page, we have to add 2 to the mptt level
        if instance.level + 2 == level:
            pass
        elif instance.level + 2 < level:
            try:
                queryset = instance.get_descendants().filter(level=level - 2, in_navigation=True)
                instance = PageManager.apply_active_filters(queryset)[0]
            except IndexError:
                return []
        else:
            instance = instance.get_ancestors()[level - 2]


        if depth == 1:
            return instance.children.in_navigation()
        elif show_all_subnav:
            queryset = instance.get_descendants().filter(level__lte=instance.level + depth, in_navigation=True)
            return PageManager.apply_active_filters(queryset)
        else:
            return instance.children.in_navigation() | \
                    instance.get_ancestors().filter(in_navigation=True, level__gte=level-1) | \
                    instance.get_siblings(include_self=True).filter(in_navigation=True, level__gte=level-1, level__lte=instance.level + depth)



def do_feincms_page_menu(parser, token):
    args = token.split_contents()
    if len(args) > 6:
        raise template.TemplateSyntaxError("'%s tag accepts no more than 5 arguments." % args[0])
    return FeincmsPageMenuNode(*map(parser.compile_filter, args[1:]))

register.tag('feincms_page_menu', do_feincms_page_menu)

