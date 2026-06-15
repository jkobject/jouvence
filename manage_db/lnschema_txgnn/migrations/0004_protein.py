# Generated manually 2026-06-10
#
# Adds the custom Protein registry for dedicated Ensembl Protein ENSP
# translation-product nodes. UniProt is stored as an xref, not as the primary
# TxGNN protein registry key.
# This migration only defines schema; it does not sync node data.

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
        ("lnschema_txgnn", "0003_alter_dataset_branch_alter_dataset_id_and_more"),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # Protein — Ensembl Protein ENSP primary IDs                          #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="Protein",
            fields=[
                (
                    "is_locked",
                    lamindb.base.fields.BooleanField(
                        blank=True, db_default=False, default=False
                    ),
                ),
                (
                    "_aux",
                    lamindb.base.fields.JSONField(
                        blank=True, db_default=None, default=None, null=True
                    ),
                ),
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
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
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
                    "ensembl_protein_id",
                    lamindb.base.fields.CharField(
                        blank=True,
                        db_index=True,
                        default=None,
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "ensembl_gene_id",
                    lamindb.base.fields.CharField(
                        blank=True,
                        db_index=True,
                        default=None,
                        max_length=64,
                        null=True,
                    ),
                ),
                (
                    "uniprot_id",
                    lamindb.base.fields.CharField(
                        blank=True,
                        db_index=True,
                        default=None,
                        max_length=16,
                        null=True,
                    ),
                ),
                (
                    "refseq_protein",
                    lamindb.base.fields.CharField(
                        blank=True,
                        db_index=True,
                        default=None,
                        max_length=64,
                        null=True,
                    ),
                ),
                (
                    "pdb_ids",
                    lamindb.base.fields.TextField(
                        blank=True, default=None, null=True
                    ),
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
