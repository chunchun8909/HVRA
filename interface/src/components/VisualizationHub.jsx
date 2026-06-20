import { useEffect, useState } from 'react'

const viewTabs = [
  { key: 'site', label: 'site map', title: 'site map' },
  { key: 'room', label: 'room', title: 'room view' },
  { key: 'links', label: 'links', title: 'links view' },
  { key: 'validation', label: 'check', title: 'validation view' },
  { key: 'report', label: 'report', title: 'final report' },
]

const fallbackStrategyOptions = [
  { id: 'option_1', label: 'option 1', name: 'waiting for validated option 1' },
  { id: 'option_2', label: 'option 2', name: 'waiting for validated option 2' },
  { id: 'option_3', label: 'option 3', name: 'waiting for validated option 3' },
]

export default function VisualizationHub({
  backendUrl,
  roomRef,
  kgRef,
  reportRef,
  enabledViews = ['room', 'links', 'validation', 'report'],
  viewerMode = 'review',
  isLoading = false,
  loadingLabel = '',
  loadingProgress = 0,
}) {
  const firstView = enabledViews[0] || 'room'
  const [activeView, setActiveView] = useState(firstView)
  const [strategyOptions, setStrategyOptions] = useState([])
  const [activeStrategyId, setActiveStrategyId] = useState('')
  const visibleTabs = viewTabs.filter((tab) => enabledViews.includes(tab.key))
  const selectedView = enabledViews.includes(activeView) ? activeView : firstView
  const encodedBackendUrl = encodeURIComponent(backendUrl)
  const siteSrc = `/risk_map_3d_test.html?embedded=1&api_base=${encodedBackendUrl}`
  const strategyQuery = activeStrategyId ? `&strategy_id=${encodeURIComponent(activeStrategyId)}` : ''
  const optionQuery = activeStrategyId ? `?strategy_id=${encodeURIComponent(activeStrategyId)}` : ''
  const roomSrc = `${backendUrl}/static-views/spatial/room_3d_view.html?viewer_mode=${viewerMode}&api_base=${encodedBackendUrl}${strategyQuery}`
  const kgSrc = `${backendUrl}/static-views/kg/kg_view.html${optionQuery}`
  const validationSrc = `${backendUrl}/static-views/validation_view.html${optionQuery}`
  const reportSrc = `${backendUrl}/static-views/final_report_view.html${optionQuery}`

  useEffect(() => {
    setActiveView(firstView)
  }, [firstView, viewerMode])

  useEffect(() => {
    if (viewerMode !== 'review') {
      setStrategyOptions([])
      setActiveStrategyId('')
      return
    }

    fetch(`${backendUrl}/api/strategy-options`)
      .then((response) => (response.ok ? response.json() : { options: [] }))
      .then((payload) => {
        const options = payload.options?.length ? payload.options : fallbackStrategyOptions
        setStrategyOptions(options)
        setActiveStrategyId((current) => current || options[0]?.id || '')
      })
      .catch(() => {
        setStrategyOptions(fallbackStrategyOptions)
        setActiveStrategyId((current) => current || fallbackStrategyOptions[0].id)
      })
  }, [backendUrl, viewerMode])

  const frameClass = (key) => `h-full w-full border-0 ${selectedView === key ? 'block' : 'hidden'}`

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-surface-secondary">
      <div className="type-level-1 flex items-center justify-between gap-3 border-b border-DEFAULT px-5 py-3">
        <div className="flex min-w-0 items-center gap-2">
          {strategyOptions.length && !isLoading ? (
            strategyOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                title={`${option.name}${option.status ? ` | ${option.status}` : ''}${option.confidence ? ` | ${option.confidence}` : ''}`}
                className={`type-level-3 rounded-sm border px-3 py-2 ${
                  activeStrategyId === option.id
                    ? 'border-strong bg-surface-primary text-ink-primary'
                    : 'border-DEFAULT bg-surface-secondary text-ink-tertiary'
                }`}
                onClick={() => setActiveStrategyId(option.id)}
              >
                {option.label}
              </button>
            ))
          ) : (
            <span>{isLoading ? loadingLabel || 'working' : viewTabs.find((tab) => tab.key === selectedView)?.title}</span>
          )}
        </div>
        {visibleTabs.length > 1 && !isLoading ? (
          <div className="flex gap-2">
            {visibleTabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={`type-level-3 rounded-sm border px-3 py-2 ${
                  selectedView === tab.key
                    ? 'border-strong bg-surface-primary text-ink-primary'
                    : 'border-DEFAULT bg-surface-secondary text-ink-tertiary'
                }`}
                onClick={() => setActiveView(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-hidden bg-surface-primary">
        {enabledViews.includes('site') ? <iframe src={siteSrc} title="risk map view" className={frameClass('site')} /> : null}
        {enabledViews.includes('room') ? <iframe ref={roomRef} src={roomSrc} title="room view" className={frameClass('room')} /> : null}
        {enabledViews.includes('links') ? <iframe ref={kgRef} src={kgSrc} title="links view" className={frameClass('links')} /> : null}
        {enabledViews.includes('validation') ? <iframe src={validationSrc} title="validation view" className={frameClass('validation')} /> : null}
        {enabledViews.includes('report') ? <iframe ref={reportRef} src={reportSrc} title="final report" className={frameClass('report')} /> : null}
      </div>

      {isLoading ? (
        <div className="absolute inset-x-0 bottom-0 border-t border-DEFAULT bg-surface-primary/95 px-5 py-4">
          <div className="mb-2 flex items-center justify-between type-level-3">
            <span>{loadingLabel || 'working'}</span>
            <span>{Math.round(loadingProgress)}%</span>
          </div>
          <div className="h-1 w-full bg-surface-tertiary">
            <div className="h-full bg-accent transition-[width] duration-300" style={{ width: `${Math.min(100, Math.max(0, loadingProgress))}%` }} />
          </div>
        </div>
      ) : null}
    </div>
  )
}

