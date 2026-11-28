// E4 FR-020 – nút Xuất CSV dùng chung (dữ liệu dựng sẵn bởi lib/exports).
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { downloadCsv } from '@/lib/csv'

export function ExportCsvButton({ filename, build, disabled }: { filename: string; build: () => string; disabled?: boolean }) {
  const { t } = useTranslation()
  return (
    <Button size="sm" variant="outline" disabled={disabled} onClick={() => downloadCsv(filename, build())} data-testid="export-csv">
      {t('dashboard.csv.export')}
    </Button>
  )
}
