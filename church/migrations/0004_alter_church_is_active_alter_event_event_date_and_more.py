from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('church', '0003_sitesettings_cover_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='church',
            name='is_active',
            field=models.BooleanField(db_index=True, default=True, verbose_name='Active'),
        ),
        migrations.AlterField(
            model_name='event',
            name='event_date',
            field=models.DateField(db_index=True, verbose_name='Date'),
        ),
        migrations.AlterField(
            model_name='sermon',
            name='sermon_date',
            field=models.DateField(blank=True, db_index=True, null=True, verbose_name='Date'),
        ),
        migrations.AddIndex(
            model_name='contactmessage',
            index=models.Index(fields=['church', 'is_read', 'created_at'], name='church_cont_church__05923c_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['church', 'is_active', 'event_date'], name='church_even_church__5e5f06_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['church', 'is_featured'], name='church_even_church__6fbfb3_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['church', 'event_date'], name='church_even_church__c8dc08_idx'),
        ),
        migrations.AddIndex(
            model_name='member',
            index=models.Index(fields=['church', 'is_active'], name='church_memb_church__f7bf7c_idx'),
        ),
        migrations.AddIndex(
            model_name='member',
            index=models.Index(fields=['church', 'gender'], name='church_memb_church__b9d98c_idx'),
        ),
        migrations.AddIndex(
            model_name='member',
            index=models.Index(fields=['church', 'last_name', 'first_name'], name='church_memb_church__1fa4ac_idx'),
        ),
        migrations.AddIndex(
            model_name='page',
            index=models.Index(fields=['church', 'is_active', 'is_in_menu'], name='church_page_church__7e7d13_idx'),
        ),
        migrations.AddIndex(
            model_name='page',
            index=models.Index(fields=['church', 'sort_order'], name='church_page_church__fcce58_idx'),
        ),
        migrations.AddIndex(
            model_name='sermon',
            index=models.Index(fields=['church', 'is_active', 'sermon_date'], name='church_serm_church__32e477_idx'),
        ),
        migrations.AddIndex(
            model_name='sermon',
            index=models.Index(fields=['church', 'is_featured'], name='church_serm_church__14b3aa_idx'),
        ),
        migrations.AddIndex(
            model_name='sermon',
            index=models.Index(fields=['church', 'sermon_date'], name='church_serm_church__53937e_idx'),
        ),
    ]
