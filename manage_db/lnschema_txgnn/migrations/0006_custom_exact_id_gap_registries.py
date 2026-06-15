# Generated manually 2026-06-11
#
# Adds exact-ID custom registries for canonical KG node types whose public
# bionty/pertdb write paths are not safe for parity repair.

import django.db.models.deletion
import django.db.models.functions.datetime
import lamindb.base.fields
import lamindb.base.uids
import lamindb.base.users
import lamindb.models.run
from django.db import migrations, models


def base_fields():
    return [
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
    ]


def tracking_fields():
    return [
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
    ]


def char_field(max_length, *, unique=False):
    return lamindb.base.fields.CharField(blank=True, db_index=True, default=None, max_length=max_length, unique=unique)


def nullable_char_field(max_length):
    return lamindb.base.fields.CharField(blank=True, db_index=True, default=None, max_length=max_length, null=True)


class Migration(migrations.Migration):
    dependencies = [
        ("lamindb", "0183_squashed"),
        ("lnschema_txgnn", "0005_custom_disease"),
    ]

    operations = [
        migrations.CreateModel(
            name="Gene",
            fields=base_fields()
            + [
                ("ensembl_gene_id", char_field(64, unique=True)),
                ("symbol", nullable_char_field(128)),
                ("name", nullable_char_field(512)),
                ("ncbi_gene_id", nullable_char_field(64)),
                ("hgnc_id", nullable_char_field(64)),
                ("uniprot_id", nullable_char_field(64)),
            ]
            + tracking_fields(),
            options={"abstract": False},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Molecule",
            fields=base_fields()
            + [
                ("chembl_id", char_field(64, unique=True)),
                ("ontology_id", nullable_char_field(64)),
                ("name", nullable_char_field(512)),
                ("inchikey", nullable_char_field(64)),
            ]
            + tracking_fields(),
            options={"abstract": False},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Pathway",
            fields=base_fields()
            + [
                ("ontology_id", char_field(64, unique=True)),
                ("name", nullable_char_field(512)),
            ]
            + tracking_fields(),
            options={"abstract": False},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Tissue",
            fields=base_fields()
            + [
                ("ontology_id", char_field(64, unique=True)),
                ("name", nullable_char_field(512)),
            ]
            + tracking_fields(),
            options={"abstract": False},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="CellType",
            fields=base_fields()
            + [
                ("ontology_id", char_field(64, unique=True)),
                ("name", nullable_char_field(512)),
            ]
            + tracking_fields(),
            options={"abstract": False},
            bases=(models.Model,),
        ),
    ]
