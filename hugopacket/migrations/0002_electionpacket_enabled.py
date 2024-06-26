# Generated by Django 5.0.6 on 2024-05-16 07:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hugopacket", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="electionpacket",
            name="enabled",
            field=models.BooleanField(
                default=False,
                help_text="When not enabled, this packet's page will show up as not found",
            ),
        ),
    ]
