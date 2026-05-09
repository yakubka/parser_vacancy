#!/bin/bash
# Автозапуск агрегатора вакансий
# Запуск вручную: bash ~/job_aggregator/run.sh
# Добавить в cron (каждый день в 9:00):
#   crontab -e  → добавить строку:
#   0 9 * * * bash /Users/yakubka/job_aggregator/run.sh

cd /Users/yakubka/job_aggregator
source venv/bin/activate

echo "[$(date '+%Y-%m-%d %H:%M')] Запуск агрегатора..."
python main.py >> /tmp/job_aggregator.log 2>&1
echo "[$(date '+%Y-%m-%d %H:%M')] Готово"
