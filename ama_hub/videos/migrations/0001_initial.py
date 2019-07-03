# -*- coding: utf-8 -*-
# Generated by Django 1.11.21 on 2019-07-03 14:50
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('base', '0027_auto_20170801_1228_squashed_0037_auto_20190222_1347'),
    ]

    operations = [
        migrations.CreateModel(
            name='Video',
            fields=[
                ('resourcebase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='base.ResourceBase')),
                ('title_en', models.CharField(help_text='name by which the cited resource is known', max_length=255, null=True, verbose_name='title')),
                ('abstract_en', models.TextField(blank=True, help_text='brief narrative summary of the content of the resource(s)', max_length=2000, null=True, verbose_name='abstract')),
                ('purpose_en', models.TextField(blank=True, help_text='summary of the intentions with which the resource(s) was developed', max_length=500, null=True, verbose_name='purpose')),
                ('constraints_other_en', models.TextField(blank=True, help_text='other restrictions and legal prerequisites for accessing and using the resource or metadata', null=True, verbose_name='restrictions other')),
                ('supplemental_information_en', models.TextField(default='No information provided', help_text='any other descriptive information about the dataset', max_length=2000, null=True, verbose_name='supplemental information')),
                ('data_quality_statement_en', models.TextField(blank=True, help_text="general explanation of the data producer's knowledge about the lineage of a dataset", max_length=2000, null=True, verbose_name='data quality statement')),
                ('video_file', models.FileField(blank=True, max_length=255, null=True, upload_to='videos', verbose_name='Video File')),
                ('extension', models.CharField(blank=True, max_length=128, null=True)),
                ('video_type', models.CharField(blank=True, max_length=128, null=True)),
                ('video_url', models.URLField(blank=True, help_text='The URL of the video.', max_length=255, null=True, verbose_name='URL')),
            ],
            options={
                'abstract': False,
                'manager_inheritance_from_future': True,
                'base_manager_name': 'objects',
            },
            bases=('base.resourcebase',),
        ),
        migrations.CreateModel(
            name='VideoResourceLink',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
                ('video', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='links', to='videos.Video')),
            ],
        ),
    ]
