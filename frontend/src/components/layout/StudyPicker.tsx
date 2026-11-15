import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useWorkstationStore } from '@/stores/useWorkstationStore'

/** Switches the open study; lists every non-erased study on the server worklist. */
export function StudyPicker() {
  const worklist = useWorkstationStore((s) => s.worklist)
  const activeStudy = useWorkstationStore((s) => s.activeStudy)
  const selectWorklistStudy = useWorkstationStore((s) => s.selectWorklistStudy)
  const studies = worklist.filter((w) => !w.is_shredded)

  if (studies.length === 0) return null

  return (
    <Select
      value={activeStudy?.anonymous_study_instance_uid ?? ''}
      onValueChange={(uid) => {
        void selectWorklistStudy(uid)
      }}
    >
      <SelectTrigger aria-label="Open study" className="h-8 min-w-[220px] text-[13px]">
        <SelectValue placeholder="Open a study…" />
      </SelectTrigger>
      <SelectContent>
        {studies.map((entry) => (
          <SelectItem key={entry.anonymous_study_instance_uid} value={entry.anonymous_study_instance_uid}>
            {entry.file_name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
