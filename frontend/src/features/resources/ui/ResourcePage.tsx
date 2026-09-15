import { UploadDropzone } from './UploadDropzone'
import { ResourceList } from './ResourceList'
import { t } from '@/shared/lib/locale/zh'

export function ResourcePage() {
  return (
    <div className="mx-auto h-full max-w-3xl overflow-y-auto px-4 py-6">
      <h1 className="mb-4 text-lg font-medium">{t.resources.title}</h1>
      <UploadDropzone />
      <ResourceList />
    </div>
  )
}
