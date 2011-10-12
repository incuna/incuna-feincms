from django.db import models

def register(cls, admin_cls):
    cls.add_to_class('_prepared_date', models.TextField('Date of Preparation', blank=True, null=True))

    def getter(obj):
        if not obj._prepared_date:
            try:
                return obj.get_ancestors(ascending=True).filter(_prepared_date__isnull=False)[0]._prepared_date
            except IndexError:
                return None
        return obj._prepared_date

    def setter(obj, value):
        obj._prepared_date = value

    cls.prepared_date = property(getter, setter)

    if admin_cls and admin_cls.fieldsets:
        admin_cls.fieldsets[2][1]['fields'].append('_prepared_date')
