from django.db import models
import os
from django.conf import settings


class CSVFile(models.Model):
    FILE_STATUS = [
        ('pending', 'Ожидает обработки'),
        ('processing', 'В обработке'),
        ('completed', 'Завершено'),
        ('error', 'Ошибка'),
    ]

    filename = models.CharField(max_length=255, verbose_name="Имя файла")
    status = models.CharField(max_length=20, choices=FILE_STATUS, default='pending', verbose_name="Статус")
    upload_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата обнаружения")
    processed_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата обработки")
    row_count = models.IntegerField(default=0, verbose_name="Количество строк")
    error_message = models.TextField(blank=True, verbose_name="Сообщение об ошибке")

    class Meta:
        verbose_name = "CSV файл"
        verbose_name_plural = "CSV файлы"
        ordering = ['-upload_date']

    def __str__(self):
        return self.filename

    @property
    def full_path(self):
        """Динамически вычисляет полный путь к файлу"""
        return os.path.join(settings.BASE_DIR, self.filename)

    @property
    def file_exists(self):
        """Проверяет, существует ли файл"""
        return os.path.exists(self.full_path)

    def get_file_size(self):
        """Возвращает размер файла"""
        if self.file_exists:
            size = os.path.getsize(self.full_path)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return "Файл не найден"


class CSVData(models.Model):
    csv_file = models.ForeignKey(CSVFile, on_delete=models.CASCADE, related_name='data_rows', verbose_name="CSV файл")
    row_number = models.IntegerField(verbose_name="Номер строки")
    data = models.JSONField(verbose_name="Данные строки")
    import_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата импорта")

    class Meta:
        verbose_name = "Данные CSV"
        verbose_name_plural = "Данные CSV"
        ordering = ['csv_file', 'row_number']

    def __str__(self):
        return f"{self.csv_file.filename} - Строка {self.row_number}"