from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('claims', '0002_employeeprofile_is_company_admin'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='logo',
            field=models.ImageField(blank=True, upload_to='company-logos/'),
        ),
        migrations.CreateModel(
            name='ExpenseReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='receipts/%Y/%m/')),
                ('label', models.CharField(blank=True, max_length=120)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('claim', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='receipts', to='claims.expenseclaim')),
            ],
            options={
                'ordering': ['uploaded_at', 'id'],
            },
        ),
    ]