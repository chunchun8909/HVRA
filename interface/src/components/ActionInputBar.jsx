import { useEffect, useRef, useState } from 'react'

const TEXTAREA_MIN_HEIGHT = 40
const TEXTAREA_MAX_HEIGHT = 106

export default function ActionInputBar({ onSend, disabled, showSetupInputs = true }) {
  const [text, setText] = useState('')
  const [panoFile, setPanoFile] = useState(null)
  const [buildingInfo, setBuildingInfo] = useState({
    room_type: '',
    room_area_m2: '',
    room_height_m: '',
  })
  const [activeZone, setActiveZone] = useState('')
  const textareaRef = useRef(null)

  const resizeTextarea = () => {
    const element = textareaRef.current
    if (!element) {
      return
    }

    element.style.height = `${TEXTAREA_MIN_HEIGHT}px`
    const nextHeight = Math.min(element.scrollHeight, TEXTAREA_MAX_HEIGHT)
    element.style.height = `${Math.max(TEXTAREA_MIN_HEIGHT, nextHeight)}px`
    element.style.overflowY = element.scrollHeight > TEXTAREA_MAX_HEIGHT ? 'auto' : 'hidden'
  }

  useEffect(() => {
    resizeTextarea()
  }, [text])

  const handleDrop = (event, setter) => {
    event.preventDefault()
    setActiveZone('')
    const file = event.dataTransfer.files?.[0]
    if (file) {
      setter(file)
    }
  }

  const handleFileChange = (event, setter) => {
    const file = event.target.files?.[0]
    if (file) {
      setter(file)
    }
  }

  const submit = async () => {
    if (disabled) {
      return
    }
    await onSend({ text: text.trim(), panoFile, buildingInfo })
    setText('')
    setPanoFile(null)
    setBuildingInfo({
      room_type: '',
      room_area_m2: '',
      room_height_m: '',
    })
  }

  const updateBuildingInfo = (key, value) => {
    setBuildingInfo((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div className="border-t border-DEFAULT bg-surface-primary px-5 py-3">
      {showSetupInputs ? (
        <>
          <div className="mb-2 grid grid-cols-3 gap-2">
            <input
              className="type-level-3 min-w-0 rounded-sm border border-DEFAULT bg-surface-secondary px-2 py-2 outline-none focus:border-strong"
              placeholder="room"
              value={buildingInfo.room_type}
              onChange={(event) => updateBuildingInfo('room_type', event.target.value)}
            />
            <input
              className="type-level-3 min-w-0 rounded-sm border border-DEFAULT bg-surface-secondary px-2 py-2 outline-none focus:border-strong"
              inputMode="decimal"
              placeholder="m2"
              value={buildingInfo.room_area_m2}
              onChange={(event) => updateBuildingInfo('room_area_m2', event.target.value)}
            />
            <input
              className="type-level-3 min-w-0 rounded-sm border border-DEFAULT bg-surface-secondary px-2 py-2 outline-none focus:border-strong"
              inputMode="decimal"
              placeholder="height"
              value={buildingInfo.room_height_m}
              onChange={(event) => updateBuildingInfo('room_height_m', event.target.value)}
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <label
              className={`type-level-3 inline-flex h-10 max-w-[168px] flex-1 basis-[148px] cursor-pointer items-center justify-between gap-2 rounded-sm border border-dashed border-strong bg-surface-secondary px-3 transition-colors duration-150 ${
                activeZone === 'pano' ? 'border-accent/40 text-accent' : ''
              }`}
              onDragOver={(event) => {
                event.preventDefault()
                setActiveZone('pano')
              }}
              onDragLeave={() => setActiveZone('')}
              onDrop={(event) => handleDrop(event, setPanoFile)}
            >
              <span>room image</span>
              <span className="truncate">{panoFile ? panoFile.name : 'choose'}</span>
              <input
                type="file"
                className="hidden"
                accept="image/*"
                onChange={(event) => handleFileChange(event, setPanoFile)}
              />
            </label>
          </div>
        </>
      ) : null}

      <div className="mt-3 flex items-end gap-2">
        <textarea
          ref={textareaRef}
          rows={1}
          className="type-level-2 min-h-10 flex-1 resize-none rounded-sm border border-DEFAULT bg-surface-secondary px-3 py-2 outline-none transition-colors duration-150 focus:border-strong focus:ring-0"
          placeholder="type address or coordinates, room basics, resident note"
          value={text}
          onChange={(event) => setText(event.target.value)}
          onInput={resizeTextarea}
        />
        <button
          type="button"
          className="inline-flex h-10 w-10 flex-shrink-0 items-center justify-center self-end rounded-sm bg-ink-primary text-surface-primary transition-opacity duration-150 disabled:cursor-not-allowed disabled:opacity-50"
          onClick={submit}
          disabled={disabled}
        >
          <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M5 12h13" />
            <path d="m13 6 6 6-6 6" />
          </svg>
          <span className="sr-only">send</span>
        </button>
      </div>
    </div>
  )
}
