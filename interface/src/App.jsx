import { useEffect, useRef, useState } from 'react'
import InstructionBanner from './components/InstructionBanner'
import ChatStream from './components/ChatStream'
import ActionInputBar from './components/ActionInputBar'
import VisualizationHub from './components/VisualizationHub'

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8010'
const START_FROM_PHASE_ONE = import.meta.env.VITE_START_FROM_PHASE_ONE !== 'false'
const IS_PHASE_CHECK_PREVIEW = new URLSearchParams(window.location.search).has('phase_check')

if (IS_PHASE_CHECK_PREVIEW) {
  document.documentElement.dataset.phaseCheck = 'true'
}

const stageLabels = {
  input_gathering: 'getting details',
  processing: 'working',
  strategy_validation: 'review upgrades',
  spatial_vv: 'check layout',
  phase_1_to_2: 'building room',
  phase_2_to_3: 'running review',
}

const initialTasks = [
  { key: 'building_location', label: 'location', done: false },
  { key: 'site_context', label: 'site context', done: false },
  { key: 'room_type', label: 'room type', done: false },
  { key: 'room_area_m2', label: 'area', done: false },
  { key: 'room_height_m', label: 'height', done: false },
  { key: 'pano_image', label: 'room image', done: false },
  { key: 'occupant_profile', label: 'resident profile', done: false },
]

const initialMessages = [
  {
    role: 'agent',
    text: 'welcome to hvra. describe the room in the chat and add the room image to begin.',
  },
  {
    role: 'agent',
    text:
      'Please type one compact room brief. I need the building address or coordinates first so I can collect site context for weather, surrounding shade, vegetation, cooling access, and local heat exposure before the diagnosis stage.',
  },
  {
    role: 'agent',
    text: 'Then include room type, approximate room area, ceiling height, resident sensitivity, cooling access, construction age if known, and the main heat problem. Example: address: Carrer de Mallorca, Barcelona, bedroom, 18.5 m2, 2.8 m high, pre-1980, elderly resident, no AC, night overheating. Coordinates also work.',
  },
]

const phaseStageMap = {
  input: 'input_gathering',
  spatial: 'spatial_vv',
  review: 'processing',
}

function phaseOverrideStage() {
  const phase = new URLSearchParams(window.location.search).get('phase')
  return phaseStageMap[phase] || null
}

function App() {
  const forcedStage = phaseOverrideStage()
  const [splitPercent, setSplitPercent] = useState(33)
  const [messages, setMessages] = useState(initialMessages)
  const [tasks, setTasks] = useState(initialTasks)
  const [currentStage, setCurrentStage] = useState(forcedStage || 'input_gathering')
  const [transition, setTransition] = useState(null)
  const [progress, setProgress] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [refreshSignal, setRefreshSignal] = useState(0)
  const dragActive = useRef(false)
  const roomRef = useRef(null)
  const kgRef = useRef(null)
  const reportRef = useRef(null)
  const phase =
    transition === 'phase_1_to_2'
      ? 'spatial'
      : transition === 'phase_2_to_3'
        ? 'review'
        : currentStage === 'input_gathering'
          ? 'input'
          : currentStage === 'spatial_vv'
            ? 'spatial'
            : 'review'

  const appendMessage = (message) => {
    setMessages((prev) => [...prev, message])
  }

  useEffect(() => {
    if (!transition) {
      setProgress(0)
      return undefined
    }
    setProgress(8)
    const interval = window.setInterval(() => {
      setProgress((value) => {
        if (value >= 94) return value
        const step = transition === 'phase_1_to_2' ? 7 : 5
        return Math.min(94, value + step)
      })
    }, 420)
    return () => window.clearInterval(interval)
  }, [transition])

  useEffect(() => {
    if (forcedStage || START_FROM_PHASE_ONE) {
      return
    }
    fetch(`${DEFAULT_API_BASE}/api/status`)
      .then((response) => (response.ok ? response.json() : null))
      .then((status) => {
        if (!status?.current_stage) {
          return
        }
        setCurrentStage(status.current_stage === 'complete' ? 'processing' : status.current_stage)
        if (status.message) {
          setMessages((prev) =>
            prev.some((message) => message.text === status.message)
              ? prev
              : [...prev, { role: 'agent', text: status.message }],
          )
        }
      })
      .catch(() => {})
  }, [forcedStage])

  useEffect(() => {
    const handleMouseUp = () => {
      dragActive.current = false
    }

    const handleMouseMove = (event) => {
      if (!dragActive.current) {
        return
      }
      const next = (event.clientX / window.innerWidth) * 100
      setSplitPercent(Math.min(70, Math.max(30, next)))
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [])

  useEffect(() => {
    if (refreshSignal === 0) {
      return
    }

    if (roomRef.current) {
      roomRef.current.src = roomRef.current.src
    }
    if (kgRef.current) {
      kgRef.current.src = kgRef.current.src
    }
    if (reportRef.current) {
      reportRef.current.src = reportRef.current.src
    }
  }, [refreshSignal])

  useEffect(() => {
    const handleViewerMessage = (event) => {
      if (!event.data || typeof event.data !== 'object') {
        return
      }
      if (event.data.type === 'hvra_spatial_vv_saved') {
        appendMessage({
          role: 'agent',
          text: event.data.message || 'room check saved.',
        })
        setCurrentStage('spatial_vv')
      }
      if (event.data.type === 'hvra_spatial_vv_continue') {
        setTransition('phase_2_to_3')
        setProgress(100)
        appendMessage({
          role: 'agent',
          text:
            event.data.message ||
            'Room check saved. I am running diagnosis, validating upgrade options, and preparing the review views.',
        })
        window.setTimeout(() => {
          setTransition(null)
          setCurrentStage('processing')
          setRefreshSignal((value) => value + 1)
          appendMessage({
            role: 'agent',
            text:
              'Here are the upgrade options. Please tell me if any option feels unsuitable, too expensive, visually unacceptable, or if you want me to combine or revise the fixes.',
          })
        }, 650)
      }
      if (event.data.type === 'hvra_spatial_vv_error') {
        setTransition(null)
        appendMessage({
          role: 'system',
          text: `unable to continue from room check: ${event.data.message || 'unknown error'}`,
        })
      }
    }

    window.addEventListener('message', handleViewerMessage)
    return () => window.removeEventListener('message', handleViewerMessage)
  }, [])

  const updateTaskState = (missingInputs) => {
    setTasks(
      initialTasks.map((task) => ({
        ...task,
        done: missingInputs.length === 0 || !missingInputs.includes(task.key),
      })),
    )
  }

  const handleSend = async ({ text, panoFile, buildingInfo }) => {
    const hasBuildingInfo = Object.values(buildingInfo || {}).some((value) => String(value || '').trim())
    if (!text && !panoFile && !hasBuildingInfo) {
      return
    }

    appendMessage({ role: 'user', text: text || (hasBuildingInfo ? 'updated room basics' : 'uploaded new asset') })
    setIsSubmitting(true)
    setTransition('phase_1_to_2')

    try {
      const formData = new FormData()
      formData.append('client_stage', currentStage)
      if (text) {
        formData.append('text', text)
      }
      if (panoFile) {
        formData.append('pano_image', panoFile)
      }
      Object.entries(buildingInfo || {}).forEach(([key, value]) => {
        if (String(value || '').trim()) {
          formData.append(key, String(value).trim())
        }
      })

      const response = await fetch(`${DEFAULT_API_BASE}/api/chat`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorText = await response.text()
        setTransition(null)
        appendMessage({ role: 'system', text: `failed to send request: ${errorText}` })
        return
      }

      const payload = await response.json()
      appendMessage({ role: 'agent', text: payload.chat_message })
      updateTaskState(payload.missing_inputs || [])

      if (payload.refresh_views) {
        setRefreshSignal((value) => value + 1)
      }

      if (payload.current_stage === 'spatial_vv') {
        setProgress(100)
        window.setTimeout(() => {
          setTransition(null)
          setCurrentStage('spatial_vv')
          appendMessage({
            role: 'agent',
            text:
              'Please confirm the main window wall, wall directions, and detected window segments in the room view. Press save when it looks right, then continue to the diagnosis review.',
          })
        }, 650)
      } else {
        setTransition(null)
        setCurrentStage(payload.current_stage || 'input_gathering')
      }
    } catch (error) {
      setTransition(null)
      appendMessage({ role: 'system', text: 'unable to reach the backend. check the api server and try again.' })
    } finally {
      setIsSubmitting(false)
    }
  }

  const chatPanel = (
    <div className="flex min-w-0 flex-col overflow-hidden border-r border-DEFAULT bg-surface-primary">
      <div className="flex flex-col h-full overflow-hidden">
        <InstructionBanner tasks={tasks} currentStage={stageLabels[transition || currentStage] || currentStage.replaceAll('_', ' ')} />
        <ChatStream messages={messages} />
        <ActionInputBar onSend={handleSend} disabled={isSubmitting} showSetupInputs={false} />
      </div>
    </div>
  )

  if (phase === 'input') {
    return (
      <div className="h-screen overflow-hidden bg-surface-primary text-ink-primary">
        <div className="mx-auto flex h-full max-w-3xl flex-col border-x border-DEFAULT bg-surface-primary">
          <InstructionBanner tasks={tasks} currentStage={stageLabels[currentStage] || currentStage.replaceAll('_', ' ')} />
          <ChatStream messages={messages} />
          <ActionInputBar onSend={handleSend} disabled={isSubmitting} showSetupInputs />
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen overflow-hidden bg-surface-primary text-ink-primary">
      <div className="grid h-full" style={{ gridTemplateColumns: `${splitPercent}% 8px calc(${100 - splitPercent}% - 8px)` }}>
        {chatPanel}

        <div
          className="cursor-col-resize bg-surface-tertiary"
          onMouseDown={() => {
            dragActive.current = true
          }}
        />

        <div className="flex min-w-0 flex-col overflow-hidden bg-surface-secondary">
          <VisualizationHub
            backendUrl={DEFAULT_API_BASE}
            roomRef={roomRef}
            kgRef={kgRef}
            reportRef={reportRef}
            enabledViews={phase === 'spatial' ? ['room'] : ['components', 'report']}
            viewerMode={phase === 'spatial' ? 'spatial_vv' : 'review'}
            isLoading={Boolean(transition)}
            loadingLabel={
              transition === 'phase_1_to_2'
                ? 'building room model'
                : transition === 'phase_2_to_3'
                  ? 'running diagnosis and upgrades'
                  : ''
            }
            loadingProgress={progress}
            refreshSignal={refreshSignal}
          />
        </div>
      </div>
    </div>
  )
}

export default App



