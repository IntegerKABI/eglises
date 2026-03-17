from django.db import migrations, models
from django.utils.text import slugify


def _generate_unique_slug(base_value, queryset, max_length, fallback):
    base_slug = slugify(base_value) or fallback
    if max_length:
        base_slug = base_slug[:max_length]
    slug = base_slug
    counter = 2
    while queryset.filter(slug=slug).exists():
        suffix = f"-{counter}"
        trimmed = base_slug
        if max_length and len(base_slug) + len(suffix) > max_length:
            trimmed = base_slug[: max_length - len(suffix)]
        slug = f"{trimmed}{suffix}"
        counter += 1
    return slug


def populate_slugs(apps, schema_editor):
    Event = apps.get_model("church", "Event")
    Sermon = apps.get_model("church", "Sermon")

    for event in Event.objects.all().order_by("id"):
        queryset = Event.objects.filter(church_id=event.church_id).exclude(pk=event.pk)
        event.slug = _generate_unique_slug(event.slug or event.title, queryset, 120, "evenement")
        event.save(update_fields=["slug"])

    for sermon in Sermon.objects.all().order_by("id"):
        queryset = Sermon.objects.filter(church_id=sermon.church_id).exclude(pk=sermon.pk)
        sermon.slug = _generate_unique_slug(sermon.slug or sermon.title, queryset, 120, "sermon")
        sermon.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("church", "0010_merge_0009s"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="slug",
            field=models.SlugField(max_length=120, null=True, blank=True, verbose_name="Identifiant URL"),
        ),
        migrations.AddField(
            model_name="sermon",
            name="slug",
            field=models.SlugField(max_length=120, null=True, blank=True, verbose_name="Identifiant URL"),
        ),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="event",
            name="slug",
            field=models.SlugField(max_length=120, verbose_name="Identifiant URL"),
        ),
        migrations.AlterField(
            model_name="sermon",
            name="slug",
            field=models.SlugField(max_length=120, verbose_name="Identifiant URL"),
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.UniqueConstraint(fields=["church", "slug"], name="uniq_event_church_slug"),
        ),
        migrations.AddConstraint(
            model_name="sermon",
            constraint=models.UniqueConstraint(fields=["church", "slug"], name="uniq_sermon_church_slug"),
        ),
    ]
