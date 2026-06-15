# Generated manually 2026-06-11
#
# Adds a custom Disease registry for TxGNN disease-like source ontology IDs
# that are not represented by the live MONDO-backed bionty.Disease source.

import django.db.models.deletion
import django.db.models.functions.datetime
import lamindb.base.fields
import lamindb.base.uids
import lamindb.base.users
import lamindb.models.run
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lamindb", "0183_squashed"),
        ("lnschema_txgnn", "0004_protein"),
    ]

    operations = [
        migrations.CreateModel(
            name="Disease",
            fields=[
                ("is_locked", lamindb.base.fields.BooleanField(blank=True, db_default=False, default=False)),
                ("_aux", lamindb.base.fields.JSONField(blank=True, db_default=None, default=None, null=True)),
                (
                    "created_at",
                    lamindb.base.fields.DateTimeField(
                        blank=True,
                        db_default=django.db.models.functions.datetime.Now(),
                        db_index=True,
                        editable=False,
                    ),
                ),
                (
                    "updated_at",
                    lamindb.base.fields.DateTimeField(
                        blank=True,
                        db_default=django.db.models.functions.datetime.Now(),
                        db_index=True,
                        editable=False,
                    ),
                ),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "uid",
                    lamindb.base.fields.CharField(
                        blank=True,
                        db_index=True,
                        default=lamindb.base.uids.base62_12,
                        editable=False,
                        max_length=12,
                        unique=True,
                    ),
                ),
                (
                    "ontology_id",
                    lamindb.base.fields.CharField(
                        blank=True,
                        db_index=True,
                        default=None,
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "source_ontology",
                    lamindb.base.fields.CharField(blank=True, db_index=True, default=None, max_length=32, null=True),
                ),
                (
                    "name",
                    lamindb.base.fields.CharField(blank=True, db_index=True, default=None, max_length=512, null=True),
                ),
                (
                    "mondo_id",
                    lamindb.base.fields.CharField(blank=True, db_index=True, default=None, max_length=32, null=True),
                ),
                (
                    "omim_id",
                    lamindb.base.fields.CharField(blank=True, db_index=True, default=None, max_length=16, null=True),
                ),
                (
                    "doid_id",
                    lamindb.base.fields.CharField(blank=True, db_index=True, default=None, max_length=32, null=True),
                ),
                (
                    "icd10_code",
                    lamindb.base.fields.CharField(blank=True, db_index=True, default=None, max_length=16, null=True),
                ),
                (
                    "mesh_id",
                    lamindb.base.fields.CharField(blank=True, db_index=True, default=None, max_length=16, null=True),
                ),
                (
                    "hp_id",
                    lamindb.base.fields.CharField(blank=True, db_index=True, default=None, max_length=32, null=True),
                ),
                (
                    "branch",
                    lamindb.base.fields.ForeignKey(
                        blank=True,
                        db_default=1,
                        default=1,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="lamindb.branch",
                    ),
                ),
                (
                    "created_on",
                    lamindb.base.fields.ForeignKey(
                        blank=True,
                        db_default=1,
                        default=1,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="lamindb.branch",
                    ),
                ),
                (
                    "created_by",
                    lamindb.base.fields.ForeignKey(
                        blank=True,
                        default=lamindb.base.users.current_user_id,
                        editable=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="lamindb.user",
                    ),
                ),
                (
                    "run",
                    lamindb.base.fields.ForeignKey(
                        blank=True,
                        default=lamindb.models.run.current_run,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="lamindb.run",
                    ),
                ),
                (
                    "space",
                    lamindb.base.fields.ForeignKey(
                        blank=True,
                        db_default=1,
                        default=1,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="lamindb.space",
                    ),
                ),
            ],
            options={"abstract": False},
            bases=(models.Model,),
        ),
    ]
